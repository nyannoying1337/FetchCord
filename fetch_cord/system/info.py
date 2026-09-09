"""Collecting the system facts FetchCord shows on Discord.

Everything is read natively (registry, a couple of ctypes calls and psutil) so
there is no dependency on an external fetch tool.
"""

import os
import platform
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import psutil

from . import naming, winapi

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

UNKNOWN = "N/A"


def _uptime_text(boot_time: float) -> str:
    seconds = max(0, int(time.time() - boot_time))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60

    parts = []
    if days:
        parts.append("{} day{}".format(days, "s" if days != 1 else ""))
    if hours:
        parts.append("{} hour{}".format(hours, "s" if hours != 1 else ""))
    parts.append("{} min{}".format(minutes, "s" if minutes != 1 else ""))

    return ", ".join(parts)


@dataclass
class SystemInfo:
    """A snapshot of the machine, plus the display lines built from it."""

    os_name: str = "Windows"
    os_release: str = ""
    os_key: str = "unknown"
    build: str = ""
    arch: str = ""

    boot_time: float = 0.0

    cpu_name: str = ""
    cpu_model: str = ""
    cpu_vendor: str = "unknown"
    cpu_family: Optional[str] = None
    cpu_cores: int = 0
    cpu_clock_mhz: int = 0

    gpus: List[str] = field(default_factory=list)

    system_vendor: str = ""
    system_model: str = ""
    board_vendor: str = ""
    board_model: str = ""

    memory_used: int = 0
    memory_total: int = 0
    disk_used: int = 0
    disk_total: int = 0

    resolution: str = ""
    refresh_rate: int = 0

    battery_percent: Optional[float] = None
    battery_plugged: bool = False
    laptop: bool = False

    terminal: str = ""
    shell: str = ""

    memory_unit: str = "gb"

    # -- display lines ---------------------------------------------------

    @property
    def os_line(self) -> str:
        parts = [self.os_name]
        if self.os_release:
            parts.append(self.os_release)
        if self.arch:
            parts.append(self.arch)

        return " ".join(parts)

    @property
    def kernel_line(self) -> str:
        return self.build or UNKNOWN

    @property
    def uptime_line(self) -> str:
        return _uptime_text(self.boot_time)

    @property
    def cpu_line(self) -> str:
        if not self.cpu_model:
            return UNKNOWN

        line = self.cpu_model
        if self.cpu_cores:
            line += " ({})".format(self.cpu_cores)
        if self.cpu_clock_mhz:
            line += " @ {:.2f}GHz".format(self.cpu_clock_mhz / 1000)

        return line

    @property
    def gpu_line(self) -> str:
        return ", ".join(self.gpus) if self.gpus else UNKNOWN

    @property
    def gpu_vendor_key(self) -> str:
        return "".join(naming.gpu_vendors(self.gpus))

    @property
    def memory_line(self) -> str:
        if not self.memory_total:
            return UNKNOWN

        return "{} / {}".format(
            naming.format_bytes(self.memory_used, self.memory_unit),
            naming.format_bytes(self.memory_total, self.memory_unit),
        )

    @property
    def disk_line(self) -> str:
        if not self.disk_total:
            return UNKNOWN

        percent = round(self.disk_used / self.disk_total * 100)
        return "{} / {} ({}%)".format(
            naming.format_bytes(self.disk_used),
            naming.format_bytes(self.disk_total),
            percent,
        )

    @property
    def host_line(self) -> str:
        host = " ".join(part for part in (self.system_vendor, self.system_model) if part)

        return host or UNKNOWN

    @property
    def board_line(self) -> str:
        board = " ".join(part for part in (self.board_vendor, self.board_model) if part)

        return board or self.host_line

    @property
    def resolution_line(self) -> str:
        if not self.resolution:
            return UNKNOWN
        if self.refresh_rate:
            return "{} @ {}Hz".format(self.resolution, self.refresh_rate)

        return self.resolution

    @property
    def battery_line(self) -> str:
        if self.battery_percent is None:
            return UNKNOWN

        return "{}%{}".format(
            round(self.battery_percent), " (charging)" if self.battery_plugged else ""
        )

    @property
    def terminal_line(self) -> str:
        return self.terminal or UNKNOWN

    @property
    def shell_line(self) -> str:
        return self.shell or UNKNOWN

    @property
    def chassis(self) -> str:
        return "laptop" if self.laptop else "desktop"

    def line(self, name: str) -> str:
        """Look up a display line by the name used in the config file."""
        lines: Dict[str, str] = {
            "os": self.os_line,
            "kernel": self.kernel_line,
            "uptime": self.uptime_line,
            "cpu": self.cpu_line,
            "gpu": self.gpu_line,
            "memory": self.memory_line,
            "disk": self.disk_line,
            "host": self.host_line,
            "board": self.board_line,
            "resolution": self.resolution_line,
            "battery": self.battery_line,
            "terminal": self.terminal_line,
            "shell": self.shell_line,
        }

        return lines.get(name, UNKNOWN)

    # -- collection ------------------------------------------------------

    def refresh(self):
        """Re-read the values that change while FetchCord is running."""
        _collect_memory(self)
        _collect_disk(self)
        _collect_battery(self)


LINE_NAMES = (
    "os",
    "kernel",
    "uptime",
    "cpu",
    "gpu",
    "memory",
    "disk",
    "host",
    "board",
    "resolution",
    "battery",
    "terminal",
    "shell",
)


def _collect_memory(info: SystemInfo):
    try:
        memory = psutil.virtual_memory()
    except Exception:
        return

    info.memory_total = memory.total
    info.memory_used = memory.total - memory.available


def _collect_disk(info: SystemInfo):
    root = os.environ.get("SystemDrive", "C:") + "\\" if winapi.IS_WINDOWS else "/"
    try:
        usage = psutil.disk_usage(root)
    except Exception:
        return

    info.disk_total = usage.total
    info.disk_used = usage.used


def _collect_battery(info: SystemInfo):
    try:
        battery = psutil.sensors_battery()
    except Exception:
        battery = None

    if battery is None:
        info.battery_percent = None
        info.battery_plugged = False
        return

    info.battery_percent = battery.percent
    info.battery_plugged = bool(battery.power_plugged)
    info.laptop = True


def _collect_os(info: SystemInfo):
    values = winapi.os_version()

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


def _collect_cpu(info: SystemInfo):
    values = winapi.cpu_info()

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


def _collect_board(info: SystemInfo):
    values = winapi.bios_info()

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


def _collect_display(info: SystemInfo):
    mode = winapi.screen_mode()
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
    real = [name for name in names if naming.gpu_vendor(name)]

    return real or names


def _collect_shell(info: SystemInfo):
    """Walk up the process tree looking for the terminal and shell we run in."""
    if os.environ.get("WT_SESSION"):
        info.terminal = "Windows Terminal"

    try:
        process = psutil.Process().parent()
    except Exception:
        return

    depth = 0
    while process is not None and depth < 8:
        if info.terminal and info.shell:
            break

        depth += 1
        try:
            name = process.name().lower()
            parent = process.parent()
        except Exception:
            return

        if not info.shell and name in _SHELLS:
            info.shell = _SHELLS[name]
        elif not info.terminal and name in _TERMINALS:
            info.terminal = _TERMINALS[name]
            break
        elif name in _NOT_A_TERMINAL or name in _SHELLS:
            pass
        elif not info.terminal:
            # Something we don't have a name for; stop rather than guess.
            break

        process = parent


def collect(memory_unit: str = "gb") -> SystemInfo:
    """Gather everything we know about this machine."""
    info = SystemInfo(memory_unit=memory_unit)

    try:
        info.boot_time = psutil.boot_time()
    except Exception:
        info.boot_time = time.time()

    if winapi.IS_WINDOWS:
        _collect_os(info)
        _collect_cpu(info)
        _collect_board(info)
        _collect_display(info)
        _collect_shell(info)
        info.gpus = _display_adapters(winapi.gpu_names())

    info.refresh()

    return info
