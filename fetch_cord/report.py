"""Building a hardware report to paste into a GitHub issue.

Unknown hardware is the most common thing people open issues about, and the
id table is this project's main upkeep. This turns "my GPU shows as unknown"
into one command whose output contains everything needed to add it.
"""

from typing import List, Optional, Tuple

from . import __version__
from .ids import IdTable
from .system import platforms
from .system.info import UNKNOWN, SystemInfo

GENERIC = "generic fallback - needs an entry"
RESOLVED = "ok"
NOT_DETECTED = "not detected on this machine"


def _row(component: str, raw: str, key: Optional[str], status: str) -> str:
    return "| {} | {} | {} | {} |".format(
        component, raw or "-", key or "-", status
    )


def _os_rows(info: SystemInfo, ids: IdTable) -> List[str]:
    status = GENERIC if ids.os_id(info.os_key) == ids.generic("distro") else RESOLVED

    return [_row("OS", info.os_line, info.os_key, status)]


def _cpu_rows(info: SystemInfo, ids: IdTable) -> List[str]:
    if not info.cpu_name:
        return [_row("CPU", "", None, NOT_DETECTED)]

    resolved = ids.cpu_id(info.cpu_vendor, info.cpu_family)
    status = GENERIC if resolved == ids.generic("cpu") else RESOLVED
    key = "{} / {}".format(info.cpu_vendor, info.cpu_family or "-")

    return [_row("CPU", info.cpu_name, key, status)]


def _gpu_rows(info: SystemInfo, ids: IdTable) -> List[str]:
    if not info.gpus:
        return [_row("GPU", "", None, NOT_DETECTED)]

    asset = ids.gpu_asset(info.gpu_vendor_key)
    status = RESOLVED if asset else GENERIC

    return [_row("GPU", ", ".join(info.gpus), info.gpu_vendor_key or "-", status)]


def _board_rows(info: SystemInfo, ids: IdTable) -> List[str]:
    rows = []
    for component, value in (("Host", info.host_line), ("Board", info.board_line)):
        if value == UNKNOWN:
            rows.append(_row(component, "", None, NOT_DETECTED))
            continue

        key = ids.board_key(value)
        rows.append(_row(component, value, key, RESOLVED if key else GENERIC))

    return rows


def _desktop_rows(info: SystemInfo, ids: IdTable) -> List[str]:
    if not info.desktop and not info.window_manager:
        return []

    asset = ids.desktop_asset(info.desktop, info.window_manager)

    return [
        _row("Desktop", info.dewm_line, asset, RESOLVED if asset else GENERIC)
    ]


def _terminal_rows(info: SystemInfo, ids: IdTable) -> List[str]:
    if info.terminal_line == UNKNOWN:
        return []

    status = (
        GENERIC if ids.terminal_id(info.terminal) == ids.generic("terminal") else RESOLVED
    )

    return [_row("Terminal", info.terminal, info.terminal, status)]


def unresolved(info: SystemInfo, ids: IdTable) -> List[str]:
    """Components that fell back to a generic application or icon."""
    rows = _os_rows(info, ids) + _cpu_rows(info, ids) + _gpu_rows(info, ids)
    rows += _board_rows(info, ids) + _desktop_rows(info, ids) + _terminal_rows(info, ids)

    return [row for row in rows if GENERIC in row]


def build(info: SystemInfo, ids: Optional[IdTable] = None) -> Tuple[str, int]:
    """Render the report, and how many components need an id table entry."""
    ids = ids or IdTable()

    rows = _os_rows(info, ids) + _cpu_rows(info, ids) + _gpu_rows(info, ids)
    rows += _board_rows(info, ids) + _desktop_rows(info, ids) + _terminal_rows(info, ids)
    missing = [row for row in rows if GENERIC in row]

    lines = [
        "<!-- Paste this into a FetchCord issue -->",
        "",
        "**FetchCord** {} on **{}**".format(__version__, platforms.name()),
        "",
        "| Component | Detected | Matched key | Status |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(rows)
    lines.append("")

    if missing:
        lines.append(
            "{} component(s) fell back to a generic application. The "
            "**Detected** column above is the raw string to match against.".format(len(missing))
        )
    else:
        lines.append("Everything on this machine resolved to a specific application.")

    return "\n".join(lines), len(missing)


def report(info: SystemInfo, ids: Optional[IdTable] = None) -> int:
    """Print the report. Returns a process exit code."""
    text, _ = build(info, ids)
    print(text)

    return 0
