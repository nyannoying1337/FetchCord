"""Process matching, with psutil's process list faked."""

import unittest
from unittest import mock

import psutil

from fetch_cord.system import processes


class FakeProcess:
    def __init__(self, name, raises=None):
        self._name = name
        self._raises = raises

    @property
    def info(self):
        if self._raises:
            raise self._raises

        return {"name": self._name}


def running(*names):
    """Patch the process list with the given process names."""
    return mock.patch.object(
        psutil, "process_iter", return_value=[FakeProcess(n) for n in names]
    )


class TestFindRunning(unittest.TestCase):
    def test_exact_match(self):
        with running("systemd", "steam.exe", "chrome"):
            self.assertEqual(processes.find_running(["steam.exe"]), "steam.exe")

    def test_matching_is_case_insensitive(self):
        with running("Spotify.exe"):
            self.assertEqual(processes.find_running(["spotify.exe"]), "spotify.exe")

    def test_exe_suffix_is_optional_in_either_direction(self):
        """One config line should work on every platform."""
        with running("steam"):
            self.assertEqual(processes.find_running(["steam.exe"]), "steam.exe")

        with running("steam.exe"):
            self.assertEqual(processes.find_running(["steam"]), "steam")

    def test_returns_the_name_as_configured(self):
        with running("r5apex.exe"):
            self.assertEqual(processes.find_running([" R5Apex.exe "]), "R5Apex.exe")

    def test_no_match(self):
        with running("systemd", "bash"):
            self.assertIsNone(processes.find_running(["steam.exe"]))

    def test_empty_configuration_matches_nothing(self):
        with running("steam.exe"):
            self.assertIsNone(processes.find_running([]))
            self.assertIsNone(processes.find_running(["", "  "]))

    def test_a_process_that_exits_mid_scan_is_skipped(self):
        """psutil raises when a process goes away; the scan must continue."""
        listing = [
            FakeProcess("gone", raises=psutil.NoSuchProcess(1)),
            FakeProcess("steam.exe"),
        ]
        with mock.patch.object(psutil, "process_iter", return_value=listing):
            self.assertEqual(processes.find_running(["steam.exe"]), "steam.exe")

    def test_an_unreadable_process_list_is_not_fatal(self):
        with mock.patch.object(psutil, "process_iter", side_effect=OSError("denied")):
            self.assertIsNone(processes.find_running(["steam.exe"]))
            self.assertEqual(processes.running_names(), [])


class TestAnyRunning(unittest.TestCase):
    def test_matches_exactly_without_exe_juggling(self):
        with running("Xorg", "i3", "dunst"):
            self.assertEqual(processes.any_running(["sway", "i3", "dwm"]), "i3")

    def test_returns_candidates_in_priority_order(self):
        with running("i3", "dwm"):
            self.assertEqual(processes.any_running(["dwm", "i3"]), "dwm")

    def test_no_match(self):
        with running("Xorg"):
            self.assertIsNone(processes.any_running(["sway", "i3"]))


if __name__ == "__main__":
    unittest.main()
