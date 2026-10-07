"""migoodlib.diagnose: says why a Migood server can't be reached, in plain words."""
import http.server
import os
import socket
import ssl
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "overlay/usr/lib/migood-os"))
import migoodlib  # noqa: E402


class FakeServer(http.server.BaseHTTPRequestHandler):
    code = 401  # what /api/me answers; the tests change it

    def do_GET(self):
        self.send_response(FakeServer.code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"error":"Not logged in"}')

    def log_message(self, *args):
        pass


class Diagnose(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = http.server.HTTPServer(("127.0.0.1", 0), FakeServer)
        cls.url = f"http://127.0.0.1:{cls.httpd.server_port}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        # Talk to the fake server directly, never through a proxy.
        os.environ["no_proxy"] = os.environ["NO_PROXY"] = "127.0.0.1"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_signed_out_answer_means_ok(self):
        FakeServer.code = 401
        self.assertIsNone(migoodlib.diagnose(self.url))
        self.assertTrue(migoodlib.test_server(self.url))

    def test_cloudflare_block(self):
        FakeServer.code = 403
        self.assertIn("blocked", migoodlib.diagnose(self.url))
        self.assertFalse(migoodlib.test_server(self.url))

    def test_reasons(self):
        self.assertIn("server's name", migoodlib._why(socket.gaierror(-2, "Name not known")))
        self.assertIn("date and time", migoodlib._why(ssl.SSLCertVerificationError("expired")))
        self.assertIn("No answer in time", migoodlib._why(TimeoutError()))


if __name__ == "__main__":
    unittest.main()
