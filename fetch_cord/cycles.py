"""Turning system info + config into the presences FetchCord rotates through.

Each cycle is shown under a different Discord application, which is what makes
the "playing Windows 11 / playing Ryzen 7" effect work.
"""

from dataclasses import dataclass
from typing import List, Optional

from .config import CycleConfig
from .ids import IdTable
from .system.info import UNKNOWN, SystemInfo

# Discord limits both text fields to 128 characters and rejects a field with
# fewer than 2, so anything shorter is dropped instead of sent.
MAX_TEXT = 128
MIN_TEXT = 2


def clamp(text: Optional[str]) -> Optional[str]:
    """Fit a line into what Discord accepts, or None if it can't be shown."""
    if not text or text == UNKNOWN:
        # Better to leave the line out than to publish "N/A" to a profile.
        return None

    text = text.strip()
    if len(text) < MIN_TEXT:
        return None
    if len(text) > MAX_TEXT:
        text = text[: MAX_TEXT - 1].rstrip() + "…"

    return text


@dataclass
class Payload:
    """One presence update, ready to hand to pypresence."""

    name: str
    client_id: str
    details: Optional[str] = None
    state: Optional[str] = None
    large_image: str = "big"
    large_text: Optional[str] = None
    small_image: Optional[str] = None
    small_text: Optional[str] = None
    start: Optional[int] = None
    seconds: int = 30
    buttons: Optional[List[dict]] = None

    def as_update(self) -> dict:
        """Keyword arguments for ``Presence.update``, omitting empty fields."""
        fields = {
            "details": self.details,
            "state": self.state,
            "large_image": self.large_image,
            "large_text": self.large_text,
            "small_image": self.small_image,
            "small_text": self.small_text,
            "start": self.start,
            "buttons": self.buttons,
        }

        return {key: value for key, value in fields.items() if value is not None}


def _build(
    cycle: CycleConfig,
    info: SystemInfo,
    client_id: str,
    large_text: str,
    small_image: Optional[str],
    small_text: Optional[str],
) -> Payload:
    # small_text is the tooltip for the small icon, so it is only worth
    # sending when there is an icon to hover.
    icon = small_image if cycle.small_icon else None

    return Payload(
        name=cycle.name,
        client_id=client_id,
        details=clamp(info.line(cycle.top_line)),
        state=clamp(info.line(cycle.bottom_line)),
        large_text=clamp(large_text),
        small_image=icon,
        small_text=clamp(small_text) if icon else None,
        start=int(info.boot_time) if info.boot_time else None,
        seconds=cycle.time,
    )


def build_payload(cycle: CycleConfig, info: SystemInfo, ids: IdTable) -> Optional[Payload]:
    """Build one cycle's presence, or None when there's nothing worth showing."""
    if cycle.name == "os":
        return _build(
            cycle,
            info,
            client_id=ids.os_id(info.os_key),
            large_text=info.os_line,
            # The distro applications carry desktop/window manager icons, so
            # prefer those; Windows and macOS have no desktop set and keep
            # showing their board vendor.
            small_image=(
                ids.desktop_asset(info.desktop, info.window_manager)
                or ids.board_asset(info.board_line)
            ),
            small_text=info.dewm_line or info.board_line,
        )

    if cycle.name == "hardware":
        if info.cpu_line == UNKNOWN and info.gpu_line == UNKNOWN:
            return None

        return _build(
            cycle,
            info,
            client_id=ids.cpu_id(info.cpu_vendor, info.cpu_family),
            large_text=info.cpu_line,
            small_image=ids.gpu_asset(info.gpu_vendor_key),
            small_text=info.gpu_line,
        )

    if cycle.name == "host":
        if info.host_line == UNKNOWN and info.board_line == UNKNOWN:
            return None

        return _build(
            cycle,
            info,
            client_id=ids.board_id(info.board_line),
            large_text=info.board_line,
            small_image=info.chassis,
            small_text=info.chassis.capitalize(),
        )

    if cycle.name == "terminal":
        if info.terminal_line == UNKNOWN:
            return None

        return _build(
            cycle,
            info,
            client_id=ids.terminal_id(info.terminal),
            large_text=info.terminal_line,
            small_image=ids.shell_asset(info.shell),
            small_text=info.shell_line,
        )

    return None


def build_payloads(
    cycles: List[CycleConfig],
    info: SystemInfo,
    ids: IdTable,
    buttons: Optional[List] = None,
) -> List[Payload]:
    """Build every enabled cycle that has something to show.

    Buttons are the same whichever cycle is showing, so they are attached
    to all of them here rather than built per cycle.
    """
    links = [{"label": button.label, "url": button.url} for button in buttons or []]

    payloads = []
    for cycle in cycles:
        payload = build_payload(cycle, info, ids)
        if payload and payload.client_id:
            payload.buttons = links or None
            payloads.append(payload)

    return payloads
