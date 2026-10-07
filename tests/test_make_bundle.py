"""tools/make-bundle.sh: build the real 0.1.0 -> 0.1.1 bundle, then install it
into a pretend computer (a temporary folder) with its own apply.sh."""
import os
import stat
import subprocess
import tarfile
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def have_tags():
    return all(subprocess.run(["git", "rev-parse", "-q", "--verify", f"{t}^{{commit}}"],
                              cwd=REPO, capture_output=True).returncode == 0
               for t in ("v0.1.0", "v0.1.1"))


@unittest.skipUnless(have_tags(), "needs git tags v0.1.0 and v0.1.1 (git fetch --tags)")
class MakeBundle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = os.path.join(self.tmp.name, "out")
        subprocess.run(["bash", "tools/make-bundle.sh", "0.1.0", "0.1.1"], cwd=REPO, check=True,
                       env={**os.environ, "OUT": self.out}, stdout=subprocess.DEVNULL)
        self.bundle = os.path.join(self.out, "migood-os-0.1.1-update.tar.gz")

    def tearDown(self):
        self.tmp.cleanup()

    def test_contents(self):
        with tarfile.open(self.bundle) as tar:
            names = {n.lstrip("./") for n in tar.getnames()}
        self.assertIn("apply.sh", names)
        self.assertIn("extra.sh", names)
        self.assertIn("files/etc/netplan/01-network-manager-all.yaml", names)
        self.assertIn("files/usr/lib/migood-os/create-account", names)
        # Only what changed: files from 0.1.0 that 0.1.1 didn't touch stay out.
        self.assertNotIn("files/usr/lib/migood-os/update", names)
        self.assertTrue(os.path.exists(self.bundle + ".sha256"))

    def test_apply_into_pretend_computer(self):
        unpacked = os.path.join(self.tmp.name, "unpacked")
        root = os.path.join(self.tmp.name, "root")
        os.makedirs(os.path.join(root, "etc/gdm3"))
        with open(os.path.join(root, "etc/gdm3/custom.conf"), "w") as f:
            f.write("[daemon]\n# AutomaticLoginEnable = true\n")
        with tarfile.open(self.bundle) as tar:
            tar.extractall(unpacked, filter="data")
        # The same way the updater runs it: bash apply.sh, in the unpacked folder.
        subprocess.run(["bash", "apply.sh"], cwd=unpacked, check=True,
                       env={**os.environ, "MIGOOD_ROOT": root})
        account = os.path.join(root, "usr/lib/migood-os/create-account")
        self.assertTrue(os.stat(account).st_mode & stat.S_IXUSR, "create-account must stay runnable")
        self.assertTrue(os.path.exists(os.path.join(root, "etc/netplan/01-network-manager-all.yaml")))
        with open(os.path.join(root, "etc/gdm3/custom.conf")) as f:
            self.assertIn("InitialSetupEnable=false", f.read())


@unittest.skipUnless(have_tags() and subprocess.run(
    ["git", "rev-parse", "-q", "--verify", "v0.1.2^{commit}"], cwd=REPO,
    capture_output=True).returncode == 0, "needs git tag v0.1.2")
class BuildChangeWarning(unittest.TestCase):
    """0.1.2 changed customize.sh with no bundles/0.1.2/extra.sh: warn.
    0.1.1 has its extra.sh: no warning."""

    def run_bundle(self, old, new):
        with tempfile.TemporaryDirectory() as out:
            return subprocess.run(["bash", "tools/make-bundle.sh", old, new], cwd=REPO, check=True,
                                  env={**os.environ, "OUT": out}, capture_output=True, text=True).stdout

    def test_warns_without_extra(self):
        self.assertIn("WARNING", self.run_bundle("0.1.1", "0.1.2"))

    def test_quiet_with_extra(self):
        self.assertNotIn("WARNING", self.run_bundle("0.1.0", "0.1.1"))


if __name__ == "__main__":
    unittest.main()
