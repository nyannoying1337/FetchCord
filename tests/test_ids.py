import unittest

from fetch_cord.ids import IdTable, normalise_vendor

TABLE = {
    "map": {"CPU:": "cpu"},
    "distro": {"windows10": "10", "windows11": "11", "unknown": "?"},
    "cpu": {
        "amd": {"ryzen 7": "amd7"},
        "intel": {"intel i5": "intel5"},
        "unknown": "cpu?",
    },
    "gpu": {"nvidia": "nvidia", "amdintel": "amdintel", "unknown": "off"},
    "motherboard": {
        "asus": "asus-id",
        "asustek": "asus-id",
        "hp": "hp-id",
        "msi": "msi-id",
        "MS-7C02 1.0": "msi-id",
        "g3": "dell-id",
        "dell": "dell-id",
        "unknown": "board?",
    },
    "terminal": {"windows terminal": "wt-id", "unknown": "term?"},
    "shell": {"bash": "bash", "unknown": "unknown"},
}


class TestIdTable(unittest.TestCase):
    def setUp(self):
        self.ids = IdTable(TABLE)

    def test_os_lookup(self):
        self.assertEqual(self.ids.os_id("windows11"), "11")
        self.assertEqual(self.ids.os_id("windows95"), "?")

    def test_cpu_lookup_falls_back_to_generic(self):
        self.assertEqual(self.ids.cpu_id("amd", "ryzen 7"), "amd7")
        self.assertEqual(self.ids.cpu_id("intel", None), "cpu?")
        self.assertEqual(self.ids.cpu_id("amd", "ryzen 5"), "cpu?")
        self.assertEqual(self.ids.cpu_id("unknown", "ryzen 7"), "cpu?")

    def test_gpu_asset_none_when_no_icon(self):
        self.assertEqual(self.ids.gpu_asset("nvidia"), "nvidia")
        self.assertEqual(self.ids.gpu_asset("amdintel"), "amdintel")
        self.assertIsNone(self.ids.gpu_asset(""))
        self.assertIsNone(self.ids.gpu_asset("matrox"))

    def test_board_matches_longest_key(self):
        self.assertEqual(self.ids.board_key("ASUSTeK COMPUTER INC. TUF X570"), "asustek")
        self.assertEqual(self.ids.board_id("ASUSTeK COMPUTER INC. TUF X570"), "asus-id")

    def test_vendor_aliases(self):
        """MSI's firmware string never contains the word "MSI"."""
        board = "Micro-Star International Co., Ltd. MS-7C02"

        self.assertEqual(self.ids.board_key(board), "msi")
        self.assertEqual(self.ids.board_id(board), "msi-id")
        self.assertEqual(self.ids.board_asset(board), "msi")

    def test_model_specific_key_borrows_vendor_icon(self):
        self.assertEqual(self.ids.board_asset("Some Board MS-7C02 1.0"), "msi")

    def test_short_keys_need_word_boundaries(self):
        """"g3" must not match inside an unrelated model name."""
        self.assertIsNone(self.ids.board_key("Toshiba Satellite G3000X"))
        self.assertEqual(self.ids.board_key("Acme G3 3579"), "g3")
        # Longer keys win, and here both spellings point at the same vendor.
        self.assertEqual(self.ids.board_id("Dell Inc. G3 3579"), "dell-id")

    def test_unknown_board(self):
        self.assertIsNone(self.ids.board_key("Framework Laptop 13"))
        self.assertIsNone(self.ids.board_asset("Framework Laptop 13"))
        self.assertEqual(self.ids.board_id("Framework Laptop 13"), "board?")

    def test_terminal_and_shell(self):
        self.assertEqual(self.ids.terminal_id("Windows Terminal"), "wt-id")
        self.assertEqual(self.ids.terminal_id("Some Other Terminal"), "term?")
        self.assertEqual(self.ids.shell_asset("bash"), "bash")
        self.assertIsNone(self.ids.shell_asset("PowerShell 7"))

    def test_normalise_vendor(self):
        self.assertIn("msi", normalise_vendor("Micro-Star International Co., Ltd."))
        self.assertIn("gigabyte", normalise_vendor("Gigabyte Technology Co., Ltd."))


class TestBundledTable(unittest.TestCase):
    """The table shipped in the package must cover what Windows reports."""

    def setUp(self):
        self.ids = IdTable()

    def test_windows_versions_have_ids(self):
        for key in ("windows7", "windows8", "windows8.1", "windows10", "windows11"):
            with self.subTest(key=key):
                self.assertTrue(self.ids.os_id(key))
                self.assertNotEqual(self.ids.os_id(key), self.ids.os_id("nope"))

    def test_common_hardware_resolves(self):
        self.assertTrue(self.ids.cpu_id("amd", "ryzen 7"))
        self.assertTrue(self.ids.cpu_id("intel", "intel i7"))
        self.assertEqual(self.ids.gpu_asset("nvidia"), "nvidia")

    def test_real_firmware_strings(self):
        cases = {
            "ASUSTeK COMPUTER INC. TUF GAMING X570-PLUS": "asustek",
            "Micro-Star International Co., Ltd. MS-7C02": "msi",
            "HP HP Pavilion Laptop 15": "hp",
            "LENOVO ThinkPad T14": "thinkpad",
            "Dell Inc. OptiPlex 780": "dell",
            "Gigabyte Technology Co., Ltd. Z370XP SLI": "gigabyte",
        }
        for board, asset in cases.items():
            with self.subTest(board=board):
                self.assertEqual(self.ids.board_asset(board), asset)


if __name__ == "__main__":
    unittest.main()
