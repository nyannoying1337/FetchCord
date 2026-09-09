"""Windows collection, with the registry and Win32 boundary faked.

The real values come from :mod:`fetch_cord.system.winapi`, which only works on
Windows. Faking that one layer lets the assembly logic - which is where the
bugs live - be tested anywhere.
"""

import unittest
from unittest import mock

from fetch_cord.system import info as info_module
from fetch_cord.system import winapi

# A Windows 11 laptop, as the registry actually reports it.
OS_VALUES = {
    "ProductName": "Windows 10 Pro",
    "DisplayVersion": "24H2",
    "CurrentBuild": "26100",
    "CurrentBuildNumber": "26100",
    "UBR": 4652,
    "CurrentMajorVersionNumber": 10,
    "CurrentMinorVersionNumber": 0,
    "EditionID": "Professional",
}

CPU_VALUES = {
    "ProcessorNameString": "Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz",
    "VendorIdentifier": "GenuineIntel",
    "~MHz": 2592,
}

BIOS_VALUES = {
    "SystemManufacturer": "ASUSTeK COMPUTER INC.",
    "SystemProductName": "TUF GAMING FX505DT",
    "BaseBoardManufacturer": "ASUSTeK COMPUTER INC.",
    "BaseBoardProduct": "FX505DT",
}


class CollectTestCase(unittest.TestCase):
    def collect(self, os_values=None, cpu_values=None, bios_values=None, gpus=None, mode=(1920, 1080, 144)):
        with mock.patch.object(winapi, "IS_WINDOWS", True), mock.patch.object(
            winapi, "os_version", return_value=OS_VALUES if os_values is None else os_values
        ), mock.patch.object(
            winapi, "cpu_info", return_value=CPU_VALUES if cpu_values is None else cpu_values
        ), mock.patch.object(
            winapi, "bios_info", return_value=BIOS_VALUES if bios_values is None else bios_values
        ), mock.patch.object(
            winapi, "gpu_names", return_value=["NVIDIA GeForce GTX 1650"] if gpus is None else gpus
        ), mock.patch.object(
            winapi, "screen_mode", return_value=mode
        ), mock.patch.object(
            info_module, "_collect_shell"
        ):
            return info_module.collect()


class TestCollectWindows(CollectTestCase):
    def test_os(self):
        info = self.collect()

        self.assertEqual(info.os_name, "Windows 11 Pro")
        self.assertEqual(info.os_key, "windows11")
        self.assertEqual(info.os_release, "24H2")
        self.assertEqual(info.build, "10.0.26100.4652")
        self.assertIn("Windows 11 Pro 24H2", info.os_line)

    def test_cpu(self):
        info = self.collect()

        self.assertEqual(info.cpu_model, "Intel Core i7-9750H")
        self.assertEqual(info.cpu_vendor, "intel")
        self.assertEqual(info.cpu_family, "intel i7")
        self.assertIn("@ 2.59GHz", info.cpu_line)

    def test_board(self):
        info = self.collect()

        self.assertEqual(info.host_line, "ASUSTeK COMPUTER INC. TUF GAMING FX505DT")
        self.assertEqual(info.board_line, "ASUSTeK COMPUTER INC. FX505DT")

    def test_oem_placeholders_are_dropped(self):
        info = self.collect(
            bios_values={
                "SystemManufacturer": "To Be Filled By O.E.M.",
                "SystemProductName": "Default string",
                "BaseBoardManufacturer": "ASRock",
                "BaseBoardProduct": "B450M PRO4",
            }
        )

        self.assertEqual(info.host_line, "N/A")
        self.assertEqual(info.board_line, "ASRock B450M PRO4")

    def test_display(self):
        info = self.collect()

        self.assertEqual(info.resolution_line, "1920x1080 @ 144Hz")

    def test_display_unavailable(self):
        info = self.collect(mode=None)

        self.assertEqual(info.resolution_line, "N/A")

    def test_gpus(self):
        info = self.collect(gpus=["Intel(R) UHD Graphics 630", "NVIDIA GeForce GTX 1650"])

        self.assertEqual(info.gpu_line, "Intel(R) UHD Graphics 630, NVIDIA GeForce GTX 1650")
        self.assertEqual(info.gpu_vendor_key, "intelnvidia")

    def test_empty_registry_does_not_crash(self):
        info = self.collect(os_values={}, cpu_values={}, bios_values={}, gpus=[], mode=None)

        self.assertEqual(info.os_key, "unknown")
        self.assertEqual(info.cpu_line, "N/A")
        self.assertEqual(info.gpu_line, "N/A")
        self.assertEqual(info.host_line, "N/A")

    def test_windows_10_is_not_relabelled(self):
        values = dict(OS_VALUES, ProductName="Windows 10 Home", CurrentBuild="19045", CurrentBuildNumber="19045")
        info = self.collect(os_values=values)

        self.assertEqual(info.os_name, "Windows 10 Home")
        self.assertEqual(info.os_key, "windows10")

    def test_non_numeric_build_is_survivable(self):
        values = dict(OS_VALUES, CurrentBuild="", CurrentBuildNumber="not a number")
        info = self.collect(os_values=values)

        self.assertEqual(info.os_key, "windows10")  # from ProductName
        self.assertEqual(info.build, "")


class TestPlatformGuards(unittest.TestCase):
    def test_winapi_helpers_refuse_to_run_off_windows(self):
        if winapi.IS_WINDOWS:  # pragma: no cover - only meaningful elsewhere
            self.skipTest("running on Windows")

        for helper in (winapi.gpu_names, winapi.screen_mode):
            with self.subTest(helper=helper.__name__):
                with self.assertRaises(winapi.UnsupportedPlatform):
                    helper()

    def test_startup_refuses_to_run_off_windows(self):
        if winapi.IS_WINDOWS:  # pragma: no cover
            self.skipTest("running on Windows")

        from fetch_cord import startup

        with self.assertRaises(winapi.UnsupportedPlatform):
            startup.status()

    def test_collect_matches_the_platform(self):
        """Real values on Windows, placeholders everywhere else."""
        info = info_module.collect()

        self.assertGreater(info.boot_time, 0)

        if winapi.IS_WINDOWS:
            self.assertNotEqual(info.cpu_line, "N/A")
            self.assertNotEqual(info.os_key, "unknown")
            self.assertGreater(info.memory_total, 0)
        else:
            self.assertEqual(info.cpu_line, "N/A")
            self.assertEqual(info.os_key, "unknown")


if __name__ == "__main__":
    unittest.main()
