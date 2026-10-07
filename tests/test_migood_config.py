"""Tests for overlay/usr/lib/migood-os/migood-config (the parts that don't need root)."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "overlay", "usr", "lib", "migood-os")
sys.path.insert(0, LIB)


def load():
    loader = importlib.machinery.SourceFileLoader("migood_config", os.path.join(LIB, "migood-config"))
    spec = importlib.util.spec_from_loader("migood_config", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class MigoodConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conf = os.path.join(self.tmp, "update.conf")
        with open(self.conf, "w") as f:
            f.write("# comment\nSERVER=https://old.example\nCHANNEL=beta\n")
        os.environ.update(MIGOOD_CONF=self.conf, MIGOOD_STATE=self.tmp)
        self.mc = load()

    def read(self):
        with open(self.conf) as f:
            return f.read()

    def test_servers_replace_old_key_and_keep_others(self):
        self.mc.set_servers(["https://a.example", "https://b.example:3001/"])
        text = self.read()
        self.assertIn("SERVERS=https://a.example https://b.example:3001", text)
        self.assertNotIn("SERVER=", text.replace("SERVERS=", ""))
        self.assertIn("CHANNEL=beta", text)
        self.assertIn("# comment", text)

    def test_bad_server_refused(self):
        with self.assertRaises(SystemExit):
            self.mc.set_servers(["javascript:alert(1)"])
        self.assertIn("SERVER=https://old.example", self.read())

    def test_channel(self):
        self.mc.set_channel("stable")
        self.assertIn("CHANNEL=stable", self.read())
        self.assertEqual(self.read().count("CHANNEL="), 1)
        with self.assertRaises(SystemExit):
            self.mc.set_channel("nightly")

    def test_powerwash_is_only_scheduled(self):
        done = os.path.join(self.tmp, "setup-done")
        open(done, "w").close()
        self.mc.powerwash()
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "powerwash")))
        self.assertFalse(os.path.exists(done))  # so first-boot setup runs again


if __name__ == "__main__":
    unittest.main()
