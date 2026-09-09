import os
import tempfile
import unittest

from fetch_cord.config import (
    DEFAULT_CYCLE_TIME,
    DEFAULT_POLL_RATE,
    MIN_CYCLE_TIME,
    load_config,
    write_default_config,
)


def write(text: str) -> str:
    handle = tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False, encoding="utf-8")
    handle.write(text)
    handle.close()

    return handle.name


class TestLoadConfig(unittest.TestCase):
    def tearDown(self):
        for path in getattr(self, "_paths", []):
            os.unlink(path)

    def load(self, text: str):
        path = write(text)
        self._paths = getattr(self, "_paths", []) + [path]

        return load_config(path)

    def test_defaults_when_file_is_empty(self):
        config = self.load("")

        self.assertEqual(config.poll_rate, DEFAULT_POLL_RATE)
        self.assertEqual(config.cycles["os"].top_line, "kernel")
        self.assertEqual(config.cycles["os"].time, DEFAULT_CYCLE_TIME)
        self.assertTrue(config.cycles["hardware"].enabled)
        self.assertFalse(config.cycles["terminal"].enabled)
        self.assertEqual(config.warnings, [])

    def test_values_are_applied(self):
        config = self.load(
            "[general]\npoll_rate = 5\ntime = 45\n"
            "[os]\ntop_line = uptime\nbottom_line = disk\nsmall_icon = off\n"
            "[terminal]\nenabled = on\n"
        )

        self.assertEqual(config.poll_rate, 5)
        self.assertEqual(config.cycles["os"].top_line, "uptime")
        self.assertEqual(config.cycles["os"].bottom_line, "disk")
        self.assertFalse(config.cycles["os"].small_icon)
        self.assertEqual(config.cycles["os"].time, 45)
        self.assertTrue(config.cycles["terminal"].enabled)

    def test_per_cycle_time_overrides_general(self):
        config = self.load("[general]\ntime = 45\n[hardware]\ntime = 120\n")

        self.assertEqual(config.cycles["hardware"].time, 120)
        self.assertEqual(config.cycles["os"].time, 45)

    def test_invalid_line_falls_back_and_warns(self):
        """A typo must never stop FetchCord from starting."""
        config = self.load("[os]\ntop_line = bananas\n")

        self.assertEqual(config.cycles["os"].top_line, "kernel")
        self.assertTrue(any("bananas" in warning for warning in config.warnings))

    def test_invalid_booleans_and_times_fall_back(self):
        config = self.load(
            "[general]\npoll_rate = 0\n[os]\nenabled = maybe\ntime = 3\nsmall_icon = sure\n"
        )

        self.assertEqual(config.poll_rate, DEFAULT_POLL_RATE)
        self.assertTrue(config.cycles["os"].enabled)
        self.assertTrue(config.cycles["os"].small_icon)
        self.assertGreaterEqual(config.cycles["os"].time, MIN_CYCLE_TIME)
        self.assertEqual(len(config.warnings), 4)

    def test_unknown_section_is_reported_not_fatal(self):
        config = self.load("[cycle_9]\ntop_line = cpu\n")

        self.assertTrue(any("cycle_9" in warning for warning in config.warnings))
        self.assertTrue(config.cycles["os"].enabled)

    def test_missing_file_warns_and_uses_defaults(self):
        config = load_config("/nonexistent/fetch_cord.conf")

        self.assertEqual(config.poll_rate, DEFAULT_POLL_RATE)
        self.assertTrue(any("does not exist" in warning for warning in config.warnings))

    def test_unreadable_file_is_not_fatal(self):
        config = self.load("this is not = [ valid\n ini ] at all\n")

        self.assertEqual(config.poll_rate, DEFAULT_POLL_RATE)
        self.assertTrue(config.warnings)

    def test_enabled_cycles_keeps_display_order(self):
        config = self.load("[terminal]\nenabled = on\n[hardware]\nenabled = off\n")

        self.assertEqual([c.name for c in config.enabled_cycles()], ["os", "host", "terminal"])


class TestBundledConfig(unittest.TestCase):
    def test_shipped_config_is_valid(self):
        """The example config must parse with no warnings."""
        with tempfile.TemporaryDirectory() as directory:
            path = write_default_config(os.path.join(directory, "fetch_cord.conf"))
            config = load_config(path)

        self.assertEqual(config.warnings, [])
        self.assertEqual(config.poll_rate, DEFAULT_POLL_RATE)
        self.assertEqual([c.name for c in config.enabled_cycles()], ["os", "hardware", "host"])

    def test_write_default_config_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "fetch_cord.conf")
            write_default_config(path)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("[general]\npoll_rate = 9\n")

            write_default_config(path)
            config = load_config(path)

        self.assertEqual(config.poll_rate, 9)


if __name__ == "__main__":
    unittest.main()
