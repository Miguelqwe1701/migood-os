"""migood-sleepd: the sleep & wake service, with a pretend PC and a pretend
Migood server. Every branch of the check-in from the design:
wake / touched / gone / nothing (back to sleep) / no network / crash."""
import http.server
import importlib.machinery
import importlib.util
import json
import os
import socket
import stat
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "overlay/usr/lib/migood-os")
TMP = tempfile.TemporaryDirectory()
os.environ["MIGOOD_STATE"] = TMP.name
os.environ["MIGOOD_SLEEPD_SOCK"] = os.path.join(TMP.name, "sleepd.sock")
os.environ["no_proxy"] = os.environ["NO_PROXY"] = "127.0.0.1"

loader = importlib.machinery.SourceFileLoader("sleepd", os.path.join(LIB, "migood-sleepd"))
spec = importlib.util.spec_from_loader("sleepd", loader)
sleepd = importlib.util.module_from_spec(spec)
loader.exec_module(sleepd)

TICKET = "t" * 48


class FakePC:
    """Records what the service asks the PC to do."""
    dry_run = False

    def __init__(self):
        self.calls = []
        self.online = True
        self.touched = False
        self.on_battery, self.percent = False, 80
        self.user = "kid"
        self.t = 1_000_000.0

    def now(self):
        return self.t

    def sleep(self, s):
        pass

    def set_alarm(self, when):
        self.calls.append(("alarm", int(when - self.t)))

    def clear_alarm(self):
        self.calls.append(("clear_alarm",))

    def suspend(self):
        self.calls.append(("suspend",))

    def screen(self, on):
        self.calls.append(("screen", on))

    def freeze(self):
        self.calls.append(("freeze",))

    def thaw(self):
        self.calls.append(("thaw",))

    def network_up(self, timeout):
        return self.online

    def wait_for_touch(self, timeout):
        self.calls.append(("wait", round(timeout)))
        return self.touched

    def battery(self):
        return self.on_battery, self.percent

    def toast(self, text):
        self.calls.append(("toast", text))


class Server(http.server.BaseHTTPRequestHandler):
    answer = {"wake": False, "every": 5}
    bodies = []

    def do_POST(self):
        Server.bodies.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        body = json.dumps(Server.answer).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class SleepdTest(unittest.TestCase):
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
        Server.answer, Server.bodies = {"wake": False, "every": 5}, []
        try:
            os.remove(sleepd.STATE)
        except FileNotFoundError:
            pass
        self.pc = FakePC()
        self.d = sleepd.Sleepd(self.pc, server=self.url)

    def start_sleeping(self, every=5):
        self.assertEqual(self.d.handle({"cmd": "sleep", "token": TICKET, "every": every}, 1000), {"ok": True})
        for _ in range(100):  # it sleeps on its own thread, after answering
            if ("suspend",) in self.pc.calls:
                break
            time.sleep(0.01)
        self.assertIn(("suspend",), self.pc.calls)
        self.pc.calls.clear()

    def alarm_wake(self):
        self.pc.t = self.d.state["alarm"] + 3  # resumed 3 s after the alarm
        self.d.on_resume()

    # --- going to sleep ---
    def test_sleep_saves_ticket_privately_and_sets_alarm(self):
        self.d.handle({"cmd": "sleep", "token": TICKET, "every": 5}, 1000)
        time.sleep(0.1)
        self.assertEqual(stat.S_IMODE(os.stat(sleepd.STATE).st_mode), 0o600)
        with open(sleepd.STATE) as f:
            self.assertEqual(json.load(f)["token"], TICKET)
        self.assertIn(("alarm", 300), self.pc.calls)

    def test_bad_requests(self):
        self.assertFalse(self.d.handle({"cmd": "sleep", "token": "x y"}, 1000)["ok"])
        self.assertFalse(self.d.handle({"cmd": "format-disk"}, 1000)["ok"])
        self.assertFalse(self.d.handle({"cmd": "resumed"}, 1000)["ok"])  # root only

    def test_status(self):
        s = self.d.handle({"cmd": "status"}, 1000)
        self.assertEqual((s["ok"], s["version"], s["sleeping"]), (True, 1, False))

    # --- the check-in ---
    def test_nothing_asked_goes_back_to_sleep_frozen(self):
        self.start_sleeping()
        self.alarm_wake()
        self.assertEqual(self.pc.calls[:2], [("screen", False), ("freeze",)])
        self.assertIn(("suspend",), self.pc.calls)
        self.assertNotIn(("thaw",), self.pc.calls)  # apps stay paused until a real wake
        self.assertEqual(Server.bodies, [{"token": TICKET}])
        self.assertEqual(self.d.state["last"]["result"], "asleep")

    def test_woken_from_phone(self):
        self.start_sleeping()
        Server.answer = {"wake": True}
        self.alarm_wake()
        self.assertIn(("thaw",), self.pc.calls)
        self.assertIn(("screen", True), self.pc.calls)
        self.assertIn(("toast", "Woken up from your phone"), self.pc.calls)
        self.assertEqual(Server.bodies[-1], {"token": TICKET, "up": True})
        self.assertNotIn(("suspend",), self.pc.calls)
        self.assertFalse(self.d.state.get("sleeping"))

    def test_someone_touched_it(self):
        self.start_sleeping()
        self.pc.touched = True
        self.alarm_wake()
        self.assertIn(("thaw",), self.pc.calls)
        self.assertEqual(Server.bodies[-1]["up"], True)
        self.assertEqual(self.d.state["last"]["result"], "touched")

    def test_forgotten_stops_sleeping(self):
        self.start_sleeping()
        Server.answer = {"gone": True}
        self.alarm_wake()
        self.assertIn(("thaw",), self.pc.calls)
        self.assertEqual(len(Server.bodies), 1)  # no "up" for a forgotten ticket
        self.assertNotIn(("suspend",), self.pc.calls)

    def test_no_network_tries_next_time(self):
        self.start_sleeping()
        self.pc.online = False
        self.alarm_wake()
        self.assertEqual(Server.bodies, [])
        self.assertIn(("suspend",), self.pc.calls)
        self.assertEqual(self.d.state["last"]["result"], "no-network")

    def test_power_button_is_a_real_wake(self):
        self.start_sleeping()
        self.pc.t = self.d.state["alarm"] - 120  # woke 2 min before the alarm
        self.d.on_resume()
        self.assertIn(("thaw",), self.pc.calls)
        self.assertNotIn(("freeze",), self.pc.calls)

    def test_crash_never_leaves_it_frozen(self):
        self.start_sleeping()
        self.pc.network_up = lambda t: 1 / 0
        self.alarm_wake()
        self.assertIn(("thaw",), self.pc.calls)
        self.assertIn(("screen", True), self.pc.calls)

    def test_every_from_server_is_used(self):
        self.start_sleeping()
        Server.answer = {"wake": False, "every": 10}
        self.alarm_wake()
        self.assertIn(("alarm", 600), self.pc.calls)

    # --- battery care ---
    def test_battery_checks_in_less_often(self):
        self.pc.on_battery, self.pc.percent = True, 60
        self.start_sleeping()
        self.assertEqual(self.d.state["alarm"] - int(self.pc.t), 15 * 60)

    def test_low_battery_stays_asleep(self):
        self.pc.on_battery, self.pc.percent = True, 10
        self.start_sleeping()
        self.assertNotIn("alarm", self.d.state)
        self.assertTrue(self.d.handle({"cmd": "status"}, 1000)["low_battery"])

    def test_cancel(self):
        self.start_sleeping()
        self.assertEqual(self.d.handle({"cmd": "cancel"}, 1000), {"ok": True})
        self.assertEqual(Server.bodies[-1], {"token": TICKET, "up": True})
        self.assertFalse(self.d.handle({"cmd": "status"}, 1000)["sleeping"])


class SocketTest(unittest.TestCase):
    """The real socket protocol: one JSON object per line."""

    def test_status_over_socket(self):
        d = sleepd.Sleepd(FakePC())
        threading.Thread(target=sleepd.serve, args=(d,), daemon=True).start()
        for _ in range(100):
            if os.path.exists(sleepd.SOCK):
                break
            time.sleep(0.02)
        s = socket.socket(socket.AF_UNIX)
        s.connect(sleepd.SOCK)
        with s:
            f = s.makefile("rwb")
            f.write(b'{"cmd":"status"}\n{"cmd":"nope"}\n')
            f.flush()
            first, second = json.loads(f.readline()), json.loads(f.readline())
        self.assertEqual((first["ok"], first["version"]), (True, 1))
        self.assertFalse(second["ok"])
        self.assertEqual(stat.S_IMODE(os.stat(sleepd.SOCK).st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
