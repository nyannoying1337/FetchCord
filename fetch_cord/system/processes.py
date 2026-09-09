"""Looking at what else is running on this machine.

Used to suspend the presence while another program is running, and to spot a
window manager without shelling out to anything.
"""

from typing import Iterable, List, Optional, Set

import psutil


def _variants(name: str) -> Set[str]:
    """A process name with and without its .exe suffix.

    Lets one config line ("steam.exe") match on every platform.
    """
    name = name.strip().lower()
    if not name:
        return set()

    variants = {name}
    if name.endswith(".exe"):
        variants.add(name[: -len(".exe")])
    else:
        variants.add(name + ".exe")

    return variants


def running_names() -> List[str]:
    """Lowercased names of every process we can see."""
    names = []

    try:
        processes = psutil.process_iter(["name"])
    except Exception:
        return []

    for process in processes:
        try:
            name = process.info.get("name")
        except Exception:
            # A process that exited between listing and reading is normal,
            # and must not abandon the scan.
            continue

        if name:
            names.append(name.lower())

    return names


def find_running(names: Iterable[str]) -> Optional[str]:
    """The first of ``names`` that is currently running, or None.

    Returns the name as the caller wrote it, so it can be reported back.
    """
    wanted = {}
    for name in names:
        for variant in _variants(name):
            wanted[variant] = name.strip()

    if not wanted:
        return None

    for running in running_names():
        if running in wanted:
            return wanted[running]

    return None


def any_running(candidates: Iterable[str]) -> Optional[str]:
    """The first candidate that is running, matched exactly (lowercased).

    Unlike :func:`find_running` this does no .exe juggling - it is for
    matching against a known list of program names, such as window managers.
    """
    candidates = [c.lower() for c in candidates]
    running = set(running_names())

    for candidate in candidates:
        if candidate in running:
            return candidate

    return None
