"""Per-platform collectors.

Each module in here exposes ``collect(info)``, which fills in the parts of
:class:`~fetch_cord.system.info.SystemInfo` that can only be read from that
operating system. Everything above the collectors - the display lines, the id
lookups, the cycles and the presence loop - is platform-neutral.
"""

import sys
from types import ModuleType
from typing import Optional

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"

SUPPORTED = IS_WINDOWS or IS_LINUX or IS_MACOS


def name() -> str:
    """A human-readable name for the platform we're running on."""
    if IS_WINDOWS:
        return "Windows"
    if IS_LINUX:
        return "Linux"
    if IS_MACOS:
        return "macOS"

    return sys.platform


def current() -> Optional[ModuleType]:
    """The collector for this platform, or None if we have none."""
    if IS_WINDOWS:
        from . import windows

        return windows

    if IS_LINUX:
        from . import linux

        return linux

    if IS_MACOS:
        from . import macos

        return macos

    return None


def disk_root() -> str:
    """The filesystem to report usage for."""
    if IS_WINDOWS:
        import os

        return os.environ.get("SystemDrive", "C:") + "\\"

    return "/"
