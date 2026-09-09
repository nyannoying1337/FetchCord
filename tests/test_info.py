import time
import unittest

from fetch_cord.system.info import LINE_NAMES, UNKNOWN, SystemInfo, collect


def sample() -> SystemInfo:
    return SystemInfo(
        os_name="Windows 11 Pro",
        os_release="24H2",
        os_key="windows11",
        build="10.0.26100.4652",
        arch="x86_64",
        boot_time=time.time() - (3 * 3600 + 12 * 60),
        cpu_name="AMD Ryzen 7 5800X 8-Core Processor",
        cpu_model="AMD Ryzen 7 5800X",
        cpu_vendor="amd",
        cpu_family="ryzen 7",
        cpu_cores=16,
        cpu_clock_mhz=3800,
        gpus=["NVIDIA GeForce RTX 4070"],
        system_vendor="ASUSTeK COMPUTER INC.",
        system_model="ROG STRIX",
        board_vendor="ASUSTeK COMPUTER INC.",
        board_model="TUF GAMING X570-PLUS",
        memory_used=13 * 1024**3,
        memory_total=32 * 1024**3,
        disk_used=410 * 1024**3,
        disk_total=930 * 1024**3,
        resolution="2560x1440",
        refresh_rate=165,
    )


class TestDisplayLines(unittest.TestCase):
    def setUp(self):
        self.info = sample()

    def test_lines(self):
        self.assertEqual(self.info.os_line, "Windows 11 Pro 24H2 x86_64")
        self.assertEqual(self.info.kernel_line, "10.0.26100.4652")
        self.assertEqual(self.info.cpu_line, "AMD Ryzen 7 5800X (16) @ 3.80GHz")
        self.assertEqual(self.info.gpu_line, "NVIDIA GeForce RTX 4070")
        self.assertEqual(self.info.memory_line, "13.00 GiB / 32.00 GiB")
        self.assertEqual(self.info.disk_line, "410.00 GiB / 930.00 GiB (44%)")
        self.assertEqual(self.info.host_line, "ASUSTeK COMPUTER INC. ROG STRIX")
        self.assertEqual(self.info.board_line, "ASUSTeK COMPUTER INC. TUF GAMING X570-PLUS")
        self.assertEqual(self.info.resolution_line, "2560x1440 @ 165Hz")
        self.assertEqual(self.info.uptime_line, "3 hours, 12 mins")

    def test_memory_unit(self):
        self.info.memory_unit = "mb"

        self.assertEqual(self.info.memory_line, "13312 MiB / 32768 MiB")

    def test_missing_values_report_na(self):
        info = SystemInfo()

        for name in LINE_NAMES:
            with self.subTest(name=name):
                if name in ("os", "uptime"):
                    continue
                self.assertEqual(info.line(name), UNKNOWN)

    def test_board_falls_back_to_host(self):
        info = sample()
        info.board_vendor = ""
        info.board_model = ""

        self.assertEqual(info.board_line, info.host_line)

    def test_line_lookup_covers_every_configurable_name(self):
        for name in LINE_NAMES:
            with self.subTest(name=name):
                self.assertNotEqual(self.info.line(name), "")

        self.assertEqual(self.info.line("nonsense"), UNKNOWN)

    def test_battery_and_chassis(self):
        info = sample()
        self.assertEqual(info.battery_line, UNKNOWN)
        self.assertEqual(info.chassis, "desktop")

        info.battery_percent = 86.6
        info.battery_plugged = True
        info.laptop = True

        self.assertEqual(info.battery_line, "87% (charging)")
        self.assertEqual(info.chassis, "laptop")

    def test_gpu_vendor_key_combines_vendors(self):
        info = sample()
        info.gpus = ["Intel(R) UHD Graphics 630", "NVIDIA GeForce RTX 3060"]

        self.assertEqual(info.gpu_vendor_key, "intelnvidia")

    def test_uptime_formats(self):
        now = time.time()
        cases = [(30, "0 mins"), (60 * 5, "5 mins"), (3600 + 60, "1 hour, 1 min"), (86400 * 2 + 3600, "2 days, 1 hour, 0 mins")]
        for seconds, expected in cases:
            with self.subTest(seconds=seconds):
                self.assertEqual(SystemInfo(boot_time=now - seconds).uptime_line, expected)


class TestCollect(unittest.TestCase):
    def test_collect_never_raises(self):
        """Collection degrades to N/A rather than failing, whatever the host."""
        info = collect()

        self.assertIsInstance(info, SystemInfo)
        self.assertGreater(info.boot_time, 0)
        self.assertIsInstance(info.line("cpu"), str)

    def test_refresh_updates_volatile_values(self):
        info = collect()
        info.memory_used = 0
        info.refresh()

        self.assertGreater(info.memory_total, 0)


if __name__ == "__main__":
    unittest.main()
