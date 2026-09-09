"""The Linux collector, driven against captured fixture trees.

Every reader takes a root path, so these run on any operating system - the
same trick the Windows tests use with a faked registry.
"""

import os
import unittest
from unittest import mock

from fetch_cord.cycles import build_payload
from fetch_cord.ids import IdTable
from fetch_cord.system import naming
from fetch_cord.system.info import SystemInfo
from fetch_cord.system.platforms import linux

from .test_cycles import cycle

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "linux")

# Real PCI device directories are named "0000:00:02.0", but a colon is not a
# legal filename character on Windows - git refuses to check the repository out
# at all. The fixtures use dashes instead; nothing reads the directory name.
WINDOWS_RESERVED = set('<>:"|?*')


def fixture(name: str) -> str:
    return os.path.join(FIXTURES, name)


def collect(name: str) -> SystemInfo:
    """Run the collector against a fixture, with the process walk stubbed out."""
    info = SystemInfo()
    with mock.patch.object(linux.shell, "detect", return_value=("", "bash")):
        linux.collect(info, root=fixture(name))

    return info


class TestUbuntuDesktop(unittest.TestCase):
    """Intel + NVIDIA desktop on an ASUS board, with pci.ids installed."""

    def setUp(self):
        self.info = collect("ubuntu-desktop")

    def test_distro(self):
        self.assertEqual(self.info.os_name, "Ubuntu")
        self.assertEqual(self.info.os_release, "24.04")
        self.assertEqual(self.info.os_key, "ubuntu")

    def test_distro_resolves_to_a_real_application(self):
        ids = IdTable()

        self.assertEqual(ids.os_id("ubuntu"), ids.os_id(self.info.os_key))
        self.assertNotEqual(ids.os_id(self.info.os_key), ids.os_id("nope"))

    def test_cpu(self):
        self.assertEqual(self.info.cpu_model, "Intel Core i7-9700K")
        self.assertEqual(self.info.cpu_family, "intel i7")
        self.assertEqual(self.info.cpu_vendor, "intel")
        # cpufreq wins over the "cpu MHz" line, which is the current speed.
        self.assertEqual(self.info.cpu_clock_mhz, 4900)

    def test_gpu_model_comes_from_pci_ids(self):
        self.assertEqual(self.info.gpus, ["NVIDIA GeForce RTX 3070"])
        self.assertEqual(self.info.gpu_vendor_key, "nvidia")

    def test_non_display_pci_devices_are_ignored(self):
        self.assertEqual(len(self.info.gpus), 1)

    def test_board_placeholders_are_dropped_and_the_board_is_used(self):
        # sys_vendor is real but product_name/version are OEM placeholders.
        self.assertEqual(self.info.system_vendor, "ASUS")
        self.assertEqual(self.info.system_model, "")
        self.assertEqual(self.info.host_line, "ASUSTeK COMPUTER INC. PRIME Z390-A")

    def test_resolution_uses_the_connected_display(self):
        self.assertEqual(self.info.resolution, "2560x1440")

    def test_not_a_laptop(self):
        self.assertFalse(self.info.laptop)
        self.assertEqual(self.info.chassis, "desktop")


class TestArchLaptop(unittest.TestCase):
    """AMD laptop with integrated Intel graphics and no pci.ids."""

    def setUp(self):
        self.info = collect("arch-laptop")

    def test_distro(self):
        self.assertEqual(self.info.os_key, "arch")

    def test_cpu(self):
        self.assertEqual(self.info.cpu_model, "AMD Ryzen 7 5800H")
        self.assertEqual(self.info.cpu_family, "ryzen 7")
        # No cpufreq file here, so the /proc/cpuinfo speed is used.
        self.assertEqual(self.info.cpu_clock_mhz, 3194)

    def test_gpus_fall_back_to_vendor_names(self):
        self.assertEqual(self.info.gpus, ["Intel", "AMD"])
        self.assertEqual(self.info.gpu_vendor_key, "intelamd")

    def test_gpu_combination_has_an_icon(self):
        self.assertEqual(IdTable().gpu_asset(self.info.gpu_vendor_key), "amdintel")

    def test_friendly_product_version_beats_the_machine_type(self):
        """ThinkPads put the recognisable name in product_version."""
        self.assertEqual(self.info.system_model, "ThinkPad T14 Gen 1")
        self.assertEqual(self.info.host_line, "LENOVO ThinkPad T14 Gen 1")

    def test_board_resolves_to_the_lenovo_application(self):
        ids = IdTable()

        self.assertEqual(ids.board_asset(self.info.host_line), "thinkpad")

    def test_battery_makes_it_a_laptop(self):
        self.assertTrue(self.info.laptop)
        self.assertEqual(self.info.chassis, "laptop")


class TestContainer(unittest.TestCase):
    """No DMI tables, no DRM connectors, no PCI - the degradation case."""

    def setUp(self):
        self.info = collect("container")

    def test_what_is_readable_is_read(self):
        self.assertEqual(self.info.os_key, "debian")
        self.assertEqual(self.info.cpu_model, "Intel Xeon")

    def test_missing_hardware_reads_na(self):
        for name in ("gpu", "host", "board", "resolution"):
            with self.subTest(name=name):
                self.assertEqual(self.info.line(name), "N/A")

    def test_host_cycle_is_skipped_entirely(self):
        """Nothing to say about the machine, so the cycle doesn't run."""
        self.assertIsNone(build_payload(cycle("host"), self.info, IdTable()))

    def test_os_cycle_still_works(self):
        payload = build_payload(cycle("os", top_line="kernel", bottom_line="memory"), self.info, IdTable())

        self.assertEqual(payload.client_id, IdTable().os_id("debian"))
        self.assertIsNone(payload.small_image)


class TestReaders(unittest.TestCase):
    def test_os_release_parsing_strips_quotes(self):
        values = linux.read_os_release(fixture("ubuntu-desktop"))

        self.assertEqual(values["PRETTY_NAME"], "Ubuntu 24.04.1 LTS")
        self.assertEqual(values["ID"], "ubuntu")
        self.assertEqual(values["ID_LIKE"], "debian")

    def test_cpuinfo_reads_only_the_first_processor(self):
        values = linux.read_cpuinfo(fixture("ubuntu-desktop"))

        self.assertEqual(values["vendor_id"], "GenuineIntel")
        self.assertIn("i7-9700K", values["model name"])

    def test_missing_files_are_not_an_error(self):
        self.assertEqual(linux.read_os_release("/nonexistent"), {})
        self.assertEqual(linux.read_cpuinfo("/nonexistent"), {})
        self.assertEqual(linux.read_dmi("/nonexistent"), {})
        self.assertEqual(linux.read_gpus("/nonexistent"), [])
        self.assertIsNone(linux.read_resolution("/nonexistent"))
        self.assertFalse(linux.is_laptop("/nonexistent"))


class TestFixtureLayout(unittest.TestCase):
    def test_fixture_paths_can_be_checked_out_on_windows(self):
        """A colon in a path makes the whole repo un-clonable on Windows."""
        for root, dirs, files in os.walk(FIXTURES):
            for entry in dirs + files:
                with self.subTest(entry=entry):
                    self.assertFalse(
                        WINDOWS_RESERVED & set(entry),
                        "{} contains a character Windows cannot check out".format(entry),
                    )


class TestDistroKeys(unittest.TestCase):
    def test_ids_that_match_the_table_directly(self):
        for distro in ("ubuntu", "debian", "arch", "fedora", "manjaro", "void"):
            with self.subTest(distro=distro):
                self.assertEqual(naming.linux_distro_key({"ID": distro}), distro)

    def test_ids_that_need_an_alias(self):
        cases = {
            "pop": "pop!_os",
            "opensuse-leap": "opensuseleap",
            "opensuse-tumbleweed": "opensusetumbleweed",
            "gentoo": "gentoo/linux",
            "arcolinux": "arco",
            "parrot": "parrotos",
            "amzn": "amazon",
        }
        for distro, key in cases.items():
            with self.subTest(distro=distro):
                self.assertEqual(naming.linux_distro_key({"ID": distro}), key)

    def test_unknown_derivative_falls_back_to_what_it_is_based_on(self):
        self.assertEqual(
            naming.linux_distro_key({"ID": "somethingnew", "ID_LIKE": "arch"}), "arch"
        )

    def test_name_is_the_last_resort(self):
        self.assertEqual(naming.linux_distro_key({"NAME": "Zorin OS"}), "zorin")

    def test_completely_unknown(self):
        self.assertEqual(naming.linux_distro_key({"ID": "nope", "ID_LIKE": "alsonope"}), "unknown")
        self.assertEqual(naming.linux_distro_key({}), "unknown")

    def test_every_key_naming_knows_exists_in_the_shipped_table(self):
        """Guards against naming.py drifting away from fetchcord_ids.json."""
        table = IdTable().data["distro"]

        for key in naming._DISTRO_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, table)


if __name__ == "__main__":
    unittest.main()
