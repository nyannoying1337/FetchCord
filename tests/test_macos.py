"""The macOS collector, with sysctl and CoreGraphics faked.

Those two are the only things the collector cannot get from the standard
library, so stubbing them lets the rest be tested on any machine - the same
boundary trick used for the Windows registry and the Linux sysfs trees.
"""

import unittest
from unittest import mock

from fetch_cord.cycles import build_payload
from fetch_cord.ids import IdTable
from fetch_cord.system import naming
from fetch_cord.system.info import SystemInfo
from fetch_cord.system.platforms import macos

from .test_cycles import cycle

# A MacBook Pro on Apple Silicon, as sysctl reports it.
APPLE_SILICON = {
    "hw.model": "MacBookPro18,3",
    "machdep.cpu.brand_string": "Apple M1 Pro",
}

# An older Intel MacBook Pro, which also publishes a clock.
INTEL = {
    "hw.model": "MacBookPro15,2",
    "machdep.cpu.brand_string": "Intel(R) Core(TM) i5-8259U CPU @ 2.30GHz",
    "hw.cpufrequency_max": "2300000000",
}


def collect(values, version="14.5", machine="arm64", mode=(3024, 1964)):
    info = SystemInfo()
    with mock.patch.object(macos, "sysctl", return_value=values), mock.patch.object(
        macos, "screen_mode", return_value=mode
    ), mock.patch.object(
        macos.platform, "mac_ver", return_value=(version, ("", "", ""), machine)
    ), mock.patch.object(
        macos.platform, "machine", return_value=machine
    ), mock.patch.object(
        macos.shell, "detect", return_value=("apple_terminal", "zsh")
    ):
        macos.collect(info)

    return info


class TestAppleSilicon(unittest.TestCase):
    def setUp(self):
        self.info = collect(APPLE_SILICON)

    def test_release_name(self):
        self.assertEqual(self.info.os_name, "macOS Sonoma")
        self.assertEqual(self.info.os_release, "14.5")
        self.assertEqual(self.info.os_line, "macOS Sonoma 14.5 arm64")

    def test_cpu(self):
        self.assertEqual(self.info.cpu_model, "Apple M1 Pro")
        self.assertEqual(self.info.cpu_vendor, "apple")
        self.assertEqual(self.info.cpu_family, "m1 pro")

    def test_no_clock_is_reported_for_apple_silicon(self):
        """Apple Silicon doesn't publish hw.cpufrequency_max."""
        self.assertEqual(self.info.cpu_clock_mhz, 0)
        self.assertNotIn("GHz", self.info.cpu_line)

    def test_gpu_comes_from_the_chip(self):
        self.assertEqual(self.info.gpus, ["Apple M1 Pro GPU"])

    def test_host_and_board(self):
        self.assertEqual(self.info.host_line, "Apple MacBookPro18,3")
        self.assertEqual(self.info.board_line, "Apple MacBookPro18,3")

    def test_board_resolves_to_the_macbook_pro_application(self):
        ids = IdTable()

        self.assertEqual(ids.board_asset(self.info.host_line), "macbookpro")
        self.assertNotEqual(ids.board_id(self.info.host_line), ids.board_id("Nothing"))

    def test_retina_resolution_is_in_pixels(self):
        self.assertEqual(self.info.resolution_line, "3024x1964")


class TestIntelMac(unittest.TestCase):
    def setUp(self):
        self.info = collect(INTEL, version="12.7.6", machine="x86_64")

    def test_release_name(self):
        self.assertEqual(self.info.os_name, "macOS Monterey")

    def test_cpu_uses_the_shared_intel_normalisation(self):
        self.assertEqual(self.info.cpu_model, "Intel Core i5-8259U")
        self.assertEqual(self.info.cpu_family, "intel i5")
        self.assertEqual(self.info.cpu_clock_mhz, 2300)

    def test_intel_cpu_resolves_to_an_existing_application(self):
        ids = IdTable()

        self.assertEqual(
            ids.cpu_id(self.info.cpu_vendor, self.info.cpu_family),
            ids.cpu_id("intel", "intel i5"),
        )
        self.assertNotEqual(
            ids.cpu_id(self.info.cpu_vendor, self.info.cpu_family), ids.cpu_id("intel", None)
        )

    def test_gpu_is_left_unknown_on_intel(self):
        """Intel Mac GPUs would need system_profiler, which is too slow."""
        self.assertEqual(self.info.gpus, [])
        self.assertEqual(self.info.gpu_line, "N/A")


class TestDegradation(unittest.TestCase):
    def test_no_sysctl_and_no_display(self):
        info = collect({}, mode=None)

        self.assertEqual(info.cpu_line, "N/A")
        self.assertEqual(info.host_line, "N/A")
        self.assertEqual(info.resolution_line, "N/A")
        # The release still comes from the standard library.
        self.assertEqual(info.os_name, "macOS Sonoma")

    def test_host_cycle_is_skipped_without_a_model(self):
        info = collect({}, mode=None)

        self.assertIsNone(build_payload(cycle("host"), info, IdTable()))

    def test_sysctl_survives_a_missing_binary(self):
        with mock.patch.object(macos.subprocess, "run", side_effect=OSError("no sysctl")):
            self.assertEqual(macos.sysctl("hw.model"), {})

    def test_screen_mode_survives_a_missing_framework(self):
        with mock.patch.object(macos.ctypes.util, "find_library", return_value=None):
            self.assertIsNone(macos.screen_mode())


class TestSysctlParsing(unittest.TestCase):
    def test_values_are_keyed_by_name(self):
        """Querying without -n keeps a missing key from shifting the rest."""
        output = "hw.model: MacBookPro18,3\nmachdep.cpu.brand_string: Apple M1 Pro\n"
        with mock.patch.object(macos.subprocess, "run") as run:
            run.return_value = mock.Mock(stdout=output)
            values = macos.sysctl("hw.model", "machdep.cpu.brand_string", "hw.cpufrequency_max")

        self.assertEqual(values["hw.model"], "MacBookPro18,3")
        self.assertEqual(values["machdep.cpu.brand_string"], "Apple M1 Pro")
        self.assertNotIn("hw.cpufrequency_max", values)


class TestReleaseNames(unittest.TestCase):
    def test_known_releases(self):
        cases = {
            "10.13.6": "macOS High Sierra",
            "10.15.7": "macOS Catalina",
            "11.7.10": "macOS Big Sur",
            "12.7.6": "macOS Monterey",
            "13.6.9": "macOS Ventura",
            "14.5": "macOS Sonoma",
            "15.1": "macOS Sequoia",
            "26.0": "macOS Tahoe",
        }
        for version, name in cases.items():
            with self.subTest(version=version):
                self.assertEqual(naming.macos_name(version), name)

    def test_unknown_release_still_names_the_os(self):
        self.assertEqual(naming.macos_name("99.0"), "macOS")
        self.assertEqual(naming.macos_name(""), "macOS")

    def test_every_release_name_matches_the_shipped_table(self):
        """naming.py and fetchcord_ids.json must not drift apart."""
        table = IdTable().data["version"]

        for key, codename in naming._MACOS_CODENAMES.items():
            with self.subTest(key=key):
                self.assertEqual(table.get(key), codename)


class TestAppleChipLookup(unittest.TestCase):
    def test_variant_falls_back_to_the_base_chip(self):
        table = IdTable({"cpu": {"apple": {"m4": "BASE"}, "unknown": "GENERIC"}})

        self.assertEqual(table.cpu_id("apple", "m4 max"), "BASE")
        self.assertEqual(table.cpu_id("apple", "m4"), "BASE")

    def test_exact_variant_wins_when_it_exists(self):
        table = IdTable({"cpu": {"apple": {"m1": "BASE", "m1 pro": "PRO"}, "unknown": "GENERIC"}})

        self.assertEqual(table.cpu_id("apple", "m1 pro"), "PRO")

    def test_unlisted_chip_is_generic(self):
        """Until the applications exist, Apple Silicon uses the generic app."""
        self.assertEqual(IdTable().cpu_id("apple", "m4"), IdTable().cpu_id("apple", None))

    def test_chip_families(self):
        for brand, family in [
            ("Apple M1", "m1"),
            ("Apple M1 Pro", "m1 pro"),
            ("Apple M2 Max", "m2 max"),
            ("Apple M3 Ultra", "m3 ultra"),
            ("Apple M4", "m4"),
        ]:
            with self.subTest(brand=brand):
                self.assertEqual(naming.cpu_family(brand), family)


if __name__ == "__main__":
    unittest.main()
