"""Optional "start FetchCord when I sign in" support.

Each platform gets the mechanism its users expect - a per-user Run key on
Windows, a systemd user service on Linux - behind one set of flags. Neither
needs administrator rights, and neither touches anything outside the current
user's own configuration.
"""

import os
import shutil
import subprocess
import sys
from typing import Optional

from .system import platforms

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "FetchCord"

SERVICE_NAME = "fetchcord.service"
SERVICE_UNIT = """[Unit]
Description=FetchCord - system info as Discord Rich Presence
After=graphical-session.target

[Service]
Type=simple
ExecStart={command}
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
"""


class UnsupportedPlatform(RuntimeError):
    """Raised when autostart isn't available on this platform."""


def launcher() -> str:
    """The command that starts FetchCord.

    Prefers the installed entry point, falling back to running the module with
    the interpreter we're using now.
    """
    if platforms.IS_WINDOWS:
        # The windowless launcher keeps a console from flashing up at sign-in.
        found = shutil.which("fetchcordw") or shutil.which("fetchcord")
        if found:
            return '"{}"'.format(found)

        executable = sys.executable
        windowless = os.path.join(os.path.dirname(executable), "pythonw.exe")
        if os.path.exists(windowless):
            executable = windowless

        return '"{}" -m fetch_cord'.format(executable)

    found = shutil.which("fetchcord")

    return found or "{} -m fetch_cord".format(sys.executable)


# -- Windows ------------------------------------------------------------


def _winreg():
    import winreg

    return winreg


def _windows_status() -> Optional[str]:
    winreg = _winreg()

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except OSError:
        return None

    return value


def _windows_install() -> str:
    winreg = _winreg()
    command = launcher()

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)

    return command


def _windows_uninstall() -> bool:
    winreg = _winreg()

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except OSError:
        return False

    return True


# -- Linux --------------------------------------------------------------


def unit_path() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")

    return os.path.join(base, "systemd", "user", SERVICE_NAME)


def _systemctl(*args) -> bool:
    """Run systemctl --user, reporting whether it worked.

    Missing systemd is not an error worth crashing over: the unit file is
    still written, and the user can start it however they like.
    """
    if not shutil.which("systemctl"):
        return False

    try:
        result = subprocess.run(
            ["systemctl", "--user"] + list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    return result.returncode == 0


def _linux_status() -> Optional[str]:
    path = unit_path()
    if not os.path.exists(path):
        return None

    return path


def _linux_install() -> str:
    path = unit_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(SERVICE_UNIT.format(command=launcher()))

    _systemctl("daemon-reload")
    _systemctl("enable", "--now", SERVICE_NAME)

    return path


def _linux_uninstall() -> bool:
    path = unit_path()
    if not os.path.exists(path):
        return False

    _systemctl("disable", "--now", SERVICE_NAME)
    try:
        os.remove(path)
    except OSError:
        return False

    _systemctl("daemon-reload")

    return True


# -- dispatch -----------------------------------------------------------


def _backend():
    if platforms.IS_WINDOWS:
        return _windows_status, _windows_install, _windows_uninstall
    if platforms.IS_LINUX:
        return _linux_status, _linux_install, _linux_uninstall

    raise UnsupportedPlatform("autostart is not available on {}".format(platforms.name()))


def status() -> Optional[str]:
    """What is registered to start FetchCord, or None if nothing is."""
    return _backend()[0]()


def install() -> str:
    """Register FetchCord to start at sign-in; returns what was registered."""
    return _backend()[1]()


def uninstall() -> bool:
    """Remove the autostart entry. True if one was actually removed."""
    return _backend()[2]()
