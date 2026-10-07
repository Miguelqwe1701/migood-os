"""build/fetch-assets.sh against a pretend Migood server: the app must match
linux.json's size and sha256, or the build stops."""
import hashlib
import http.server
import json
import os
import subprocess
import tempfile
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = b"pretend Migood Games tarball " * 1000


class Server(http.server.BaseHTTPRequestHandler):
    info = {}       # what linux.json says; the tests change it
    payload = APP   # what the download really is

    def do_GET(self):
        if self.path == "/downloads/desktop/linux.json":
            body = json.dumps(Server.info).encode()
        elif self.path == Server.info.get("url"):
            body = Server.payload
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class FetchAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = http.server.HTTPServer(("127.0.0.1", 0), Server)
        cls.url = f"http://127.0.0.1:{cls.httpd.server_port}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        self.assets = tempfile.TemporaryDirectory()
        Server.payload = APP
        Server.info = {"version": "3.9.1", "file": "Migood-Games-3.9.1.tar.gz",
                       "url": "/downloads/desktop/Migood-Games-3.9.1.tar.gz",
                       "size": len(APP), "sha256": hashlib.sha256(APP).hexdigest()}

    def tearDown(self):
        self.assets.cleanup()

    def fetch(self, servers=None):
        env = {**os.environ, "ASSETS": self.assets.name, "SERVERS": servers or self.url,
               "no_proxy": "127.0.0.1", "NO_PROXY": "127.0.0.1"}
        return subprocess.run(["bash", "build/fetch-assets.sh"], cwd=REPO, env=env,
                              capture_output=True, text=True)

    def test_good_download(self):
        r = self.fetch()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(self.assets.name, "migood-games-3.9.1.tar.gz"), "rb") as f:
            self.assertEqual(f.read(), APP)
        with open(os.path.join(self.assets.name, "migood-games.version")) as f:
            self.assertEqual(f.read().strip(), "3.9.1")

    def test_swapped_file_stops_the_build(self):
        Server.payload = APP.replace(b"pretend", b"swapped")  # same size, other bytes
        r = self.fetch()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(os.listdir(self.assets.name), [])  # nothing half-done left behind

    def test_no_server(self):
        r = self.fetch("http://127.0.0.1:9")  # nothing listens on port 9
        self.assertEqual(r.returncode, 2, r.stdout)


if __name__ == "__main__":
    unittest.main()
