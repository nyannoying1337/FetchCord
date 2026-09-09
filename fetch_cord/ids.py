"""Lookups against fetchcord_ids.json.

The table maps hardware to two different things:

* **Discord application ids** (long numeric strings) - these decide which
  application, and so which name, the presence is shown under.
* **Asset keys** (short names like ``nvidia``) - these name an image uploaded
  to that application, used as the small icon.

An unknown component is normal, not an error: we fall back to the table's
``unknown`` entry and still show the full model name as text.
"""

import json
import os
import re
from typing import Dict, List, Optional

from importlib.resources import files as _resource_files

from .system import naming

IDS_FILE = "fetchcord_ids.json"

# Firmware vendor strings that don't contain the name the id table knows them
# by. Rewritten before lookup so both the app id and the icon resolve.
_VENDOR_ALIASES = (
    ("micro-star international", "msi"),
    ("micro-star", "msi"),
    ("hewlett packard", "hewlett-packard"),
    ("gigabyte technology", "gigabyte"),
    ("asustek computer", "asustek"),
)

# Table keys that name a vendor and therefore have an icon uploaded. Model
# specific keys ("MS-7C02 1.0") share an app id with one of these, and borrow
# its icon.
_VENDOR_ASSETS = (
    "asrock",
    "aorus",
    "asus",
    "asustek",
    "acer",
    "aspire",
    "dell",
    "inspiron",
    "latitude",
    "optiplex",
    "gigabyte",
    "hp",
    "hewlett-packard",
    "lenovo",
    "thinkpad",
    "thinkcentre",
    "ideapad",
    "msi",
    "tuf",
    "hvm",
    "macbookpro",
    "macbookair",
)


def load_ids() -> Dict:
    """Read the id table, preferring a copy fetched by ``fetchcord --update``."""
    from . import resources
    from .config import config_dir

    updated = os.path.join(config_dir(), IDS_FILE)
    if os.path.exists(updated):
        try:
            with open(updated, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            print("Ignoring unreadable {} ({}), using the bundled table.".format(updated, error))

    with _resource_files(resources).joinpath(IDS_FILE).open(encoding="utf-8") as handle:
        return json.load(handle)


def _match(table: Dict[str, str], value: str) -> Optional[str]:
    """Find the table key contained in ``value``, longest key first.

    Short keys ("hp", "g3") are matched on word boundaries so they don't fire
    inside unrelated model names.
    """
    value = value.lower()
    if not value:
        return None

    for key in sorted(table, key=len, reverse=True):
        if key == "unknown":
            continue

        needle = key.lower()
        if len(needle) <= 3 and needle.isalnum():
            if re.search(r"\b{}\b".format(re.escape(needle)), value):
                return key
        elif needle in value:
            return key

    return None


def normalise_vendor(text: str) -> str:
    """Rewrite firmware vendor strings into the names the id table uses."""
    value = text.lower()
    for alias, replacement in _VENDOR_ALIASES:
        value = value.replace(alias, replacement)

    return value


class IdTable:
    """Resolves hardware into Discord application ids and asset keys."""

    def __init__(self, data: Optional[Dict] = None):
        self.data = data if data is not None else load_ids()

    def _section(self, name: str) -> Dict:
        return self.data.get(name, {})

    def os_id(self, os_key: str) -> str:
        distros = self._section("distro")

        return distros.get(os_key, distros.get("unknown", ""))

    def cpu_id(self, vendor: str, family: Optional[str]) -> str:
        cpus = self._section("cpu")
        unknown = cpus.get("unknown", "")

        by_vendor = cpus.get(vendor)
        if not isinstance(by_vendor, dict) or not family:
            return unknown

        for candidate in naming.cpu_family_fallbacks(family):
            if candidate in by_vendor:
                return by_vendor[candidate]

        return unknown

    def gpu_asset(self, vendor_key: str) -> Optional[str]:
        """Asset name for a GPU vendor combination, or None if we have no icon."""
        gpus = self._section("gpu")
        asset = gpus.get(vendor_key, gpus.get("unknown"))

        return None if asset in (None, "off") else asset

    def board_key(self, text: str) -> Optional[str]:
        return _match(self._section("motherboard"), normalise_vendor(text))

    def board_id(self, text: str) -> str:
        boards = self._section("motherboard")
        key = self.board_key(text)

        return boards.get(key, boards.get("unknown", "")) if key else boards.get("unknown", "")

    def board_asset(self, text: str) -> Optional[str]:
        """Icon name for a board, or None when we have nothing to show.

        Model specific matches ("MS-7C02 1.0") are resolved to the vendor icon
        that shares their application id.
        """
        key = self.board_key(text)
        if not key:
            return None
        if key.lower() in _VENDOR_ASSETS:
            return key.lower()

        boards = self._section("motherboard")
        board_id = boards.get(key)
        for vendor in _VENDOR_ASSETS:
            if vendor in boards and boards[vendor] == board_id:
                return vendor

        return None

    def terminal_id(self, name: str) -> str:
        terminals = self._section("terminal")
        key = _match(terminals, name)

        return terminals.get(key, terminals.get("unknown", "")) if key else terminals.get("unknown", "")

    def desktop_asset(self, desktop: str, window_manager: str = "") -> Optional[str]:
        """Icon for a desktop environment, falling back to the window manager.

        Distro applications carry these assets (kde, gnome, i3, sway, ...),
        which is what makes them worth showing on the OS cycle.
        """
        for section, value in (("desktop", desktop), ("windowmanager", window_manager)):
            if not value:
                continue

            table = self._section(section)
            key = _match(table, value)
            if key:
                asset = table.get(key)
                if asset and asset != "unknown":
                    return asset

        return None

    def desktop_keys(self) -> List[str]:
        """Window manager names worth looking for in the process list."""
        return [key for key in self._section("windowmanager") if key != "unknown"]

    def shell_asset(self, name: str) -> Optional[str]:
        shells = self._section("shell")
        key = _match(shells, name)
        if not key:
            return None

        asset = shells.get(key)

        return None if asset in (None, "unknown") else asset

    def known_boards(self) -> List[str]:
        return sorted(key for key in self._section("motherboard") if key != "unknown")
