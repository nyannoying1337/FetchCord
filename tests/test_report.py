"""The --report-hardware output."""

import unittest

from fetch_cord.ids import IdTable
from fetch_cord.report import GENERIC, NOT_DETECTED, RESOLVED, build, unresolved
from fetch_cord.system.info import SystemInfo

from .test_info import sample


class TestKnownHardware(unittest.TestCase):
    """A machine whose parts all have applications."""

    def setUp(self):
        self.text, self.missing = build(sample())

    def test_nothing_needs_an_entry(self):
        self.assertEqual(self.missing, 0)
        self.assertIn("resolved to a specific application", self.text)
        self.assertNotIn(GENERIC, self.text)

    def test_raw_strings_are_included(self):
        """The raw string is what a maintainer needs to match against."""
        self.assertIn("AMD Ryzen 7 5800X 8-Core Processor", self.text)
        self.assertIn("NVIDIA GeForce RTX 4070", self.text)
        self.assertIn("ASUSTeK COMPUTER INC.", self.text)

    def test_matched_keys_are_shown(self):
        self.assertIn("ryzen 7", self.text)
        self.assertIn("windows11", self.text)

    def test_it_is_pasteable_markdown(self):
        self.assertIn("| Component | Detected | Matched key | Status |", self.text)
        self.assertIn("Paste this into a FetchCord issue", self.text)


class TestUnknownHardware(unittest.TestCase):
    def setUp(self):
        self.info = sample()
        self.info.cpu_name = "Whatever Ultra 9"
        self.info.cpu_model = "Whatever Ultra 9"
        self.info.cpu_vendor = "unknown"
        self.info.cpu_family = None
        self.info.gpus = ["Matrox G200eR2"]
        self.info.system_vendor = "Framework"
        self.info.system_model = "Laptop 13"
        self.info.board_vendor = "Framework"
        self.info.board_model = "FRANMZCP09"

    def test_each_unresolved_component_is_counted_and_flagged(self):
        text, missing = build(self.info)

        self.assertEqual(missing, 4)  # cpu, gpu, host, board
        self.assertIn(GENERIC, text)
        self.assertIn("4 component(s) fell back", text)

    def test_the_raw_strings_of_unknown_parts_are_reported(self):
        text, _ = build(self.info)

        self.assertIn("Whatever Ultra 9", text)
        self.assertIn("Matrox G200eR2", text)
        self.assertIn("Framework Laptop 13", text)

    def test_unresolved_lists_only_the_problems(self):
        rows = unresolved(self.info, IdTable())

        self.assertEqual(len(rows), 4)
        for row in rows:
            with self.subTest(row=row):
                self.assertIn(GENERIC, row)


class TestMissingHardware(unittest.TestCase):
    def test_undetected_parts_are_distinguished_from_unknown_ones(self):
        """Nothing to read is a different problem from nothing to match."""
        text, missing = build(SystemInfo())

        self.assertIn(NOT_DETECTED, text)
        # An absent component needs no id table entry.
        self.assertNotIn("GPU | -" + " | - | " + GENERIC, text)

    def test_a_bare_machine_does_not_crash_the_report(self):
        text, missing = build(SystemInfo())

        self.assertIn("| Component |", text)
        self.assertIsInstance(missing, int)


class TestOptionalSections(unittest.TestCase):
    def test_desktop_row_appears_only_when_detected(self):
        info = sample()
        self.assertNotIn("| Desktop |", build(info)[0])

        info.desktop = "KDE"
        text, _ = build(info)
        self.assertIn("| Desktop |", text)
        self.assertIn(RESOLVED, text)

    def test_terminal_row_appears_only_when_detected(self):
        info = sample()
        self.assertNotIn("| Terminal |", build(info)[0])

        info.terminal = "Windows Terminal"
        self.assertIn("| Terminal |", build(info)[0])


class TestGenericLookup(unittest.TestCase):
    def test_generic_returns_the_unknown_entry(self):
        ids = IdTable({"distro": {"a": "1", "unknown": "GEN"}, "cpu": {}})

        self.assertEqual(ids.generic("distro"), "GEN")
        self.assertEqual(ids.generic("cpu"), "")
        self.assertEqual(ids.generic("nope"), "")


if __name__ == "__main__":
    unittest.main()
