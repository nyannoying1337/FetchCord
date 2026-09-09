"""Reading system info on Linux.

Everything comes from /proc, /sys and /etc, so there are no subprocesses and
no dependency on anything being installed. Each reader takes a ``root`` so the
whole collector can be pointed at a fixture tree in tests.

Hardware that isn't there to read - a container with no DMI tables, a headless
box with no DRM connectors - is an expected outcome, not an error: those fields
simply stay empty and display as N/A.
"""

import glob
import os
import platform
from typing import TYPE_CHECKING, Dict, List, Optional

import psutil

from .. import naming, processes, shell

if TYPE_CHECKING:  # pragma: no cover
    from ..info import SystemInfo

OS_RELEASE = "etc/os-release"
CPUINFO = "proc/cpuinfo"
DMI = "sys/devices/virtual/dmi/id"
PCI_DEVICES = "sys/bus/pci/devices"
DRM = "sys/class/drm"
POWER_SUPPLY = "sys/class/power_supply"
CPU_FREQ = "sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"

# Ask collect() for the window manager names the id table knows.
WANTS_WINDOW_MANAGERS = True

# Where distributions put the PCI id database, when they ship it at all.
PCI_IDS = ("usr/share/hwdata/pci.ids", "usr/share/misc/pci.ids")

_TERMINALS = {
    "gnome-terminal-server": "gnome-terminal",
    "gnome-terminal": "gnome-terminal",
    "konsole": "konsole",
    "yakuake": "yakuake",
    "kitty": "kitty",
    "alacritty": "alacritty",
    "wezterm-gui": "wezterm",
    "xterm": "xterm",
    "urxvt": "urxvt",
    "rxvt": "urxvt",
    "st": "st",
    "foot": "foot",
    "xfce4-terminal": "xfce4-terminal",
    "lxterminal": "lxterminal",
    "mate-terminal": "mate-terminal",
    "cool-retro-term": "cool-retro-term",
    "terminator": "terminator",
    "tilix": "tilix",
    "io.elementary.terminal": "io.elementary.t",
    "terminus": "terminus",
    "code": "Visual Studio Code",
}

_SHELLS = {
    "bash": "bash",
    "zsh": "zsh",
    "fish": "fish",
    "tcsh": "tcsh",
    "csh": "csh",
    "ksh": "ksh",
    "dash": "dash",
    "sh": "sh",
    "nu": "nushell",
}

# Ancestors that tell us nothing about where we were launched from.
_IGNORED = {
    "python",
    "python3",
    "fetchcord",
    "sudo",
    "su",
    "env",
    "login",
    "systemd",
    "init",
    "sh",
}


def _read(root: str, *parts: str) -> Optional[str]:
    """Read a file under ``root``, or None if it isn't readable."""
    try:
        with open(os.path.join(root, *parts), encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def read_os_release(root: str = "/") -> Dict[str, str]:
    """Parse /etc/os-release into a dict."""
    text = _read(root, OS_RELEASE)
    if text is None:
        return {}

    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def read_cpuinfo(root: str = "/") -> Dict[str, str]:
    """First processor block of /proc/cpuinfo, as a dict."""
    text = _read(root, CPUINFO)
    if text is None:
        return {}

    values = {}
    for line in text.splitlines():
        if not line.strip():
            # Blank line ends the first processor's block.
            if values:
                break
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if key and key not in values:
            values[key] = value.strip()

    return values


def read_dmi(root: str = "/") -> Dict[str, str]:
    """DMI identity strings. Empty on machines that expose no DMI tables."""
    fields = (
        "sys_vendor",
        "product_name",
        "product_version",
        "board_vendor",
        "board_name",
    )

    values = {}
    for field in fields:
        text = _read(root, DMI, field)
        if text is not None:
            values[field] = naming.strip_placeholder(text.strip())

    return values


def _pci_model(root: str, vendor_id: str, device_id: str) -> Optional[str]:
    """Look a device up in pci.ids, when the distro ships it."""
    vendor_id = vendor_id.replace("0x", "").lower()
    device_id = device_id.replace("0x", "").lower()

    for candidate in PCI_IDS:
        text = _read(root, candidate)
        if text is None:
            continue

        in_vendor = False
        for line in text.splitlines():
            if not line or line.startswith("#"):
                continue
            if not line.startswith("\t"):
                # Vendor line: "10de  NVIDIA Corporation"
                in_vendor = line[:4].lower() == vendor_id
                continue
            if in_vendor and not line.startswith("\t\t"):
                entry = line.strip()
                if entry[:4].lower() == device_id:
                    model = entry[4:].strip()
                    # Prefer the marketing name: "GA104 [GeForce RTX 3070 Ti]"
                    if "[" in model and "]" in model:
                        model = model[model.index("[") + 1 : model.rindex("]")]

                    return model

    return None


def read_gpus(root: str = "/") -> List[str]:
    """Display adapters, from the PCI device tree."""
    names = []

    for device in sorted(glob.glob(os.path.join(root, PCI_DEVICES, "*"))):
        device_class = (_read(device, "class") or "").strip()
        # 0x03xxxx is the display controller class.
        if not device_class.startswith("0x03"):
            continue

        vendor_id = (_read(device, "vendor") or "").strip()
        vendor = naming.pci_vendor(vendor_id)
        if not vendor:
            continue

        model = _pci_model(root, vendor_id, (_read(device, "device") or "").strip())
        label = vendor.upper() if vendor in ("amd",) else vendor.capitalize()
        if vendor == "nvidia":
            label = "NVIDIA"

        names.append("{} {}".format(label, model) if model else label)

    return names


def read_resolution(root: str = "/") -> Optional[str]:
    """Mode of the first connected display, e.g. "2560x1440"."""
    for connector in sorted(glob.glob(os.path.join(root, DRM, "*"))):
        status = (_read(connector, "status") or "").strip()
        enabled = (_read(connector, "enabled") or "").strip()
        if status != "connected" and enabled != "enabled":
            continue

        modes = _read(connector, "modes")
        if modes:
            first = modes.strip().splitlines()
            if first:
                return first[0].strip()

    return None


# Wayland compositors that announce themselves, so we needn't look at the
# process list to find them.
_WM_ENV_HINTS = (
    ("SWAYSOCK", "sway"),
    ("I3SOCK", "i3"),
    ("HYPRLAND_INSTANCE_SIGNATURE", "hyprland"),
)


def read_desktop() -> str:
    """The desktop environment, from whichever variable the session set.

    XDG_CURRENT_DESKTOP can carry several colon-separated names
    ("ubuntu:GNOME"); the last is the actual desktop.
    """
    for variable in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION"):
        value = os.environ.get(variable, "").strip()
        if not value:
            continue

        name = value.split(":")[-1].strip()
        if name:
            # DESKTOP_SESSION is sometimes a path to a session file.
            return os.path.basename(name)

    return ""


def read_window_manager(candidates: Optional[List[str]] = None) -> str:
    """The window manager, from an environment hint or the process list.

    Looking at running processes avoids needing xprop or wmctrl, and works
    the same under X11 and Wayland.
    """
    for variable, name in _WM_ENV_HINTS:
        if os.environ.get(variable):
            return name

    if not candidates:
        return ""

    return processes.any_running(candidates) or ""


def is_laptop(root: str = "/") -> bool:
    return any(
        os.path.basename(path).startswith("BAT")
        for path in glob.glob(os.path.join(root, POWER_SUPPLY, "*"))
    )


def collect(info: "SystemInfo", root: str = "/", window_managers: Optional[List[str]] = None):
    """Fill in everything we can read from Linux.

    ``window_managers`` is the list of names worth looking for in the process
    list; the caller passes the ones the id table has icons for.
    """
    release = read_os_release(root)
    info.os_name = release.get("NAME") or release.get("PRETTY_NAME") or "Linux"
    info.os_release = release.get("VERSION_ID", "")
    info.os_key = naming.linux_distro_key(release)

    info.build = platform.release()
    machine = platform.machine()
    info.arch = {"AMD64": "x86_64", "arm64": "aarch64"}.get(machine, machine)

    cpuinfo = read_cpuinfo(root)
    info.cpu_name = (
        cpuinfo.get("model name") or cpuinfo.get("Model") or cpuinfo.get("Hardware") or ""
    )
    info.cpu_model = naming.cpu_model(info.cpu_name)
    info.cpu_vendor = naming.cpu_vendor(info.cpu_name or cpuinfo.get("vendor_id", ""))
    info.cpu_family = naming.cpu_family(info.cpu_name)

    max_freq = _read(root, CPU_FREQ)
    try:
        info.cpu_clock_mhz = int(max_freq.strip()) // 1000 if max_freq else 0
    except ValueError:
        info.cpu_clock_mhz = 0
    if not info.cpu_clock_mhz:
        try:
            info.cpu_clock_mhz = int(float(cpuinfo.get("cpu MHz", 0)))
        except (TypeError, ValueError):
            info.cpu_clock_mhz = 0

    try:
        info.cpu_cores = psutil.cpu_count(logical=True) or 0
    except Exception:
        info.cpu_cores = 0

    dmi = read_dmi(root)
    info.system_vendor = dmi.get("sys_vendor", "")
    product = dmi.get("product_name", "")
    version = dmi.get("product_version", "")
    # Laptops often put the machine type in product_name ("20UD0013US") and the
    # name people recognise in product_version ("ThinkPad T14 Gen 1").
    info.system_model = version if naming.looks_like_a_name(version) else product
    info.board_vendor = dmi.get("board_vendor", "")
    info.board_model = dmi.get("board_name", "")

    info.gpus = read_gpus(root)

    resolution = read_resolution(root)
    if resolution:
        info.resolution = resolution

    info.laptop = is_laptop(root)

    info.terminal, info.shell = shell.detect(
        _TERMINALS, _SHELLS, _IGNORED, shell=shell.basename(os.environ.get("SHELL"))
    )

    info.desktop = read_desktop()
    info.window_manager = read_window_manager(window_managers)
