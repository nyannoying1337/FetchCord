"""Optional "start FetchCord when I sign in" support.

Uses the per-user Run key, so it needs no administrator rights and touches
nothing outside HKEY_CURRENT_USER.
"""

import os
import shutil
import sys
from typing import Optional

from .system.winapi import IS_WINDOWS, UnsupportedPlatform

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "FetchCord"


def _winreg():
    if not IS_WINDOWS:
        raise UnsupportedPlatform("autostart is only available on Windows")

    import winreg

    return winreg


def startup_command() -> str:
    """The command Windows should run at sign-in.

    Prefers the windowless launcher so no console window appears; falls back to
    running the module with pythonw.exe.
    """
    launcher = shutil.which("fetchcordw") or shutil.which("fetchcord")
    if launcher:
        return '"{}"'.format(launcher)

    executable = sys.executable
    windowless = os.path.join(os.path.dirname(executable), "pythonw.exe")
    if os.path.exists(windowless):
        executable = windowless

    return '"{}" -m fetch_cord'.format(executable)


def status() -> Optional[str]:
    """The registered autostart command, or None if there isn't one."""
    winreg = _winreg()

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except OSError:
        return None

    return value


def install() -> str:
    """Register FetchCord to start at sign-in and return the command used."""
    winreg = _winreg()
    command = startup_command()

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)

    return command


def uninstall() -> bool:
    """Remove the autostart entry. True if one was actually removed."""
    winreg = _winreg()

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        return False
    except OSError:
        return False

    return True
