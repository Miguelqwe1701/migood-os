"""homecore: Migood Home's backend (apps, recently played, battery, commands)."""
import json
import os
import shutil
import sys
import tempfile
import unittest

TMP = tempfile.mkdtemp()
APPS, ICONS, STATE, POWER = (os.path.join(TMP, d) for d in ("apps", "icons", "state", "power"))
os.environ.update(MIGOOD_APP_DIRS=APPS, MIGOOD_ICON_DIRS=ICONS, MIGOOD_HOME_STATE=STATE,
                  MIGOOD_POWER_SUPPLY=POWER)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "overlay/usr/lib/migood-os"))
import homecore  # noqa: E402


def desktop(name, **fields):
    body = "[Desktop Entry]\nType=Application\n" + "".join(f"{k}={v}\n" for k, v in fields.items())
    with open(os.path.join(APPS, name), "w") as f:
        f.write(body)


class HomeCore(unittest.TestCase):
    def setUp(self):
        for d in (APPS, ICONS, STATE, POWER):
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d)
        homecore._icon_cache.clear()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TMP, ignore_errors=True)

    def test_apps_listed_games_marked_migood_first(self):
        os.makedirs(os.path.join(ICONS, "128x128/apps"))
        open(os.path.join(ICONS, "128x128/apps/steam.png"), "w").close()
        desktop("steam.desktop", Name="Steam", Exec="steam", Icon="steam")
        desktop("org.gnome.Calculator.desktop", Name="Calculator", Exec="gnome-calculator")
        desktop("migood-games.desktop", Name="Migood Games", Exec="/opt/migood-games/migood-games")
        desktop("hidden.desktop", Name="Hidden", Exec="x", NoDisplay="true")
        desktop("gnome-control-center.desktop", Name="Settings", Exec="x")  # system clutter
        desktop("dolphin.desktop", Name="Dolphin", Exec="d", Categories="Game;Emulator;")
        got = homecore.apps()
        ids = [a["id"] for a in got]
        self.assertEqual(ids[:2], ["migood-games.desktop", "steam.desktop"])  # pinned order
        self.assertNotIn("hidden.desktop", ids)
        self.assertNotIn("gnome-control-center.desktop", ids)
        by = {a["id"]: a for a in got}
        self.assertTrue(by["dolphin.desktop"]["game"])
        self.assertFalse(by["org.gnome.Calculator.desktop"]["game"])
        self.assertTrue(by["steam.desktop"]["icon"].endswith("steam.png"))

    def test_app_path_refuses_anything_but_app_ids(self):
        desktop("steam.desktop", Name="Steam", Exec="steam")
        self.assertTrue(homecore.app_path("steam.desktop"))
        for bad in ("../../etc/passwd", "/bin/sh", "steam", "x.desktop; rm -rf /", None):
            self.assertIsNone(homecore.app_path(bad))

    def test_recent_newest_first_no_duplicates(self):
        homecore.remember_launch("a.desktop", now=1)
        homecore.remember_launch("b.desktop", now=2)
        homecore.remember_launch("a.desktop", now=3)
        self.assertEqual([r["id"] for r in homecore.recent()], ["a.desktop", "b.desktop"])

    def test_battery(self):
        os.makedirs(os.path.join(POWER, "BAT0"))
        for k, v in (("type", "Battery"), ("capacity", "42"), ("status", "Discharging")):
            open(os.path.join(POWER, "BAT0", k), "w").write(v + "\n")
        self.assertEqual(homecore.battery(), {"percent": 42, "charging": False})

    def test_nmcli_escaped_colons(self):
        self.assertEqual(homecore.parse_nmcli(r"*:Cafe\:Guest:70:WPA2"), ["*", "Cafe:Guest", "70", "WPA2"])

    def test_only_known_commands(self):
        self.assertIn("error", homecore.handle("rm", {"path": "/"}))
        self.assertIn("error", homecore.handle("power", {"action": "format"}))
        self.assertEqual(json.loads(json.dumps(homecore.handle("recent"))), [])


if __name__ == "__main__":
    unittest.main()
