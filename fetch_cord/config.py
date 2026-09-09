"""Reading fetch_cord.conf.

A broken config should never stop FetchCord from starting: unknown or invalid
values are reported and replaced with the default, and a missing file just
means the defaults are used throughout.
"""

import configparser
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from .system.info import LINE_NAMES

APP_DIR_NAME = "FetchCord"
CONFIG_NAME = "fetch_cord.conf"

MIN_CYCLE_TIME = 15

# Discord's limits on presence buttons.
MAX_BUTTONS = 2
MAX_BUTTON_LABEL = 32
DEFAULT_CYCLE_TIME = 30
DEFAULT_POLL_RATE = 3

# The cycles FetchCord knows how to show, in display order.
CYCLE_NAMES = ("os", "hardware", "host", "terminal")

DEFAULTS: Dict[str, Dict[str, str]] = {
    "general": {
        "poll_rate": str(DEFAULT_POLL_RATE),
        "time": str(DEFAULT_CYCLE_TIME),
        "pause_when": "",
    },
    "os": {
        "enabled": "on",
        "top_line": "kernel",
        "bottom_line": "memory",
        "small_icon": "on",
        "time": "",
    },
    "hardware": {
        "enabled": "on",
        "top_line": "cpu",
        "bottom_line": "gpu",
        "small_icon": "on",
        "time": "",
    },
    "host": {
        "enabled": "on",
        "top_line": "host",
        "bottom_line": "resolution",
        "small_icon": "on",
        "time": "",
    },
    "buttons": {
        "label_1": "",
        "url_1": "",
        "label_2": "",
        "url_2": "",
    },
    "terminal": {
        "enabled": "off",
        "top_line": "terminal",
        "bottom_line": "shell",
        "small_icon": "on",
        "time": "",
    },
}


@dataclass
class CycleConfig:
    name: str
    enabled: bool
    top_line: str
    bottom_line: str
    small_icon: bool
    time: int


@dataclass
class Button:
    label: str
    url: str


@dataclass
class Config:
    poll_rate: int = DEFAULT_POLL_RATE
    cycles: Dict[str, CycleConfig] = None
    warnings: List[str] = None
    pause_when: List[str] = None
    buttons: List[Button] = None

    def enabled_cycles(self) -> List[CycleConfig]:
        return [self.cycles[name] for name in CYCLE_NAMES if self.cycles[name].enabled]


def config_dir() -> str:
    """Where a user's config lives (%APPDATA%\\FetchCord, or ~/.config elsewhere)."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, APP_DIR_NAME)

    return os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), APP_DIR_NAME
    )


def config_path() -> str:
    return os.path.join(config_dir(), CONFIG_NAME)


def default_config_text() -> str:
    """The bundled example config, used when writing one out for the user."""
    from importlib.resources import files as resource_files

    from . import resources

    return resource_files(resources).joinpath(CONFIG_NAME).read_text(encoding="utf-8")


def write_default_config(path: Optional[str] = None) -> str:
    """Write the example config for the user to edit. Never overwrites."""
    target = path or config_path()
    if os.path.exists(target):
        return target

    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(default_config_text())

    return target


def _buttons_from_section(section: Dict[str, str], warnings: List[str]) -> List["Button"]:
    """Read up to two presence buttons, dropping any that Discord would reject."""
    buttons = []

    for index in range(1, MAX_BUTTONS + 1):
        label = section.get("label_{}".format(index), "").strip()
        url = section.get("url_{}".format(index), "").strip()

        if not label and not url:
            continue

        if not label or not url:
            warnings.append(
                "config: button {} needs both a label and a url, ignoring".format(index)
            )
            continue

        if len(label) > MAX_BUTTON_LABEL:
            warnings.append(
                "config: button {} label is longer than {} characters, ignoring".format(
                    index, MAX_BUTTON_LABEL
                )
            )
            continue

        # Discord only accepts https links on presence buttons.
        if not url.lower().startswith("https://"):
            warnings.append(
                'config: button {} url must start with "https://", ignoring'.format(index)
            )
            continue

        buttons.append(Button(label=label, url=url))

    return buttons


def _as_bool(value: str) -> Optional[bool]:
    value = value.strip().lower()
    if value in ("on", "true", "yes", "1"):
        return True
    if value in ("off", "false", "no", "0"):
        return False

    return None


def _cycle_from_section(
    name: str, section: Dict[str, str], fallback_time: int, warnings: List[str]
) -> CycleConfig:
    defaults = DEFAULTS[name]

    def warn(option: str, value: str, using: object):
        warnings.append(
            'config: invalid value "{}" for {} in [{}], using {}'.format(
                value, option, name, using
            )
        )

    enabled = _as_bool(section.get("enabled", defaults["enabled"]))
    if enabled is None:
        warn("enabled", section.get("enabled", ""), defaults["enabled"])
        enabled = _as_bool(defaults["enabled"])

    small_icon = _as_bool(section.get("small_icon", defaults["small_icon"]))
    if small_icon is None:
        warn("small_icon", section.get("small_icon", ""), defaults["small_icon"])
        small_icon = _as_bool(defaults["small_icon"])

    lines = {}
    for option in ("top_line", "bottom_line"):
        value = section.get(option, defaults[option]).strip().lower()
        if value not in LINE_NAMES:
            warn(option, value, defaults[option])
            value = defaults[option]
        lines[option] = value

    raw_time = section.get("time", "").strip()
    if raw_time:
        try:
            cycle_time = int(raw_time)
            if cycle_time < MIN_CYCLE_TIME:
                raise ValueError
        except ValueError:
            warn("time", raw_time, "{} seconds".format(fallback_time))
            cycle_time = fallback_time
    else:
        cycle_time = fallback_time

    return CycleConfig(
        name=name,
        enabled=bool(enabled),
        top_line=lines["top_line"],
        bottom_line=lines["bottom_line"],
        small_icon=bool(small_icon),
        time=cycle_time,
    )


def load_config(path: Optional[str] = None) -> Config:
    """Load the user's config, falling back to defaults for anything missing.

    ``path`` overrides the search; otherwise %APPDATA%\\FetchCord is used when
    a config has been written there.
    """
    parser = configparser.ConfigParser()
    parser.read_dict(DEFAULTS)

    warnings: List[str] = []
    candidates = [path] if path else [config_path()]

    for candidate in candidates:
        if not candidate:
            continue
        if not os.path.exists(candidate):
            if path:
                warnings.append("config: {} does not exist, using defaults".format(candidate))
            continue
        try:
            parser.read(candidate, encoding="utf-8")
        except (configparser.Error, OSError) as error:
            warnings.append("config: could not read {} ({}), using defaults".format(candidate, error))

    general = parser["general"] if parser.has_section("general") else {}

    try:
        poll_rate = int(general.get("poll_rate", DEFAULTS["general"]["poll_rate"]))
        if poll_rate < 1:
            raise ValueError
    except ValueError:
        warnings.append("config: invalid poll_rate, using {}".format(DEFAULT_POLL_RATE))
        poll_rate = DEFAULT_POLL_RATE

    try:
        default_time = int(general.get("time", DEFAULTS["general"]["time"]))
        if default_time < MIN_CYCLE_TIME:
            raise ValueError
    except ValueError:
        warnings.append(
            "config: invalid time, using {} seconds (minimum is {})".format(
                DEFAULT_CYCLE_TIME, MIN_CYCLE_TIME
            )
        )
        default_time = DEFAULT_CYCLE_TIME

    for section in parser.sections():
        if section not in DEFAULTS:
            warnings.append('config: unknown section [{}], ignoring'.format(section))

    pause_when = [
        name.strip()
        for name in general.get("pause_when", "").replace(";", ",").split(",")
        if name.strip()
    ]

    buttons = _buttons_from_section(
        dict(parser["buttons"]) if parser.has_section("buttons") else {}, warnings
    )

    cycles = {
        name: _cycle_from_section(
            name,
            dict(parser[name]) if parser.has_section(name) else {},
            default_time,
            warnings,
        )
        for name in CYCLE_NAMES
    }

    return Config(
        poll_rate=poll_rate,
        cycles=cycles,
        warnings=warnings,
        pause_when=pause_when,
        buttons=buttons,
    )
