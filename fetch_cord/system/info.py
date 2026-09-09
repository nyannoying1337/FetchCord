"""Collecting the system facts FetchCord shows on Discord.

Everything is read natively (registry, a couple of ctypes calls and psutil) so
there is no dependency on an external fetch tool.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import psutil

from . import naming
from . import platforms


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

    def _system_text(self) -> str:
        return " ".join(part for part in (self.system_vendor, self.system_model) if part)

    def _board_text(self) -> str:
        return " ".join(part for part in (self.board_vendor, self.board_model) if part)

    @property
    def host_line(self) -> str:
        system = self._system_text()

        # Self-built desktops usually leave SystemProductName as a placeholder,
        # which we drop - that leaves the bare vendor ("ASUS"), so prefer the
        # board, which names the actual hardware.
        if not self.system_model:
            return self._board_text() or system or UNKNOWN

        return system or UNKNOWN

    @property
    def board_line(self) -> str:
        return self._board_text() or self._system_text() or UNKNOWN

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
    root = platforms.disk_root()
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


def collect(memory_unit: str = "gb") -> SystemInfo:
    """Gather everything we know about this machine."""
    info = SystemInfo(memory_unit=memory_unit)

    try:
        info.boot_time = psutil.boot_time()
    except Exception:
        info.boot_time = time.time()

    collector = platforms.current()
    if collector is not None:
        try:
            collector.collect(info)
        except Exception as error:
            # A collector failing is not worth losing the whole presence over:
            # anything it didn't fill simply reads N/A.
            print("Could not read some system info: {}".format(error))

    info.refresh()

    return info
