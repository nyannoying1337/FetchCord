"""Turning raw hardware strings into the keys FetchCord's id table uses.

These are pure functions on purpose: the Discord id lookups are the part most
likely to need tweaking when new hardware shows up, and keeping them free of
any Windows API calls means they can be tested on any machine.
"""

import re
from typing import Dict, List, Optional

# Marketing noise that shows up in registry CPU/GPU names.
_TRADEMARKS = re.compile(r"\((?:r|tm|c)\)", re.IGNORECASE)

_INTEL_CORE = re.compile(r"\bi([3579])\b")
_RYZEN = re.compile(r"\bryzen\s+([3579])\b")
_AMD_A_SERIES = re.compile(r"\ba(\d{1,2})\b")

# Strings firmware ships when the vendor never filled the field in.
_PLACEHOLDERS = {
    "",
    "to be filled by o.e.m.",
    "default string",
    "system product name",
    "system manufacturer",
    "system version",
    "system name",
    "not applicable",
    "not specified",
    "none",
    "o.e.m.",
    "unknown",
}

# os-release IDs that differ from the key the id table uses.
_DISTRO_ALIASES = {
    "pop": "pop!_os",
    "opensuse-leap": "opensuseleap",
    "opensuse-tumbleweed": "opensusetumbleweed",
    "gentoo": "gentoo/linux",
    "arcolinux": "arco",
    "parrot": "parrotos",
    "amzn": "amazon",
}

# Distro keys the id table carries. Mirrored here so the lookup can tell a
# usable candidate from a distro we have no application for; tests assert this
# stays in step with fetchcord_ids.json.
_DISTRO_KEYS = frozenset({
    "amazon",
    "arch",
    "arco",
    "artix",
    "bedrock",
    "centos",
    "debian",
    "elementary",
    "endeavouros",
    "fedora",
    "freebsd",
    "funtoo",
    "garuda",
    "gentoo/linux",
    "instantos",
    "linuxmint",
    "lmde",
    "mageia",
    "manjaro",
    "nixos",
    "opensuseleap",
    "opensusetumbleweed",
    "parrotos",
    "pop!_os",
    "rebornos",
    "solus",
    "ubuntu",
    "void",
    "zorin",
})

# macOS releases. Apple moved from 10.x to whole numbers with Big Sur, and
# again to year-based numbering with Tahoe.
_MACOS_CODENAMES = {
    "10.13": "High Sierra",
    "10.14": "Mojave",
    "10.15": "Catalina",
    "11": "Big Sur",
    "12": "Monterey",
    "13": "Ventura",
    "14": "Sonoma",
    "15": "Sequoia",
    "26": "Tahoe",
}

_APPLE_CHIP = re.compile(r"\bapple\s+(m\d+)(?:\s+(pro|max|ultra))?", re.IGNORECASE)

# PCI vendor ids for display adapters.
_PCI_VENDORS = {
    "0x10de": "nvidia",
    "0x1002": "amd",
    "0x1022": "amd",
    "0x8086": "intel",
    "0x15ad": "vmware",
    "0x1af4": "virtio",
    "0x1013": "cirrus",
}


def clean(value: str) -> str:
    """Strip trademark markers and collapse whitespace."""
    if not value:
        return ""

    # Substituting with "" (not a space) keeps "FX(tm)-8350" as "FX-8350".
    return " ".join(_TRADEMARKS.sub("", value).split())


def cpu_model(raw: str) -> str:
    """A short, human-readable CPU name for display.

    Registry names carry a lot of boilerplate ("8-Core Processor", "CPU @
    2.60GHz"); Discord only gives us one line, so trim it down.
    """
    model = clean(raw)
    if not model:
        return ""

    # Drop everything from the clock speed or core count onwards.
    model = re.split(r"\s+(?:CPU\s+)?@\s+", model)[0]
    model = re.sub(r"\s+\d+-Core Processor\b.*$", "", model, flags=re.IGNORECASE)
    model = re.sub(r"\s+(?:Eight|Six|Quad|Dual)-Core Processor\b.*$", "", model, flags=re.IGNORECASE)
    model = re.sub(r"\s+with Radeon.*$", "", model, flags=re.IGNORECASE)
    model = re.sub(r"\s*,?\s*\d+\s+COMPUTE CORES.*$", "", model, flags=re.IGNORECASE)
    model = re.sub(r"\s+RADEON R\d\b.*$", "", model, flags=re.IGNORECASE)
    model = re.sub(r"\s+Processor\b\s*$", "", model, flags=re.IGNORECASE)
    model = re.sub(r"\bCPU\b", "", model, flags=re.IGNORECASE)
    # "Core(TM)2 Duo" cleans up to "Core2 Duo"; space it out for display.
    model = re.sub(r"\bCore2\b", "Core 2", model, flags=re.IGNORECASE)

    return " ".join(model.split()).strip(" ,")


def cpu_vendor(raw: str) -> str:
    """'intel', 'amd' or 'unknown' for a raw CPU name or vendor id."""
    value = clean(raw).lower()

    if "genuineintel" in value or "intel" in value or "pentium" in value:
        return "intel"
    if "authenticamd" in value or "amd" in value or "ryzen" in value:
        return "amd"
    if "apple" in value:
        return "apple"

    return "unknown"


def cpu_family(raw: str) -> Optional[str]:
    """The id-table key for a CPU, or None when we don't recognise it.

    Keys match the ``cpu`` section of fetchcord_ids.json. An unrecognised CPU
    is not an error: the caller falls back to the generic id, and the model
    name is still shown in full.
    """
    value = clean(raw).lower()
    if not value:
        return None

    vendor = cpu_vendor(value)

    if vendor == "intel":
        # "Core(TM)2 Duo" cleans up to "core2 duo".
        if re.search(r"\bcore\s*2\s+duo\b", value):
            return "intel core 2 duo"
        if re.search(r"\bcore\s*2\s+quad\b", value):
            return "intel core 2 quad"
        if "xeon" in value:
            return "intel xeon"
        if "celeron" in value:
            return "intel celeron"
        if "pentium" in value:
            return "intel pentium"

        core = _INTEL_CORE.search(value)
        if core:
            return "intel i{}".format(core.group(1))

        # Core Ultra and other newer families have no id of their own yet;
        # they fall through to the generic CPU app rather than borrowing a
        # Core i logo that would be wrong on the user's profile.
        return None

    if vendor == "apple":
        chip = _APPLE_CHIP.search(value)
        if chip:
            # "Apple M4 Max" -> "m4 max", falling back to "m4" so a variant
            # still resolves when only the base chip has an application.
            return " ".join(part for part in chip.groups() if part).lower()

        return None

    if vendor == "amd":
        if "threadripper" in value:
            return "ryzen threadripper"

        ryzen = _RYZEN.search(value)
        if ryzen:
            return "ryzen {}".format(ryzen.group(1))

        if "athlon silver" in value:
            return "athlon silver"
        if "athlon gold" in value:
            return "athlon gold"
        if re.search(r"\bfx\b", value):
            return "fx apu"

        a_series = _AMD_A_SERIES.search(value)
        if a_series:
            return "a{} apu".format(a_series.group(1))

    return None


def gpu_vendor(raw: str) -> Optional[str]:
    """Vendor key for a single display adapter, or None if it isn't a real GPU."""
    value = clean(raw).lower()
    if not value:
        return None

    if "nvidia" in value or "geforce" in value or "quadro" in value:
        return "nvidia"
    if "amd" in value or "radeon" in value or "ati " in value:
        return "amd"
    if "intel" in value:
        return "intel"
    if "vmware" in value:
        return "vmware"
    if "virtio" in value or "red hat" in value:
        return "virtio"
    if "cirrus" in value:
        return "cirrus"

    # Microsoft Basic Display Adapter / Remote Desktop adapters and friends:
    # real entries, but not something we have an icon for.
    return None


def gpu_vendors(names: List[str]) -> List[str]:
    """Ordered, de-duplicated vendor keys for a list of adapter names."""
    vendors: List[str] = []
    for name in names:
        vendor = gpu_vendor(name)
        if vendor and vendor not in vendors:
            vendors.append(vendor)

    return vendors


def windows_key(product_name: str, build: int) -> str:
    """The distro-table key for this Windows release.

    The build number is authoritative: Windows 11 still reports a ProductName
    of "Windows 10 Pro" in the registry, so the name alone would be wrong.
    """
    if build >= 22000:
        return "windows11"
    if build >= 10240:
        return "windows10"

    name = clean(product_name).lower()
    if "8.1" in name:
        return "windows8.1"
    if "windows 8" in name:
        return "windows8"
    if "windows 7" in name:
        return "windows7"
    if "windows 10" in name:
        return "windows10"

    return "unknown"


def windows_name(product_name: str, build: int) -> str:
    """Display name for the running Windows release.

    Rewrites the registry's stale "Windows 10" on Windows 11 builds while
    keeping the edition ("Pro", "Home", ...) intact.
    """
    name = clean(product_name) or "Windows"

    if build >= 22000 and "windows 10" in name.lower():
        name = re.sub(r"windows 10", "Windows 11", name, flags=re.IGNORECASE)

    return name


def format_bytes(value: int, unit: str = "gb") -> str:
    """Render a byte count as GiB (default) or MiB."""
    if unit == "mb":
        return "{:.0f} MiB".format(value / (1024**2))

    return "{:.2f} GiB".format(value / (1024**3))


def strip_placeholder(value: str) -> str:
    """Blank out a firmware field the vendor left as boilerplate."""
    if not isinstance(value, str):
        return ""

    value = value.strip()

    return "" if value.lower() in _PLACEHOLDERS else value


def looks_like_a_name(value: str) -> bool:
    """Whether a firmware string reads as a product name rather than a code.

    "ThinkPad T14 Gen 1" does; "20UD0013US" and "1.0" do not.
    """
    value = strip_placeholder(value)

    return bool(value) and " " in value and any(c.isalpha() for c in value)


def linux_distro_key(values: Dict[str, str]) -> str:
    """The distro-table key for a parsed /etc/os-release."""
    for candidate in _distro_key_candidates(values):
        candidate = _DISTRO_ALIASES.get(candidate.strip().lower(), candidate.strip().lower())
        # A derivative we have no icon for falls through to what it is based
        # on, rather than naming an application that doesn't exist.
        if candidate in _DISTRO_KEYS:
            return candidate

    return "unknown"


def _distro_key_candidates(values: Dict[str, str]) -> List[str]:
    candidates = [values.get("ID", "")]
    # ID_LIKE lets a derivative fall back to what it is based on.
    candidates.extend((values.get("ID_LIKE") or "").split())
    name = (values.get("NAME") or "").lower()
    candidates.append(name.replace(" ", ""))
    # "Zorin OS" -> "zorin"
    candidates.append(name.split()[0] if name.split() else "")

    return candidates


def pci_vendor(vendor_id: str) -> Optional[str]:
    """Vendor key for a PCI vendor id such as "0x10de"."""
    return _PCI_VENDORS.get((vendor_id or "").strip().lower())


def macos_version_key(version: str) -> str:
    """The release key for a macOS version string.

    Big Sur onwards are numbered whole, so "14.5" keys on "14"; the 10.x
    releases need the minor part to be told apart.
    """
    version = (version or "").strip()
    if not version:
        return ""

    parts = version.split(".")
    if parts[0] == "10":
        return ".".join(parts[:2])

    return parts[0]


def macos_codename(version: str) -> str:
    """"14.5" -> "Sonoma", or "" for a release we don't know."""
    return _MACOS_CODENAMES.get(macos_version_key(version), "")


def macos_name(version: str) -> str:
    """The display name for a macOS release, e.g. "macOS Sonoma"."""
    codename = macos_codename(version)

    return "macOS {}".format(codename) if codename else "macOS"


def cpu_family_fallbacks(family: Optional[str]) -> List[str]:
    """Lookup keys to try for a CPU family, most specific first.

    Chips with a variant suffix fall back to the base chip, so a table
    carrying only "m4" still gives an M4 Max the right application.
    """
    if not family:
        return []

    parts = family.split()

    return [family, parts[0]] if len(parts) > 1 else [family]
