import unittest

from fetch_cord.config import CycleConfig, load_config
from fetch_cord.cycles import MAX_TEXT, build_payload, build_payloads, clamp
from fetch_cord.ids import IdTable

from .test_info import sample


def cycle(name, **overrides):
    defaults = dict(
        name=name, enabled=True, top_line="cpu", bottom_line="gpu", small_icon=True, time=30
    )
    defaults.update(overrides)

    return CycleConfig(**defaults)


class TestClamp(unittest.TestCase):
    def test_short_and_empty_text_is_dropped(self):
        """Discord rejects fields shorter than two characters."""
        self.assertIsNone(clamp(""))
        self.assertIsNone(clamp(None))
        self.assertIsNone(clamp("x"))
        self.assertIsNone(clamp("  "))

    def test_long_text_is_truncated(self):
        result = clamp("y" * 300)

        self.assertEqual(len(result), MAX_TEXT)
        self.assertTrue(result.endswith("…"))

    def test_normal_text_is_untouched(self):
        self.assertEqual(clamp("  Windows 11 Pro  "), "Windows 11 Pro")


class TestPayloads(unittest.TestCase):
    def setUp(self):
        self.info = sample()
        self.ids = IdTable()

    def test_os_cycle(self):
        payload = build_payload(cycle("os", top_line="kernel", bottom_line="memory"), self.info, self.ids)

        self.assertEqual(payload.client_id, self.ids.os_id("windows11"))
        self.assertEqual(payload.details, "10.0.26100.4652")
        self.assertEqual(payload.state, "13.00 GiB / 32.00 GiB")
        self.assertEqual(payload.large_image, "big")
        self.assertEqual(payload.large_text, "Windows 11 Pro 24H2 x86_64")
        self.assertEqual(payload.small_image, "asustek")

    def test_hardware_cycle_uses_cpu_application(self):
        payload = build_payload(cycle("hardware"), self.info, self.ids)

        self.assertEqual(payload.client_id, self.ids.cpu_id("amd", "ryzen 7"))
        self.assertEqual(payload.small_image, "nvidia")

    def test_host_cycle_shows_chassis(self):
        payload = build_payload(cycle("host", top_line="host", bottom_line="resolution"), self.info, self.ids)

        self.assertEqual(payload.small_image, "desktop")
        self.assertEqual(payload.state, "2560x1440 @ 165Hz")

    def test_small_icon_off_removes_icon_and_text(self):
        payload = build_payload(cycle("os", small_icon=False), self.info, self.ids)

        self.assertIsNone(payload.small_image)
        self.assertIsNone(payload.small_text)
        self.assertNotIn("small_image", payload.as_update())

    def test_start_is_an_integer_timestamp(self):
        payload = build_payload(cycle("os"), self.info, self.ids)

        self.assertIsInstance(payload.start, int)

    def test_as_update_omits_empty_fields(self):
        info = sample()
        info.gpus = []
        payload = build_payload(cycle("hardware", bottom_line="gpu"), info, self.ids)
        update = payload.as_update()

        self.assertIn("details", update)
        self.assertIsNone(update.get("small_image"))
        self.assertTrue(all(value is not None for value in update.values()))

    def test_cycles_with_nothing_to_show_are_skipped(self):
        info = sample()
        info.terminal = ""

        self.assertIsNone(build_payload(cycle("terminal"), info, self.ids))

        info.system_vendor = info.system_model = info.board_vendor = info.board_model = ""
        self.assertIsNone(build_payload(cycle("host"), info, self.ids))

    def test_unknown_cycle_name(self):
        self.assertIsNone(build_payload(cycle("nonsense"), self.info, self.ids))

    def test_build_payloads_uses_config_order(self):
        config = load_config()
        payloads = build_payloads(config.enabled_cycles(), self.info, self.ids)

        self.assertEqual([p.name for p in payloads], ["os", "hardware", "host"])
        for payload in payloads:
            with self.subTest(cycle=payload.name):
                self.assertTrue(payload.client_id)
                self.assertEqual(payload.seconds, 30)

    def test_terminal_cycle_when_detected(self):
        info = sample()
        info.terminal = "Windows Terminal"
        info.shell = "PowerShell 7"
        payload = build_payload(cycle("terminal", top_line="terminal", bottom_line="shell"), info, self.ids)

        self.assertEqual(payload.client_id, self.ids.terminal_id("Windows Terminal"))
        self.assertEqual(payload.state, "PowerShell 7")
        # There is no PowerShell icon in the asset table.
        self.assertIsNone(payload.small_image)


if __name__ == "__main__":
    unittest.main()
