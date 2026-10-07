"""tools/publish-os.py against a pretend Migood publish server: chunked upload
with resume, then the release. The key must never show up in the output."""
import hashlib
import http.server
import json
import os
import re
import subprocess
import tempfile
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = "test-publish-key-not-real"


class Server(http.server.BaseHTTPRequestHandler):
    uploads, files, releases, auth_ok = {}, {}, [], True
    chunk_max = 1000
    nudge_once = True  # answer one chunk with 409, like a resume after a drop

    def answer(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def authed(self):
        if self.headers.get("Authorization") != "Bearer " + KEY:
            Server.auth_ok = False
            self.answer(401, {"error": "bad key"})
            return False
        return True

    def do_POST(self):
        if not self.authed():
            return
        if self.path == "/api/os/publish/upload":
            req = json.loads(self.body())
            uid = hashlib.md5(req["name"].encode()).hexdigest()
            Server.uploads[uid] = {**req, "data": b""}
            return self.answer(200, {"id": uid, "received": 0, "chunkMax": Server.chunk_max})
        m = re.fullmatch(r"/api/os/publish/upload/(\w+)/finish", self.path)
        if m:
            u = Server.uploads[m.group(1)]
            if hashlib.sha256(u["data"]).hexdigest() != u["sha256"] or len(u["data"]) != u["size"]:
                return self.answer(422, {"error": "mismatch"})
            Server.files[u["name"]] = u["data"]
            return self.answer(200, {"file": {"name": u["name"], "size": u["size"], "sha256": u["sha256"]}})
        if self.path == "/api/os/publish/release":
            Server.releases.append(json.loads(self.body()))
            return self.answer(200, {"ok": True})
        self.answer(404, {})

    def do_PUT(self):
        if not self.authed():
            return
        m = re.fullmatch(r"/api/os/publish/upload/(\w+)\?offset=(\d+)", self.path)
        u, offset, chunk = Server.uploads[m.group(1)], int(m.group(2)), self.body()
        if offset != len(u["data"]):
            return self.answer(409, {"received": len(u["data"])})
        if offset > 0 and Server.nudge_once:
            # Pretend the first chunk landed twice: tell the client where we really are.
            Server.nudge_once = False
            return self.answer(409, {"received": len(u["data"])})
        u["data"] += chunk
        self.answer(200, {"received": len(u["data"]), "size": u["size"]})

    def log_message(self, *a):
        pass


class Publish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Server)
        cls.url = f"http://127.0.0.1:{cls.httpd.server_port}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def run_tool(self, *args, key=KEY):
        env = {**os.environ, "MIGOOD_PUBLISH_SERVER": self.url, "MIGOOD_OS_PUBLISH_KEY": key,
               "no_proxy": "127.0.0.1", "NO_PROXY": "127.0.0.1"}
        return subprocess.run(["python3", "tools/publish-os.py", *args], cwd=REPO, env=env,
                              capture_output=True, text=True, timeout=60)

    def test_upload_in_chunks_then_publish(self):
        with tempfile.TemporaryDirectory() as d:
            iso = os.path.join(d, "migood-os-9.9.9.iso")
            data = os.urandom(4500)  # 5 chunks of 1000
            with open(iso, "wb") as f:
                f.write(data)
            notes = os.path.join(d, "notes.md")
            with open(notes, "w") as f:
                f.write("Sleep & wake.")
            r = self.run_tool("--version", "9.9.9", "--notes-file", notes, "--app-version", "3.11.0", iso)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(Server.files["migood-os-9.9.9.iso"], data)
        rel = Server.releases[-1]
        self.assertEqual((rel["version"], rel["channel"], rel["notes"]), ("9.9.9", "beta", "Sleep & wake."))
        self.assertEqual(rel["files"], ["migood-os-9.9.9.iso"])
        self.assertEqual(rel["settings"]["appVersion"], "3.11.0")
        self.assertNotIn(KEY, r.stdout + r.stderr)
        self.assertTrue(Server.auth_ok)

    def test_no_key_no_upload(self):
        r = self.run_tool("--version", "9.9.8", "x.iso", key="")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("MIGOOD_OS_PUBLISH_KEY", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
