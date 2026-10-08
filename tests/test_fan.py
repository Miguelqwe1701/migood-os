"""migood-fan (quiet fans) against a pretend /sys and /proc."""
import importlib.machinery
import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "overlay/usr/lib/migood-os/migood-fan")


def load():
    loader = importlib.machinery.SourceFileLoader("migood_fan", SCRIPT)
    spec = importlib.util.spec_from_loader("migood_fan", loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


class Fan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        os.environ.update(MIGOOD_SYSFS=os.path.join(t, "sys"), MIGOOD_PROCFS=os.path.join(t, "proc"),
                          MIGOOD_FAN_CONF=os.path.join(t, "fan.conf"),
                          MIGOOD_FAN_HOLD=os.path.join(t, "hold"), MIGOOD_NO_PPD="1")
        self.put("sys/firmware/acpi/platform_profile", "performance")
        self.put("sys/firmware/acpi/platform_profile_choices", "low-power balanced performance")
        self.put("sys/devices/system/cpu/intel_pstate/no_turbo", "0")
        pol = "sys/devices/system/cpu/cpufreq/policy0/"
        self.put(pol + "energy_performance_available_preferences",
                 "default performance balance_performance balance_power power")
        self.put(pol + "energy_performance_preference", "performance")
        self.m = load()

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, rel, text):
        p = os.path.join(self.tmp.name, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)

    def get(self, rel):
        with open(os.path.join(self.tmp.name, rel)) as f:
            return f.read()

    def test_quiet(self):
        self.m.apply("quiet")
        self.assertEqual(self.get("sys/firmware/acpi/platform_profile"), "low-power")
        self.assertEqual(self.get("sys/devices/system/cpu/intel_pstate/no_turbo"), "1")
        self.assertEqual(self.get("sys/devices/system/cpu/cpufreq/policy0/energy_performance_preference"),
                         "power")

    def test_balanced_turns_turbo_back_on(self):
        self.m.apply("quiet")
        self.m.apply("balanced")
        self.assertEqual(self.get("sys/firmware/acpi/platform_profile"), "balanced")
        self.assertEqual(self.get("sys/devices/system/cpu/intel_pstate/no_turbo"), "0")

    def test_old_asus_without_platform_profile(self):
        os.remove(os.path.join(self.tmp.name, "sys/firmware/acpi/platform_profile_choices"))
        self.put("sys/devices/platform/asus-nb-wmi/throttle_thermal_policy", "1")
        self.m.apply("quiet")
        self.assertEqual(self.get("sys/devices/platform/asus-nb-wmi/throttle_thermal_policy"), "2")

    def test_pc_with_nothing_to_change_is_fine(self):
        self.tmp.cleanup()
        self.assertEqual(self.m.apply("quiet"), [])

    def test_auto_waits_before_switching(self):
        a = self.m.Auto()
        self.assertEqual(a.feed(1.0), "quiet")  # one spike: stay quiet
        a.feed(1.0)
        self.assertEqual(a.feed(1.0), "balanced")  # busy for ~9 s: a game
        for _ in range(9):
            self.assertEqual(a.feed(0.05), "balanced")
        self.assertEqual(a.feed(0.05), "quiet")  # calm for ~30 s

    def test_busiest_core_not_average(self):
        before = {"cpu0": (0, 100), "cpu1": (0, 100)}
        after = {"cpu0": (95, 200), "cpu1": (0, 200)}  # one core maxed, one idle
        self.assertAlmostEqual(self.m.busiest_core(before, after), 0.95)

    def test_installer_hold_wins_over_settings(self):
        self.put("fan.conf", "MODE=performance\n")
        self.assertEqual(self.m.conf_mode(), "performance")
        self.put("hold", "quiet\n")
        self.assertEqual(self.m.held() or self.m.conf_mode(), "quiet")


if __name__ == "__main__":
    unittest.main()

