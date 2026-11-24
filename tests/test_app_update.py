"""migood-app-update: keeps the Migood Games app up to date, with a pretend
Migood server and a pretend computer (MIGOOD_ROOT)."""
import hashlib
import http.server
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import stat
import tarfile
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "..", "overlay/usr/lib/migood-os/migood-app-update")


def app_tarball(version, evil=False):
    """A pretend app release: Migood-Games-<v>-x64/{migood-games, chrome-sandbox, resources/}."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        top = f"Migood-Games-{version}-x64"
        for name, mode, data in ((f"{top}/migood-games", 0o755, f"app {version}".encode()),
                                 (f"{top}/chrome-sandbox", 0o755, b"sandbox"),
                                 (f"{top}/resources/app.asar", 0o644, b"asar")):
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), mode
            tar.addfile(info, io.BytesIO(data))
        if evil:
            info = tarfile.TarInfo(f"{top}/../../etc/evil")
            info.size = 1
            tar.addfile(info, io.BytesIO(b"x"))
    return buf.getvalue()


class Server(http.server.BaseHTTPRequestHandler):
    version, blob, lie = "3.14.1", b"", False

    def do_GET(self):
        url = f"/downloads/desktop/Migood-Games-{Server.version}-x64.tar.gz"
        if self.path == "/downloads/desktop/linux.json":
            body = json.dumps({"version": Server.version, "url": url, "size": len(Server.blob),
                               "sha256": "0" * 64 if Server.lie else hashlib.sha256(Server.blob).hexdigest()}).encode()
        elif self.path == url:
            body = Server.blob
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class AppUpdate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Server)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        os.environ["no_proxy"] = os.environ["NO_PROXY"] = "127.0.0.1"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.state = os.path.join(self.root, "var/lib/migood-os")
        os.environ.update(MIGOOD_ROOT=self.root, MIGOOD_STATE=self.state, MIGOOD_APP_RUNNING="0",
                          MIGOOD_APP_SERVERS=f"http://127.0.0.1:{self.httpd.server_port}")
        Server.version, Server.blob, Server.lie = "3.14.1", app_tarball("3.14.1"), False
        loader = importlib.machinery.SourceFileLoader("au", TOOL)
        spec = importlib.util.spec_from_loader("au", loader)
        self.au = importlib.util.module_from_spec(spec)
        loader.exec_module(self.au)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def path(self, p):
        return os.path.join(self.root, p.lstrip("/"))

    def read(self, p):
        with open(self.path(p)) as f:
            return f.read()

    def test_fresh_install_sets_everything_up(self):
        self.assertEqual(self.au.main([]), 0)
        self.assertEqual(self.read("/opt/migood-games/migood-games"), "app 3.14.1")
        self.assertEqual(self.read("/usr/share/migood-os/migood-games.version").strip(), "3.14.1")
        self.assertTrue(os.stat(self.path("/opt/migood-games/chrome-sandbox")).st_mode & stat.S_ISUID)
        self.assertIn("MimeType=x-scheme-handler/migood;", self.read("/usr/share/applications/migood-games.desktop"))
        self.assertIn("migood-games --hidden", self.read("/etc/xdg/autostart/migood-games.desktop"))
        self.assertIn("userns,", self.read("/etc/apparmor.d/migood-games"))

    def test_update_replaces_old_app_and_skips_when_current(self):
        self.au.main([])
        Server.version, Server.blob = "3.15.0", app_tarball("3.15.0")
        self.au.main([])
        self.assertEqual(self.read("/opt/migood-games/migood-games"), "app 3.15.0")
        self.assertFalse(os.path.exists(self.path("/opt/migood-games.old")))
        Server.version, Server.blob = "3.10.0", app_tarball("3.10.0")  # never downgrade
        self.au.main([])
        self.assertEqual(self.read("/opt/migood-games/migood-games"), "app 3.15.0")

    def test_open_app_is_updated_at_next_start_up(self):
        os.environ["MIGOOD_APP_RUNNING"] = "1"
        self.au.main([])
        self.assertFalse(os.path.exists(self.path("/opt/migood-games")))  # not swapped under it
        self.assertTrue(os.path.exists(os.path.join(self.state, "app-staged/app.tar.gz")))
        self.au.main(["--apply-staged"])
        self.assertEqual(self.read("/opt/migood-games/migood-games"), "app 3.14.1")
        self.assertFalse(os.path.exists(os.path.join(self.state, "app-staged")))

    def test_bad_download_is_refused(self):
        Server.lie = True
        with self.assertRaises(ValueError):
            self.au.main([])
        self.assertFalse(os.path.exists(self.path("/opt/migood-games")))

    def test_archive_escaping_the_app_folder_is_refused(self):
        self.au.main([])
        bad = os.path.join(self.root, "evil.tar.gz")
        with open(bad, "wb") as f:
            f.write(app_tarball("9.9.9", evil=True))
        with self.assertRaises(ValueError):
            self.au.main(["--install-tarball", bad])
        self.assertEqual(self.read("/opt/migood-games/migood-games"), "app 3.14.1")  # old app kept

    def test_real_release_installs(self):
        """The real Migood Games 3.14.1 download, if this machine has it."""
        real = os.environ.get("MIGOOD_REAL_APP_TGZ")
        if not real or not os.path.exists(real):
            self.skipTest("set MIGOOD_REAL_APP_TGZ to a real release to run this")
        self.au.main(["--install-tarball", real, "--version", "3.14.1"])
        self.assertTrue(os.access(self.path("/opt/migood-games/migood-games"), os.X_OK))
        self.assertTrue(os.path.exists(self.path("/opt/migood-games/resources/app.asar")))


if __name__ == "__main__":
    unittest.main()
