"""Tests for overlay/usr/lib/migood-os/create-account (the parts that don't need root)."""
import importlib.machinery
import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HELPER = os.path.join(HERE, "..", "overlay", "usr", "lib", "migood-os", "create-account")


def load():
    loader = importlib.machinery.SourceFileLoader("create_account", HELPER)
    spec = importlib.util.spec_from_loader("create_account", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class CreateAccountTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["MIGOOD_GDM_CONF"] = os.path.join(self.tmp, "custom.conf")
        self.ca = load()

    def test_local_names_are_valid_linux_usernames(self):
        cases = {"Cool Kid_7": "cool-kid_7", "Miguelqwe170": "miguelqwe170",
                 "123abc": "m123abc", "MushY": "mushy", "a" * 40: "a" * 32}
        for migood, linux in cases.items():
            self.assertEqual(self.ca.local_name(migood), linux)

    def test_display_names_are_safe_for_passwd(self):
        self.assertEqual(self.ca.clean_name("Miguel 🎮"), "Miguel 🎮")
        self.assertEqual(self.ca.clean_name("a:b,c\nd"), "a b c d")
        self.assertEqual(self.ca.clean_name("   "), "Migood player")
        self.assertEqual(len(self.ca.clean_name("x" * 100)), 64)

    def test_login_screen_picture(self):
        os.environ["MIGOOD_AS_DIR"] = self.tmp
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
        self.ca.set_picture("miguelqwe170", png)
        with open(os.path.join(self.tmp, "icons", "miguelqwe170"), "rb") as f:
            self.assertEqual(f.read(), png)
        with open(os.path.join(self.tmp, "users", "miguelqwe170")) as f:
            self.assertIn("Icon=" + os.path.join(self.tmp, "icons", "miguelqwe170"), f.read())
        self.ca.set_picture("evil", b"<html>not a png")  # ignored
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "icons", "evil")))

    def test_autologin_on_then_off_keeps_other_settings(self):
        conf = os.environ["MIGOOD_GDM_CONF"]
        with open(conf, "w") as f:
            f.write("[daemon]\nWaylandEnable=false\n\n[security]\n")
        self.ca.set_autologin("migood-setup")
        text = open(conf).read()
        self.assertIn("AutomaticLoginEnable=true\nAutomaticLogin=migood-setup", text)
        self.assertIn("WaylandEnable=false", text)
        self.ca.set_autologin(None)
        text = open(conf).read()
        self.assertNotIn("AutomaticLogin", text)
        self.assertIn("WaylandEnable=false", text)
        self.assertIn("[security]", text)


if __name__ == "__main__":
    unittest.main()
