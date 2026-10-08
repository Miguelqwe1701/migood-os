"""The installer's USB check (Calamares module migoodcheck) with a fake
Calamares, a pretend USB stick and a pretend Migood server."""
import hashlib
import http.server
import importlib.util
import os
import sys
import tempfile
import threading
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, "..", "overlay/usr/lib/x86_64-linux-gnu/calamares/modules/migoodcheck/main.py")
GOOD = os.urandom(300_000)
SHA = hashlib.sha256(GOOD).hexdigest()
NAME = "migood-os-9.9.9-filesystem.squashfs"


def fake_calamares():
    """Just the parts of Calamares' Python API the module uses."""
    lib = types.ModuleType("libcalamares")
    store = {}
    lib.globalstorage = types.SimpleNamespace(insert=store.__setitem__, value=store.get)
    lib.job = types.SimpleNamespace(configuration={}, setprogress=lambda p: None)
    lib.utils = types.SimpleNamespace(warning=lambda m: None)
    return lib, store


class Server(http.server.BaseHTTPRequestHandler):
    payload = GOOD
    drop_first = False  # cut the first response short, like Wi-Fi dropping

    def do_GET(self):
        if self.path != f"/downloads/os/{NAME}":
            self.send_response(404)
            self.end_headers()
            return
        start = 0
        rng = self.headers.get("Range")
        if rng:
            start = int(rng.split("=")[1].rstrip("-"))
        body = Server.payload[start:]
        self.send_response(206 if rng else 200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if Server.drop_first:
            Server.drop_first = False
            self.wfile.write(body[:len(body) // 3])
            self.wfile.flush()
            self.connection.shutdown(2)  # hang up mid-file
            return
        self.wfile.write(body)

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


class MigoodCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Server)
        cls.url = f"http://127.0.0.1:{cls.httpd.server_port}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        os.environ["no_proxy"] = os.environ["NO_PROXY"] = "127.0.0.1"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cdrom = os.path.join(self.tmp.name, "cdrom")
        self.root = os.path.join(self.tmp.name, "target")
        os.makedirs(os.path.join(self.cdrom, "casper"))
        os.makedirs(self.root)
        with open(os.path.join(self.cdrom, "casper/filesystem.squashfs.sha256"), "w") as f:
            f.write(f"{SHA}  {NAME}\n")
        Server.payload, Server.drop_first = GOOD, False
        self.lib, self.store = fake_calamares()
        sys.modules["libcalamares"] = self.lib
        os.environ["MIGOOD_USB_CHECK"] = os.path.join(self.tmp.name, "usb-check")
        spec = importlib.util.spec_from_file_location("migoodcheck", MODULE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.mounts = []
        self.m.run_cmd = lambda *cmd: self.mounts.append(cmd)  # no real mounting in tests
        self.store["rootMountPoint"] = self.root

    def tearDown(self):
        self.tmp.cleanup()

    def stick(self, data):
        with open(os.path.join(self.cdrom, "casper/filesystem.squashfs"), "wb") as f:
            f.write(data)

    def step(self, mode, servers=None):
        self.lib.job.configuration = {"mode": mode, "cdrom": self.cdrom,
                                      "servers": servers or [self.url]}
        return self.m.run()

    def test_good_stick_needs_nothing(self):
        self.stick(GOOD)
        self.assertIsNone(self.step("verify"))
        self.assertIsNone(self.step("repair"))
        self.assertEqual(self.mounts, [])

    def test_damaged_and_offline_stops_before_the_disk(self):
        self.stick(GOOD[:-10] + b"x" * 10)
        err = self.step("verify", servers=["http://127.0.0.1:9"])  # nothing listens there
        self.assertEqual(err[0], "The USB stick is damaged")

    def test_damaged_stick_is_repaired_from_the_internet(self):
        self.stick(GOOD[:1000])  # half the file is unreadable / missing
        Server.drop_first = True  # and the Wi-Fi drops once mid-download
        self.assertIsNone(self.step("verify"))
        self.assertIsNone(self.step("repair"))
        got = os.path.join(self.root, "var/tmp/migood-filesystem.squashfs")
        with open(got, "rb") as f:
            self.assertEqual(f.read(), GOOD)
        self.assertEqual(self.mounts[0][:2], ("mount", "--bind"))
        self.assertIsNone(self.step("cleanup"))
        self.assertFalse(os.path.exists(got))  # no 4 GB left behind on the new disk
        self.assertEqual(self.mounts[1][0], "umount")

    def test_bad_download_is_refused(self):
        self.stick(b"broken")
        Server.payload = os.urandom(len(GOOD))  # wrong bytes from the server
        self.step("verify")
        err = self.step("repair")
        self.assertEqual(err[0], "Couldn't download Migood OS")
        self.assertEqual(self.mounts, [])

    def test_old_iso_without_fingerprint_is_not_blocked(self):
        os.remove(os.path.join(self.cdrom, "casper/filesystem.squashfs.sha256"))
        self.stick(b"anything")
        self.assertIsNone(self.step("verify"))
        self.assertIsNone(self.step("repair"))

    def test_skipped_check_does_not_read_the_stick(self):
        self.stick(b"broken")  # would fail the check...
        with open(os.environ["MIGOOD_USB_CHECK"], "w") as f:
            f.write(f"{SHA} skipped\n")  # ...but the owner pressed "Skip check"
        self.assertIsNone(self.step("verify"))
        self.assertFalse(self.store["migoodNeedsRepair"])

    def test_good_result_is_saved_for_a_retry(self):
        self.stick(GOOD)
        self.step("verify")
        with open(os.environ["MIGOOD_USB_CHECK"]) as f:
            self.assertEqual(f.read().split(), [SHA, "ok"])

    def test_an_error_becomes_a_message_not_a_crash(self):
        self.stick(b"broken")
        self.step("verify")
        def boom(*_):
            raise RuntimeError("disk vanished")
        self.m.download = boom
        err = self.step("repair")
        self.assertEqual(err[0], "Couldn't install Migood OS")
        self.assertIn("disk vanished", err[1])

    def test_repair_without_a_mount_point_is_a_message(self):
        self.stick(b"broken")
        self.step("verify")
        self.store["rootMountPoint"] = None
        self.assertEqual(self.step("repair")[0], "Couldn't install Migood OS")

    def test_command_line_check(self):
        self.lib.job.configuration = {}
        self.m.libcalamares = None  # like migood-install runs it
        self.m.CDROM = self.cdrom
        self.stick(GOOD)
        self.assertEqual(self.m.cli_check(), 0)
        os.remove(os.environ["MIGOOD_USB_CHECK"])
        self.stick(b"broken")
        self.assertEqual(self.m.cli_check(), 1)


if __name__ == "__main__":
    unittest.main()
