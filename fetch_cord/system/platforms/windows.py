"""Low level access to the Windows APIs FetchCord needs.

Everything in here is import-safe on other platforms: the module imports fine,
and each accessor raises :class:`UnsupportedPlatform` rather than exploding at
import time. That keeps the rest of the package unit-testable anywhere.
"""

import os
import platform
import sys
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import psutil

from .. import naming, shell

if TYPE_CHECKING:  # pragma: no cover
    from ..info import SystemInfo

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


# Executable names we recognise when walking up the process tree.
_TERMINALS = {
    "windowsterminal.exe": "Windows Terminal",
    "conemu64.exe": "ConEmu",
    "conemu.exe": "ConEmu",
    "cmder.exe": "Cmder",
    "alacritty.exe": "Alacritty",
    "wezterm-gui.exe": "WezTerm",
    "hyper.exe": "Hyper",
    "code.exe": "Visual Studio Code",
    "explorer.exe": "",  # launched from the shell: no terminal at all
}

_SHELLS = {
    "powershell.exe": "PowerShell",
    "pwsh.exe": "PowerShell 7",
    "cmd.exe": "Command Prompt",
    "bash.exe": "bash",
    "nu.exe": "Nushell",
}

_NOT_A_TERMINAL = {"conhost.exe", "openconsole.exe", "python.exe", "pythonw.exe", "py.exe"}


def _collect_os(info: "SystemInfo"):
    values = os_version()

    build_number = 0
    for key in ("CurrentBuildNumber", "CurrentBuild"):
        try:
            build_number = int(values.get(key, 0))
        except (TypeError, ValueError):
            continue
        if build_number:
            break

    product_name = str(values.get("ProductName", "") or "")
    info.os_name = naming.windows_name(product_name, build_number)
    info.os_key = naming.windows_key(product_name, build_number)
    info.os_release = str(values.get("DisplayVersion") or values.get("ReleaseId") or "")

    revision = values.get("UBR")
    major = str(values.get("CurrentMajorVersionNumber", 10))
    minor = str(values.get("CurrentMinorVersionNumber", 0))
    if build_number:
        info.build = "{}.{}.{}".format(major, minor, build_number)
        if isinstance(revision, int):
            info.build += ".{}".format(revision)

    machine = platform.machine()
    info.arch = {"AMD64": "x86_64", "ARM64": "aarch64"}.get(machine, machine)


def _collect_cpu(info: "SystemInfo"):
    values = cpu_info()

    info.cpu_name = str(values.get("ProcessorNameString", "") or "")
    info.cpu_model = naming.cpu_model(info.cpu_name)
    info.cpu_vendor = naming.cpu_vendor(
        info.cpu_name or str(values.get("VendorIdentifier", "") or "")
    )
    info.cpu_family = naming.cpu_family(info.cpu_name)

    clock = values.get("~MHz")
    if isinstance(clock, int):
        info.cpu_clock_mhz = clock

    try:
        info.cpu_cores = psutil.cpu_count(logical=True) or 0
    except Exception:
        info.cpu_cores = 0


def _collect_board(info: "SystemInfo"):
    values = bios_info()

    def text(key: str) -> str:
        value = values.get(key)
        if not isinstance(value, str):
            return ""
        value = value.strip()
        # OEMs love leaving these placeholders in the firmware.
        if value.lower() in ("", "to be filled by o.e.m.", "default string", "system product name", "system manufacturer"):
            return ""

        return value

    info.system_vendor = text("SystemManufacturer")
    info.system_model = text("SystemProductName") or text("SystemFamily")
    info.board_vendor = text("BaseBoardManufacturer")
    info.board_model = text("BaseBoardProduct")


def _collect_display(info: "SystemInfo"):
    mode = screen_mode()
    if not mode:
        return

    width, height, refresh = mode
    info.resolution = "{}x{}".format(width, height)
    info.refresh_rate = refresh


def _display_adapters(names: List[str]) -> List[str]:
    """Drop virtual adapters like "Microsoft Basic Render Driver".

    Falls back to the raw list if filtering leaves nothing, so an unrecognised
    GPU is still shown by name.
    """
    cleaned = [naming.clean(name) for name in names]
    real = [name for name in cleaned if naming.gpu_vendor(name)]

    return real or cleaned


def _collect_shell(info):
    """Terminal and shell we were started from."""
    # Windows Terminal advertises itself, which saves a walk when it's hosting
    # a shell we'd otherwise stop at.
    terminal = "Windows Terminal" if os.environ.get("WT_SESSION") else ""

    info.terminal, info.shell = shell.detect(
        _TERMINALS, _SHELLS, _NOT_A_TERMINAL, terminal=terminal
    )


def collect(info):
    """Fill in everything we can read from Windows."""
    _collect_os(info)
    _collect_cpu(info)
    _collect_board(info)
    _collect_display(info)
    _collect_shell(info)
    info.gpus = _display_adapters(gpu_names())
