<h1 align="center">FetchCord</h1>

<p align="center">
    <img src="https://img.shields.io/badge/platform-Windows-brightgreen?style=for-the-badge&logo=windows&logoColor=white">
    <img src="https://img.shields.io/badge/python-3.9%2B-blue?style=for-the-badge&logo=python&logoColor=white">
    <img src="https://img.shields.io/badge/license-MIT-lightgrey?style=for-the-badge">
</p>

<p align="center">
    Shows your Windows system info as Discord Rich Presence.
</p>

FetchCord rotates through a few "cycles" on your Discord profile: your Windows
version, your CPU and GPU, and your PC. Each cycle shows up under its own
Discord application, so your profile reads *Playing Windows 11*, then
*Playing Ryzen 7*, and so on.

## What's new in 3.0

FetchCord 3.0 is a Windows-only rewrite.

- **No more neofetch.** Everything is read natively from the registry, a
  couple of Windows API calls and psutil. Neofetch was archived in 2024 and
  `neofetch-win` is unmaintained, so parsing their output was the main reason
  FetchCord stopped working.
- **Installing actually works.** Previous releases shipped a `setup.py` that
  left out every subpackage, so `pip install fetchcord` produced an import
  error on first run.
- **A broken config can't stop it starting.** Invalid values are reported and
  replaced with the default instead of raising.
- **Autostart without the Task Scheduler dance** - `fetchcord --install-startup`.
- **`--dry-run`** prints exactly what would be sent to Discord, which makes
  "why is my GPU not showing" a ten second question.

Linux and macOS support was removed rather than left broken; the last release
supporting them is 2.x (`pip install "fetchcord<3"`).

## Requirements

- Windows 7 or newer (developed and tested against Windows 10 and 11)
- Python 3.9+
- The **Discord desktop client**, running. Rich Presence does not exist in the
  browser version.

## Install

```powershell
python -m pip install fetchcord
```

Or straight from this repository:

```powershell
python -m pip install git+https://github.com/nyannoying1337/FetchCord
```

## Run

```powershell
fetchcord
```

That's it - no config needed. Leave it running and your profile updates every
30 seconds. `Ctrl+C` stops it and clears the presence.

To check what FetchCord detects on your machine without touching Discord:

```powershell
fetchcord --dry-run
```

### Start it automatically

```powershell
fetchcord --install-startup     # start at sign-in, no console window
fetchcord --startup-status      # check what's registered
fetchcord --uninstall-startup   # stop
```

This writes a single value under
`HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`. No
administrator rights, nothing outside your own user account.

## Configuration

```powershell
fetchcord --gen-config
```

writes a commented config to `%APPDATA%\FetchCord\fetch_cord.conf`. Open it in
any editor. Use `--config PATH` to point at a different file.

Each cycle picks two lines of text and an optional small icon:

```ini
[hardware]
enabled = on
top_line = cpu
bottom_line = gpu
small_icon = on
time = 30
```

Any of these values work as `top_line` or `bottom_line` in any cycle:

| Value | Example |
| --- | --- |
| `os` | `Windows 11 Pro 24H2 x86_64` |
| `kernel` | `10.0.26100.4652` |
| `uptime` | `3 hours, 12 mins` |
| `cpu` | `AMD Ryzen 7 5800X (16) @ 3.80GHz` |
| `gpu` | `NVIDIA GeForce RTX 4070` |
| `memory` | `12.40 GiB / 31.92 GiB` |
| `disk` | `410.22 GiB / 930.90 GiB (44%)` |
| `host` | `ASUSTeK COMPUTER INC. ROG STRIX` |
| `board` | `ASUSTeK COMPUTER INC. TUF GAMING X570-PLUS` |
| `resolution` | `2560x1440 @ 165Hz` |
| `battery` | `87% (charging)` |
| `terminal` | `Windows Terminal` |
| `shell` | `PowerShell 7` |

The four cycles are `[os]`, `[hardware]`, `[host]` and `[terminal]`. The
terminal cycle is off by default, since it only makes sense when you start
FetchCord from a terminal you keep open.

A typo in the config is reported on startup and the default is used - it will
never stop FetchCord from running.

## Arguments

| Argument | What it does |
| --- | --- |
| `--dry-run` | Print what would be sent to Discord, then exit |
| `--no-os`, `--no-hardware`, `--no-host` | Skip a cycle |
| `--with-terminal` | Show the terminal/shell cycle |
| `--pause-cycle`, `-p` | Add a cycle that clears the presence, so games show through |
| `--time`, `-t` | Seconds per cycle (minimum 15) |
| `--poll-rate`, `-r` | Refresh memory/disk/battery every N cycles |
| `--memtype`, `-m` | `gb` (default) or `mb` |
| `--config`, `-c` | Use a specific config file |
| `--gen-config` | Write a starter config and exit |
| `--install-startup`, `--uninstall-startup`, `--startup-status` | Autostart at sign-in |
| `--update` | Refresh the hardware id database |
| `--debug`, `-d` | Print every presence update |
| `--version`, `-v` | Print the version |

The old `--nodistro`, `--nohardware`, `--nohost` and `--noshell` spellings
still work.

## Troubleshooting

**"Waiting for Discord..."** - the desktop client isn't running, or you're
signed in through the browser. FetchCord keeps retrying, so just start Discord
and it will connect on its own.

**Nothing shows on my profile** - check Discord's *Settings → Activity Privacy
→ Share your detected activities with others*.

**My CPU, GPU or motherboard says "Unknown"** - run `fetchcord --dry-run` and
open an issue with the output. FetchCord still shows the full model name as
text; only the icon and the application name fall back to a generic one.
`fetchcord --update` pulls the latest id database without upgrading FetchCord.

**Some hardware is missing entirely** - `--dry-run` shows every detected line.
Anything reading `N/A` couldn't be read from this machine; include that output
in the issue.

## Adding your hardware

Icons and application names come from
[`fetch_cord/resources/fetchcord_ids.json`](fetch_cord/resources/fetchcord_ids.json).
Matching lives in `fetch_cord/system/naming.py` (raw string → lookup key) and
`fetch_cord/ids.py` (lookup key → Discord application id and icon). Both are
covered by tests you can run anywhere:

```powershell
python -m unittest discover -s tests -t .
```

## Examples

### Windows
![Windows](Examples/windows.png)
### CPUs
![Ryzen 9](Examples/ryzencpu.png) ![Intel i7](Examples/intelcpu.png) ![Intel Pentium](Examples/pent.png)
### Hosts
![HP laptop](Examples/hp.png) ![TUF gaming laptop](Examples/tuf.png) ![Lenovo desktop](Examples/len.png)
