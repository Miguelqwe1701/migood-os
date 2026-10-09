"""Tests for overlay/usr/lib/migood-os/update against a fake Migood server.

Run:  python3 -m unittest discover tests
Everything happens in a temp folder; nothing on the real system is touched.
"""
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import tarfile
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
UPDATER = os.path.join(HERE, "..", "overlay", "usr", "lib", "migood-os", "update")
TOKEN = "test-token"


def load_updater():
    loader = importlib.machinery.SourceFileLoader("migood_update", UPDATER)
    spec = importlib.util.spec_from_loader("migood_update", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def make_bundle(marker_path):
    """A bundle whose apply.sh writes a marker file, so we can see it ran."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        script = f"echo applied >> '{marker_path}'\n".encode()
        info = tarfile.TarInfo("apply.sh")
        info.size = len(script)
        tar.addfile(info, io.BytesIO(script))
    return buf.getvalue()


class FakeServer(BaseHTTPRequestHandler):
    files = {}       # name -> bytes
    releases = []    # what /api/os/updates returns
    checkins = []
    ranges = []      # Range headers we received
    cut_first = set()  # names whose first download gets cut off halfway

    def log_message(self, *a):
        pass

    def authed(self):
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self.send_error(404)  # like the real server: hidden, not 401
            return False
        return True

    def do_GET(self):
        if not self.authed():
            return
        if self.path.startswith("/api/os/updates"):
            body = json.dumps(self.releases).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/api/os/files/"):
            name = self.path.rsplit("/", 1)[1]
            data = self.files.get(name)
            if data is None:
                return self.send_error(404)
            rng = self.headers.get("Range")
            self.ranges.append(rng)
            start = int(rng.split("=")[1].rstrip("-")) if rng else 0
            if start >= len(data):
                return self.send_error(416)
            chunk = data[start:]
            if name in self.cut_first:  # simulate a dropped connection
                self.cut_first.discard(name)
                chunk = chunk[: len(chunk) // 2]
            self.send_response(206 if rng else 200)
            self.send_header("Content-Length", str(len(chunk)))
            self.end_headers()
            self.wfile.write(chunk)
        else:
            self.send_error(404)

    def do_POST(self):
        if not self.authed():
            return
        n = int(self.headers.get("Content-Length", 0))
        self.checkins.append(json.loads(self.rfile.read(n)))
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")


class UpdaterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state = os.path.join(self.tmp, "state")
        os.makedirs(self.state)
        with open(os.path.join(self.state, "token"), "w") as f:
            f.write(TOKEN)
        self.osrel = os.path.join(self.tmp, "os-release")
        with open(self.osrel, "w") as f:
            f.write('NAME="Migood OS"\nVERSION="0.1.0"\nVERSION_ID="0.1.0"\nID=migood-os\n')

        FakeServer.files, FakeServer.releases = {}, []
        FakeServer.checkins, FakeServer.ranges, FakeServer.cut_first = [], [], set()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeServer)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

        self.conf = os.path.join(self.tmp, "update.conf")
        with open(self.conf, "w") as f:
            f.write(f"SERVER=http://127.0.0.1:{self.httpd.server_port}\nCHANNEL=beta\n")
        self.status = os.path.join(self.tmp, "status.json")
        os.environ.update(MIGOOD_CONF=self.conf, MIGOOD_STATE=self.state, MIGOOD_STATUS=self.status,
                          MIGOOD_OS_RELEASE=self.osrel, MIGOOD_NO_SNAPSHOT="1")
        self.up = load_updater()
        self.marker = os.path.join(self.tmp, "marker")

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def publish(self, version, name, data, sha=None, settings=None):
        FakeServer.files[name] = data
        FakeServer.releases.append({"version": version, "channel": "beta", "settings": settings or {},
                                    "files": [{"name": name, "size": len(data),
                                               "sha256": sha or hashlib.sha256(data).hexdigest()}]})

    # --- release settings the server delivers (minFrom, rollout, mandatory) ---
    def test_min_from_skips_a_jump_too_far(self):
        self.publish("0.3.0", "c.tar.gz", make_bundle(self.marker), settings={"minFrom": "0.2.0"})
        self.up.cmd_check()
        self.assertEqual(self.up.staged_versions(), [])  # 0.1.0 can't go straight to 0.3.0

    def test_min_from_counts_releases_staged_before_it(self):
        self.publish("0.2.0", "a.tar.gz", make_bundle(self.marker))
        self.publish("0.3.0", "c.tar.gz", make_bundle(self.marker), settings={"minFrom": "0.2.0"})
        self.up.cmd_check()
        self.assertEqual(self.up.staged_versions(), ["0.2.0", "0.3.0"])  # 0.2.0 installs first

    def test_rollout_is_stable_per_device(self):
        rel = {"version": "0.2.0", "settings": {"rollout": 50}}
        first = self.up.offered(rel, "0.1.0")
        self.assertEqual([self.up.offered(rel, "0.1.0") for _ in range(5)], [first] * 5)
        self.assertIsNone(self.up.offered({"version": "0.2.0", "settings": {"rollout": 0}}, "0.1.0"))
        self.assertIsNone(self.up.offered({"version": "0.2.0", "settings": {"rollout": 100}}, "0.1.0"))

    def test_rollout_reaches_about_that_share_of_pcs(self):
        taken = 0
        for i in range(400):
            with open(os.path.join(self.state, "device-id"), "w") as f:
                f.write(f"pc-{i}\n")
            taken += self.up.offered({"version": "0.2.0", "settings": {"rollout": 25}}, "0.1.0") is None
        self.assertTrue(70 <= taken <= 130, taken)  # ~25% of 400

    def test_mandatory_shown_to_the_app(self):
        self.publish("0.2.0", "a.tar.gz", make_bundle(self.marker), settings={"mandatory": True})
        self.up.cmd_check()
        self.up.write_status("ok")
        with open(self.status) as f:
            self.assertTrue(json.load(f)["staged"][0]["mandatory"])

    def version(self):
        return self.up.read_kv(self.osrel)["VERSION_ID"]

    def test_check_then_apply_oldest_first(self):
        # Published out of order on purpose: the updater must sort them.
        self.publish("0.10.0", "b.tar.gz", make_bundle(self.marker))
        self.publish("0.2.0", "a.tar.gz", make_bundle(self.marker))
        self.assertEqual(self.up.cmd_check(), 0)
        self.assertEqual(self.up.staged_versions(), ["0.2.0", "0.10.0"])
        self.assertEqual(self.version(), "0.1.0")  # nothing installed yet

        self.assertEqual(self.up.cmd_apply(), 0)
        self.assertEqual(self.version(), "0.10.0")
        with open(self.marker) as f:
            self.assertEqual(f.read().count("applied"), 2)
        self.assertEqual(self.up.staged_versions(), [])
        self.assertEqual(FakeServer.checkins[-1]["version"], "0.10.0")
        self.assertEqual(FakeServer.checkins[-1]["channel"], "beta")

    def test_bad_sha256_is_rejected(self):
        self.publish("0.2.0", "a.tar.gz", make_bundle(self.marker), sha="0" * 64)
        with self.assertRaises(RuntimeError):
            self.up.cmd_check()
        self.assertEqual(self.up.staged_versions(), [])
        self.assertFalse(os.path.exists(
            os.path.join(self.state, "staged", "0.2.0", "a.tar.gz.part")))

    def test_resume_after_dropped_download(self):
        data = make_bundle(self.marker) + b"x" * 100_000
        self.publish("0.2.0", "a.tar.gz", data)
        FakeServer.cut_first.add("a.tar.gz")
        with self.assertRaises(RuntimeError):  # half a file fails the check...
            self.up.cmd_check()
        # ...so the part file was thrown away and the next run starts clean.
        self.assertEqual(self.up.cmd_check(), 0)
        self.assertEqual(self.up.staged_versions(), ["0.2.0"])

    def test_resume_uses_range(self):
        data = b"y" * 50_000
        self.publish("0.2.0", "a.tar.gz", data)
        folder = os.path.join(self.state, "staged", "0.2.0")
        os.makedirs(folder)
        with open(os.path.join(folder, "a.tar.gz.part"), "wb") as f:
            f.write(data[:20_000])  # pretend the last run stopped here
        part = self.up.download([f"http://127.0.0.1:{self.httpd.server_port}"],
                                "a.tar.gz", os.path.join(folder, "a.tar.gz"))
        self.assertEqual(FakeServer.ranges[-1], "bytes=20000-")
        with open(part, "rb") as f:
            self.assertEqual(f.read(), data)

    def test_iso_files_are_skipped(self):
        self.publish("0.2.0", "migood-os-0.2.0.iso", b"big iso")
        self.up.cmd_check()
        self.assertEqual(FakeServer.ranges, [])  # never downloaded

    def test_path_escape_refused(self):
        for bad in ["../evil", "/etc/passwd", ".hidden", "a/b", ""]:
            with self.assertRaises(ValueError):
                self.up.safe_name(bad)

    def test_failed_bundle_keeps_old_version(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            script = b"exit 1\n"
            info = tarfile.TarInfo("apply.sh")
            info.size = len(script)
            tar.addfile(info, io.BytesIO(script))
        self.publish("0.2.0", "a.tar.gz", buf.getvalue())
        self.up.cmd_check()
        with self.assertRaises(Exception):
            self.up.cmd_apply()
        self.assertEqual(self.version(), "0.1.0")
        self.assertEqual(self.up.staged_versions(), ["0.2.0"])  # retried next time

    def test_up_to_date(self):
        self.assertEqual(self.up.cmd_check(), 0)
        self.assertEqual(self.up.staged_versions(), [])

    def test_falls_back_when_first_server_blocked(self):
        # A "Cloudflare" that blocks every request with 403.
        class Blocked(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                self.send_error(403)
            do_POST = do_GET
        cf = ThreadingHTTPServer(("127.0.0.1", 0), Blocked)
        threading.Thread(target=cf.serve_forever, daemon=True).start()
        try:
            with open(self.conf, "w") as f:
                f.write(f"SERVERS=http://127.0.0.1:{cf.server_port} "
                        f"http://127.0.0.1:{self.httpd.server_port}\nCHANNEL=beta\n")
            self.publish("0.2.0", "a.tar.gz", make_bundle(self.marker))
            self.assertEqual(self.up.cmd_check(), 0)
            self.assertEqual(self.up.staged_versions(), ["0.2.0"])
        finally:
            cf.shutdown()
            cf.server_close()

    def test_404_does_not_fall_back(self):
        # 404 = "not in the Migood Beta"; the answer is real, don't retry elsewhere.
        with open(os.path.join(self.state, "token"), "w") as f:
            f.write("wrong-token")
        with open(self.conf, "w") as f:
            f.write(f"SERVERS=http://127.0.0.1:{self.httpd.server_port} "
                    f"http://127.0.0.1:1\nCHANNEL=beta\n")
        self.assertEqual(self.up.main(["update", "check"]), 1)

    def test_status_file_for_the_app(self):
        self.publish("0.2.0", "a.tar.gz", make_bundle(self.marker))
        FakeServer.releases[0]["notes"] = "New shelf"
        self.assertEqual(self.up.main(["update", "check"]), 0)
        with open(self.status) as f:
            st = json.load(f)
        self.assertEqual(st["result"], "ok")
        self.assertEqual(st["version"], "0.1.0")
        self.assertEqual(st["staged"], [{"version": "0.2.0", "notes": "New shelf", "mandatory": False}])
        self.assertNotIn(TOKEN, json.dumps(st))  # never leak the token

    def test_status_when_not_in_beta(self):
        with open(os.path.join(self.state, "token"), "w") as f:
            f.write("wrong-token")
        self.up.main(["update", "check"])
        with open(self.status) as f:
            self.assertEqual(json.load(f)["result"], "no-access")

    def test_version_order(self):
        self.assertLess(self.up.version_key("0.9.0"), self.up.version_key("0.10.0"))

    def test_github_releases_fallback_and_check_github(self):
        bundle = make_bundle(self.marker)
        sha = hashlib.sha256(bundle).hexdigest()

        class FakeGitHub(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                base = f"http://127.0.0.1:{self.server.server_port}"
                if self.path == "/releases":
                    body = json.dumps([{
                        "tag_name": "v0.2.0",
                        "draft": False,
                        "prerelease": True,
                        "assets": [
                            {"name": "migood-os-0.2.0-update.tar.gz", "browser_download_url": f"{base}/asset/bundle.tar.gz"},
                            {"name": "migood-os-0.2.0-update.tar.gz.sha256", "browser_download_url": f"{base}/asset/bundle.sha256"},
                        ],
                    }]).encode()
                elif self.path == "/asset/bundle.tar.gz":
                    body = bundle
                elif self.path == "/asset/bundle.sha256":
                    body = f"{sha}  migood-os-0.2.0-update.tar.gz\n".encode()
                else:
                    return self.send_error(404)
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        gh = ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHub)
        threading.Thread(target=gh.serve_forever, daemon=True).start()
        try:
            with open(self.conf, "w") as f:
                f.write(f"SERVER=http://127.0.0.1:{self.httpd.server_port}\n"
                        f"CHANNEL=beta\n"
                        f"GITHUB_RELEASES=http://127.0.0.1:{gh.server_port}/releases\n")
            # Server has no releases -> falls back to GitHub Releases and stages 0.2.0
            self.assertEqual(self.up.main(["update", "check"]), 0)
            self.assertEqual(self.up.staged_versions(), ["0.2.0"])
            with open(self.status) as f:
                st = json.load(f)
            self.assertEqual(st["staged"][0]["source"], "github")
            self.assertIn("latest release/pre-release", st["staged"][0]["notes"])
            self.assertEqual(self.up.cmd_apply(), 0)
            self.assertEqual(self.version(), "0.2.0")
        finally:
            gh.shutdown()
            gh.server_close()


if __name__ == "__main__":
    unittest.main()
