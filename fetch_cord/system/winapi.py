"""Low level access to the Windows APIs FetchCord needs.

Everything in here is import-safe on other platforms: the module imports fine,
and each accessor raises :class:`UnsupportedPlatform` rather than exploding at
import time. That keeps the rest of the package unit-testable anywhere.
"""

import sys
from typing import Dict, List, Optional, Tuple

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    import winreg
    from ctypes import wintypes
else:  # pragma: no cover - exercised on Windows only
    ctypes = None
    winreg = None
    wintypes = None

# Registry locations we read from.
_CURRENT_VERSION = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
_BIOS = r"HARDWARE\DESCRIPTION\System\BIOS"
_CPU0 = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
_DISPLAY_CLASS = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"


# Always read the 64-bit view: a 32-bit Python would otherwise be redirected
# to WOW6432Node and see a different (or missing) ProductName.
_ACCESS = (winreg.KEY_READ | winreg.KEY_WOW64_64KEY) if IS_WINDOWS else 0


class UnsupportedPlatform(RuntimeError):
    """Raised when a Windows-only helper is called somewhere else."""


def _require_windows():
    if not IS_WINDOWS:
        raise UnsupportedPlatform("this helper is only available on Windows")


def read_value(path: str, name: str, root=None) -> Optional[str]:
    """Read a single registry value, or None if it isn't there.

    Missing keys and values are an expected outcome (hardware varies, values
    come and go between Windows releases), so they are reported as None rather
    than raised.
    """
    _require_windows()

    if root is None:
        root = winreg.HKEY_LOCAL_MACHINE

    try:
        with winreg.OpenKey(root, path, 0, _ACCESS) as key:
            value, _ = winreg.QueryValueEx(key, name)
    except OSError:
        return None

    return value


def read_key(path: str, root=None) -> Dict[str, object]:
    """Read every value of a registry key into a dict (empty if unreadable)."""
    _require_windows()

    if root is None:
        root = winreg.HKEY_LOCAL_MACHINE

    values: Dict[str, object] = {}
    try:
        with winreg.OpenKey(root, path, 0, _ACCESS) as key:
            count = winreg.QueryInfoKey(key)[1]
            for i in range(count):
                name, value, _ = winreg.EnumValue(key, i)
                values[name] = value
    except OSError:
        return {}

    return values


def os_version() -> Dict[str, object]:
    """Registry facts about the running Windows install."""
    return read_key(_CURRENT_VERSION)


def bios_info() -> Dict[str, object]:
    """Manufacturer/model strings for the system and its motherboard."""
    return read_key(_BIOS)


def cpu_info() -> Dict[str, object]:
    """Name, vendor and nominal clock of the first logical processor."""
    return read_key(_CPU0)


def gpu_names() -> List[str]:
    """Names of the installed display adapters, in enumeration order.

    Reads the display device class from the registry so we don't have to pay
    for a WMI/PowerShell round trip on every start.
    """
    _require_windows()

    names: List[str] = []
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, _DISPLAY_CLASS, 0, _ACCESS
        ) as parent:
            subkeys = winreg.QueryInfoKey(parent)[0]
            for i in range(subkeys):
                try:
                    subkey = winreg.EnumKey(parent, i)
                except OSError:
                    continue
                # Only the numbered instance keys (0000, 0001, ...) are adapters.
                if not subkey.isdigit():
                    continue
                desc = read_value("{}\\{}".format(_DISPLAY_CLASS, subkey), "DriverDesc")
                if isinstance(desc, str) and desc and desc not in names:
                    names.append(desc)
    except OSError:
        return []

    return names


def screen_mode() -> Optional[Tuple[int, int, int]]:
    """Current (width, height, refresh_hz) of the primary display.

    Uses EnumDisplaySettings so the result is the real pixel mode rather than
    a DPI-scaled approximation.
    """
    _require_windows()

    class DEVMODEW(ctypes.Structure):
        _fields_ = [
            ("dmDeviceName", wintypes.WCHAR * 32),
            ("dmSpecVersion", wintypes.WORD),
            ("dmDriverVersion", wintypes.WORD),
            ("dmSize", wintypes.WORD),
            ("dmDriverExtra", wintypes.WORD),
            ("dmFields", wintypes.DWORD),
            ("dmPositionX", wintypes.LONG),
            ("dmPositionY", wintypes.LONG),
            ("dmDisplayOrientation", wintypes.DWORD),
            ("dmDisplayFixedOutput", wintypes.DWORD),
            ("dmColor", wintypes.SHORT),
            ("dmDuplex", wintypes.SHORT),
            ("dmYResolution", wintypes.SHORT),
            ("dmTTOption", wintypes.SHORT),
            ("dmCollate", wintypes.SHORT),
            ("dmFormName", wintypes.WCHAR * 32),
            ("dmLogPixels", wintypes.WORD),
            ("dmBitsPerPel", wintypes.DWORD),
            ("dmPelsWidth", wintypes.DWORD),
            ("dmPelsHeight", wintypes.DWORD),
            ("dmDisplayFlags", wintypes.DWORD),
            ("dmDisplayFrequency", wintypes.DWORD),
            ("dmICMMethod", wintypes.DWORD),
            ("dmICMIntent", wintypes.DWORD),
            ("dmMediaType", wintypes.DWORD),
            ("dmDitherType", wintypes.DWORD),
            ("dmReserved1", wintypes.DWORD),
            ("dmReserved2", wintypes.DWORD),
            ("dmPanningWidth", wintypes.DWORD),
            ("dmPanningHeight", wintypes.DWORD),
        ]

    ENUM_CURRENT_SETTINGS = -1

    mode = DEVMODEW()
    mode.dmSize = ctypes.sizeof(DEVMODEW)

    if not ctypes.windll.user32.EnumDisplaySettingsW(
        None, ENUM_CURRENT_SETTINGS, ctypes.byref(mode)
    ):
        return None

    return (int(mode.dmPelsWidth), int(mode.dmPelsHeight), int(mode.dmDisplayFrequency))
