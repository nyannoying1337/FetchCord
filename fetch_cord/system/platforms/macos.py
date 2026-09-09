"""Reading system info on macOS.

Two sources: one `sysctl` call for the hardware strings, and CoreGraphics
through ctypes for the display. `system_profiler` would give more - GPU models
on Intel Macs, chiefly - but it takes about a second to answer, which is too
long to pay on every start.
"""

import ctypes
import ctypes.util
import os
import platform
import subprocess
from typing import TYPE_CHECKING, Dict, Optional, Tuple

import psutil

from .. import naming, shell

if TYPE_CHECKING:  # pragma: no cover
    from ..info import SystemInfo

SYSCTL_KEYS = (
    "hw.model",
    "machdep.cpu.brand_string",
    "hw.cpufrequency_max",
)

_TERMINALS = {
    "terminal": "apple_terminal",
    "iterm2": "iterm2",
    "kitty": "kitty",
    "alacritty": "alacritty",
    "wezterm-gui": "wezterm",
    "hyper": "hyper",
    "warp": "warp",
    "code": "Visual Studio Code",
}

_SHELLS = {
    "zsh": "zsh",
    "bash": "bash",
    "fish": "fish",
    "tcsh": "tcsh",
    "csh": "csh",
    "ksh": "ksh",
    "sh": "sh",
    "nu": "nushell",
}

_IGNORED = {"python", "python3", "fetchcord", "login", "sudo", "su", "env", "launchd", "sh"}


def sysctl(*names: str) -> Dict[str, str]:
    """Read sysctl values by name.

    Queried without -n so the output is "key: value" and a name this machine
    doesn't have (hw.cpufrequency_max is Intel-only) can't shift the others
    out of alignment.
    """
    try:
        result = subprocess.run(
            ["sysctl"] + list(names),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            encoding="utf-8",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return {}

    values = {}
    for line in (result.stdout or "").splitlines():
        key, _, value = line.partition(":")
        if value:
            values[key.strip()] = value.strip()

    return values


def screen_mode() -> Optional[Tuple[int, int]]:
    """Native pixel size of the main display.

    CGDisplayPixelsWide reports points, which on a Retina panel is half the
    real thing, so the display mode's pixel size is preferred.
    """
    path = ctypes.util.find_library("CoreGraphics")
    if not path:
        return None

    try:
        core = ctypes.CDLL(path)
    except OSError:
        return None

    try:
        core.CGMainDisplayID.restype = ctypes.c_uint32
        display = core.CGMainDisplayID()

        core.CGDisplayCopyDisplayMode.restype = ctypes.c_void_p
        core.CGDisplayCopyDisplayMode.argtypes = [ctypes.c_uint32]
        mode = core.CGDisplayCopyDisplayMode(display)

        if mode:
            try:
                for attribute in ("CGDisplayModeGetPixelWidth", "CGDisplayModeGetPixelHeight"):
                    getattr(core, attribute).restype = ctypes.c_size_t
                    getattr(core, attribute).argtypes = [ctypes.c_void_p]

                width = core.CGDisplayModeGetPixelWidth(mode)
                height = core.CGDisplayModeGetPixelHeight(mode)
                if width and height:
                    return (int(width), int(height))
            finally:
                core.CGDisplayModeRelease.argtypes = [ctypes.c_void_p]
                core.CGDisplayModeRelease(mode)

        # Older releases without the pixel accessors: points will do.
        for attribute in ("CGDisplayPixelsWide", "CGDisplayPixelsHigh"):
            getattr(core, attribute).restype = ctypes.c_size_t
            getattr(core, attribute).argtypes = [ctypes.c_uint32]

        width = core.CGDisplayPixelsWide(display)
        height = core.CGDisplayPixelsHigh(display)
        if width and height:
            return (int(width), int(height))
    except (AttributeError, OSError, ValueError):
        return None

    return None


def collect(info: "SystemInfo"):
    """Fill in everything we can read from macOS."""
    version = platform.mac_ver()[0]
    info.os_name = naming.macos_name(version)
    info.os_release = version
    info.os_key = "macos"

    info.build = platform.release()
    machine = platform.machine()
    info.arch = {"x86_64": "x86_64", "arm64": "arm64"}.get(machine, machine)

    values = sysctl(*SYSCTL_KEYS)

    brand = values.get("machdep.cpu.brand_string", "")
    info.cpu_name = brand
    info.cpu_model = naming.cpu_model(brand)
    info.cpu_vendor = naming.cpu_vendor(brand)
    info.cpu_family = naming.cpu_family(brand)

    try:
        info.cpu_cores = psutil.cpu_count(logical=True) or 0
    except Exception:
        info.cpu_cores = 0

    try:
        # Intel only; Apple Silicon doesn't publish a clock.
        info.cpu_clock_mhz = int(values.get("hw.cpufrequency_max", 0)) // 1_000_000
    except (TypeError, ValueError):
        info.cpu_clock_mhz = 0

    model = values.get("hw.model", "")
    info.system_vendor = "Apple" if model else ""
    info.system_model = model
    info.board_vendor = info.system_vendor
    info.board_model = model

    # Apple Silicon graphics are part of the chip, so we already know the name.
    # Intel Macs would need system_profiler, which is too slow to justify.
    if info.cpu_vendor == "apple" and info.cpu_model:
        info.gpus = ["{} GPU".format(info.cpu_model)]

    mode = screen_mode()
    if mode:
        info.resolution = "{}x{}".format(mode[0], mode[1])

    info.terminal, info.shell = shell.detect(
        _TERMINALS, _SHELLS, _IGNORED, shell=shell.basename(os.environ.get("SHELL"))
    )
