import unittest

from fetch_cord.system import naming


class TestCpuNaming(unittest.TestCase):
    """Raw registry CPU strings from real machines."""

    CASES = [
        ("Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz", "Intel Core i7-9750H", "intel i7", "intel"),
        ("Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz", "Intel Core i5-8250U", "intel i5", "intel"),
        ("12th Gen Intel(R) Core(TM) i9-12900K", "12th Gen Intel Core i9-12900K", "intel i9", "intel"),
        ("Intel(R) Core(TM) i3-4130 CPU @ 3.40GHz", "Intel Core i3-4130", "intel i3", "intel"),
        ("Intel(R) Pentium(R) CPU G4560 @ 3.50GHz", "Intel Pentium G4560", "intel pentium", "intel"),
        ("Intel(R) Celeron(R) N4020 CPU @ 1.10GHz", "Intel Celeron N4020", "intel celeron", "intel"),
        ("Intel(R) Xeon(R) CPU E5-2690 v4 @ 2.60GHz", "Intel Xeon E5-2690 v4", "intel xeon", "intel"),
        ("Intel(R) Core(TM)2 Duo CPU E8400 @ 3.00GHz", "Intel Core 2 Duo E8400", "intel core 2 duo", "intel"),
        ("Intel(R) Core(TM)2 Quad CPU Q6600 @ 2.40GHz", "Intel Core 2 Quad Q6600", "intel core 2 quad", "intel"),
        ("AMD Ryzen 7 5800X 8-Core Processor", "AMD Ryzen 7 5800X", "ryzen 7", "amd"),
        ("AMD Ryzen 5 5600G with Radeon Graphics", "AMD Ryzen 5 5600G", "ryzen 5", "amd"),
        ("AMD Ryzen 9 7950X 16-Core Processor", "AMD Ryzen 9 7950X", "ryzen 9", "amd"),
        ("AMD Ryzen 3 3200U with Radeon Vega Mobile Gfx", "AMD Ryzen 3 3200U", "ryzen 3", "amd"),
        ("AMD Ryzen Threadripper 3970X 32-Core Processor", "AMD Ryzen Threadripper 3970X", "ryzen threadripper", "amd"),
        ("AMD FX(tm)-8350 Eight-Core Processor", "AMD FX-8350", "fx apu", "amd"),
        ("AMD A10-9600P RADEON R5, 10 COMPUTE CORES 4C+6G", "AMD A10-9600P", "a10 apu", "amd"),
        ("AMD Athlon Silver 3050U with Radeon Graphics", "AMD Athlon Silver 3050U", "athlon silver", "amd"),
    ]

    def test_model_family_and_vendor(self):
        for raw, model, family, vendor in self.CASES:
            with self.subTest(raw=raw):
                self.assertEqual(naming.cpu_model(raw), model)
                self.assertEqual(naming.cpu_family(raw), family)
                self.assertEqual(naming.cpu_vendor(raw), vendor)

    def test_unmapped_cpu_has_no_family(self):
        """Core Ultra has no id yet: generic app, but the name still shows."""
        raw = "Intel(R) Core(TM) Ultra 7 155H"

        self.assertIsNone(naming.cpu_family(raw))
        self.assertEqual(naming.cpu_model(raw), "Intel Core Ultra 7 155H")

    def test_empty_input(self):
        self.assertEqual(naming.cpu_model(""), "")
        self.assertIsNone(naming.cpu_family(""))
        self.assertEqual(naming.cpu_vendor(""), "unknown")


class TestGpuNaming(unittest.TestCase):
    def test_single_vendors(self):
        cases = [
            ("NVIDIA GeForce RTX 4070", "nvidia"),
            ("AMD Radeon RX 6700 XT", "amd"),
            ("Radeon(TM) Graphics", "amd"),
            ("Intel(R) UHD Graphics 630", "intel"),
            ("Intel(R) Arc(TM) A770 Graphics", "intel"),
            ("VMware SVGA 3D", "vmware"),
            ("Red Hat VirtIO GPU", "virtio"),
        ]
        for raw, vendor in cases:
            with self.subTest(raw=raw):
                self.assertEqual(naming.gpu_vendor(raw), vendor)

    def test_non_gpu_adapters_are_ignored(self):
        self.assertIsNone(naming.gpu_vendor("Microsoft Basic Display Adapter"))
        self.assertEqual(
            naming.gpu_vendors(["Microsoft Basic Display Adapter", "NVIDIA GeForce GTX 1060"]),
            ["nvidia"],
        )

    def test_vendor_order_is_preserved_and_deduplicated(self):
        names = ["Intel(R) UHD Graphics", "NVIDIA GeForce RTX 3060", "Intel(R) UHD Graphics"]

        self.assertEqual(naming.gpu_vendors(names), ["intel", "nvidia"])


class TestWindowsNaming(unittest.TestCase):
    def test_build_number_beats_stale_product_name(self):
        """Windows 11 still reports "Windows 10 Pro" in the registry."""
        self.assertEqual(naming.windows_key("Windows 10 Pro", 22631), "windows11")
        self.assertEqual(naming.windows_name("Windows 10 Pro", 22631), "Windows 11 Pro")

    def test_older_releases(self):
        self.assertEqual(naming.windows_key("Windows 10 Home", 19045), "windows10")
        self.assertEqual(naming.windows_key("Windows 8.1 Pro", 9600), "windows8.1")
        self.assertEqual(naming.windows_key("Windows 8 Pro", 9200), "windows8")
        self.assertEqual(naming.windows_key("Windows 7 Ultimate", 7601), "windows7")

    def test_unknown_release(self):
        self.assertEqual(naming.windows_key("Windows Vista", 6002), "unknown")
        self.assertEqual(naming.windows_name("", 0), "Windows")

    def test_windows_10_name_is_left_alone(self):
        self.assertEqual(naming.windows_name("Windows 10 Pro", 19045), "Windows 10 Pro")


class TestFormatting(unittest.TestCase):
    def test_units(self):
        self.assertEqual(naming.format_bytes(8 * 1024**3), "8.00 GiB")
        self.assertEqual(naming.format_bytes(8 * 1024**3, "mb"), "8192 MiB")

    def test_clean_removes_trademarks_without_splitting_words(self):
        self.assertEqual(naming.clean("AMD FX(tm)-8350"), "AMD FX-8350")
        self.assertEqual(naming.clean("Intel(R)  Core(TM) i7"), "Intel Core i7")


if __name__ == "__main__":
    unittest.main()
