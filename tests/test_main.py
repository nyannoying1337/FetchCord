import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from fetch_cord import __main__ as entry

from .test_info import sample


def run(argv, windows=True):
    """Run main() with a fixed machine, capturing stdout."""
    out = io.StringIO()
    with mock.patch.object(entry, "IS_WINDOWS", windows), mock.patch.object(
        entry, "collect", return_value=sample()
    ), redirect_stdout(out):
        code = entry.main(argv)

    return code, out.getvalue()


class TestPlatformGuard(unittest.TestCase):
    def test_refuses_to_run_off_windows(self):
        code, output = run(["--dry-run"], windows=False)

        self.assertEqual(code, 1)
        self.assertIn("Windows only", output)

    def test_startup_flags_also_require_windows(self):
        code, output = run(["--startup-status"], windows=False)

        self.assertEqual(code, 1)
        self.assertIn("Windows only", output)


class TestDryRun(unittest.TestCase):
    def test_reports_detection_and_cycles_without_connecting(self):
        code, output = run(["--dry-run"])

        self.assertEqual(code, 0)
        self.assertIn("Windows 11 Pro 24H2 x86_64", output)
        self.assertIn("AMD Ryzen 7 5800X (16) @ 3.80GHz", output)
        self.assertIn("[os]", output)
        self.assertIn("[hardware]", output)
        self.assertIn("[host]", output)

    def test_legacy_flag_still_disables_the_os_cycle(self):
        code, output = run(["--dry-run", "--nodistro"])

        self.assertEqual(code, 0)
        self.assertNotIn("[os] application", output)
        self.assertIn("[hardware]", output)

    def test_with_terminal_enables_the_terminal_cycle(self):
        info = sample()
        info.terminal = "Windows Terminal"
        info.shell = "PowerShell 7"
        out = io.StringIO()
        with mock.patch.object(entry, "IS_WINDOWS", True), mock.patch.object(
            entry, "collect", return_value=info
        ), redirect_stdout(out):
            code = entry.main(["--dry-run", "--with-terminal"])

        self.assertEqual(code, 0)
        self.assertIn("[terminal]", out.getvalue())


class TestArgumentHandling(unittest.TestCase):
    def test_time_below_the_minimum_is_rejected(self):
        code, output = run(["--time", "5"])

        self.assertEqual(code, 1)
        self.assertIn("at least 15", output)

    def test_all_cycles_disabled_is_an_error(self):
        code, output = run(["--nodistro", "--nohardware", "--nohost"])

        self.assertEqual(code, 1)
        self.assertIn("every cycle is disabled", output)

    def test_runner_receives_command_line_overrides(self):
        with mock.patch.object(entry, "PresenceRunner") as runner:
            runner.return_value.run.return_value = 0
            code, _ = run(["--time", "45", "--poll-rate", "7", "-p", "-d"])

        self.assertEqual(code, 0)
        kwargs = runner.call_args.kwargs
        self.assertEqual(kwargs["time_override"], 45)
        self.assertEqual(kwargs["poll_rate"], 7)
        self.assertTrue(kwargs["pause"])
        self.assertTrue(kwargs["debug"])

    def test_memtype_changes_the_units(self):
        with mock.patch.object(entry, "collect") as collect:
            collect.return_value = sample()
            with mock.patch.object(entry, "IS_WINDOWS", True), redirect_stdout(io.StringIO()):
                entry.main(["--dry-run", "-m", "mb"])

        self.assertEqual(collect.call_args.kwargs["memory_unit"], "mb")

    def test_gen_config_writes_a_starter_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(os.environ, {"APPDATA": directory, "XDG_CONFIG_HOME": directory}):
                code, output = run(["--gen-config"])
                written = os.path.join(directory, "FetchCord", "fetch_cord.conf")

                self.assertEqual(code, 0)
                self.assertTrue(os.path.exists(written))
                self.assertIn("FetchCord", output)

    def test_config_warnings_are_shown_before_running(self):
        with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False, encoding="utf-8") as handle:
            handle.write("[os]\ntop_line = nonsense\n")
            path = handle.name

        try:
            code, output = run(["--dry-run", "--config", path])
        finally:
            os.unlink(path)

        self.assertEqual(code, 0)
        self.assertIn("nonsense", output)


if __name__ == "__main__":
    unittest.main()
