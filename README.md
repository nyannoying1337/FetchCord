<h1 align="center">FetchCord</h1>

<p align="center">
    <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-brightgreen?style=for-the-badge&logo=windows&logoColor=white">
    <img src="https://img.shields.io/badge/python-3.9%2B-blue?style=for-the-badge&logo=python&logoColor=white">
    <img src="https://img.shields.io/badge/license-MIT-lightgrey?style=for-the-badge">
</p>

<p align="center">
    Shows your system info as Discord Rich Presence.
</p>

FetchCord rotates through a few "cycles" on your Discord profile: your Windows
version, your CPU and GPU, and your PC. Each cycle shows up under its own
Discord application, so your profile reads *Playing Windows 11*, then
*Playing Ryzen 7*, and so on.

## What's new

**3.3** adds `pause_when` so a game or Spotify keeps its own status instead of
being replaced by your system info, shows your desktop environment's icon on
Linux, adds optional profile buttons, and adds `--report-hardware` for filing
issues about unrecognised hardware.

**3.2 brings macOS back.** One `sysctl` call and CoreGraphics through ctypes -
no `system_profiler`, which takes about a second to answer. All three
platforms are supported again.

**3.1 brought Linux back**, natively - no neofetch. Everything comes from
`/proc`, `/sys` and `/etc/os-release`, so there is nothing to install beyond
FetchCord itself, and all 29 distro icons the id table carries work again.

**3.0 was a Windows-only rewrite.**

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

## Requirements

- Windows 7 or newer, any current Linux distribution, or macOS 10.13+
- Python 3.9+
- The **Discord desktop client**, running. Rich Presence does not exist in the
  browser version, and on Linux the Flatpak build needs the socket exposed
  (see Troubleshooting).

## Install

```
python -m pip install fetchcord
```

Or straight from this repository:

```
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

```
fetchcord --install-startup     # start at sign-in
fetchcord --startup-status      # check what's registered
fetchcord --uninstall-startup   # stop
```

Same flags on both platforms; each uses the mechanism its users expect.

- **Windows** - one value under
  `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`, using
  the windowless launcher so no console appears.
- **Linux** - a systemd user service at
  `~/.config/systemd/user/fetchcord.service`, enabled with
  `systemctl --user enable --now`.
- **macOS** - a launch agent at
  `~/Library/LaunchAgents/com.github.fetchcord.plist`, loaded with
  `launchctl load`.

Neither needs administrator or root rights, and neither touches anything
outside your own user account.

## Configuration

```
fetchcord --gen-config
```

writes a commented config to `%APPDATA%\FetchCord\fetch_cord.conf` on Windows,
or `~/.config/FetchCord/fetch_cord.conf` on Linux and macOS. Open it in any editor. Use
`--config PATH` to point at a different file.

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
| `os` | `Windows 11 Pro 24H2 x86_64` / `Ubuntu 24.04 x86_64` / `macOS Sonoma 14.5 arm64` |
| `kernel` | `10.0.26100.4652` / `6.11.0-9-generic` |
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
| `desktop` | `KDE` (Linux) |
| `wm` | `i3` (Linux) |

The four cycles are `[os]`, `[hardware]`, `[host]` and `[terminal]`. The
terminal cycle is off by default, since it only makes sense when you start
FetchCord from a terminal you keep open.

A typo in the config is reported on startup and the default is used - it will
never stop FetchCord from running.

### Let other programs keep their status

FetchCord's presence replaces whatever else Discord would show, so a game or
Spotify loses its status while FetchCord is running. List the programs that
should win:

```ini
[general]
pause_when = steam.exe, r5apex.exe, Spotify.exe
```

While any of them is running FetchCord shows nothing at all, and it resumes on
its own once they close. Names match with or without `.exe`, so one line works
on every platform.

### Profile buttons

Up to two clickable buttons on your profile:

```ini
[buttons]
label_1 = GitHub
url_1 = https://github.com/nyannoying1337/FetchCord
```

Labels are limited to 32 characters and URLs must be `https://`. Discord does
**not** draw these when you look at your own profile — other people see them.

## Arguments

| Argument | What it does |
| --- | --- |
| `--dry-run` | Print what would be sent to Discord, then exit |
| `--report-hardware` | Print a hardware report to paste into an issue, then exit |
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

On Linux, a **Flatpak** Discord keeps its IPC socket inside the sandbox. Either
link it out once:

```
ln -sf {XDG_RUNTIME_DIR:-/run/user/$UID}/app/com.discordapp.Discord/discord-ipc-0 \
       ${XDG_RUNTIME_DIR:-/run/user/$UID}/discord-ipc-0
```

or install Discord from your distribution's packages instead.

**Nothing shows on my profile** - check Discord's *Settings → Activity Privacy
→ Share your detected activities with others*.

**My CPU, GPU or motherboard says "Unknown"** - run `fetchcord --report-hardware`
and open an issue with the output. It lists the raw strings we read and which
ones fell back to a generic application, which is exactly what's needed to add
them. FetchCord still shows the full model name as
text; only the icon and the application name fall back to a generic one.
`fetchcord --update` pulls the latest id database without upgrading FetchCord.

**Some hardware is missing entirely** - `--dry-run` shows every detected line.
Anything reading `N/A` couldn't be read from this machine; include that output
in the issue.

On Linux specifically: `host` and `board` come from the DMI tables, which
containers don't expose; `resolution` needs a DRM connector, so it is blank on
headless machines; and GPU *model* names need `pci.ids` (`hwdata` on most
distros) - without it you get the vendor, which is all the icon needs anyway.

On macOS: Apple Silicon reports its GPU as part of the chip, but Intel Macs
show `gpu` as `N/A` - reading it would mean running `system_profiler`, which
is far too slow to run at startup. Apple Silicon chips and macOS releases also
have no Discord applications yet (see below), so they use the generic one.

## Hardware still needing Discord applications

Everything on Windows and Linux resolves to an existing application. macOS
does not, because the applications 2.x used belong to the upstream author:

- **Apple Silicon** (M1-M4 and their Pro/Max/Ultra variants). Add them under
  `"apple"` in the `cpu` section of `fetchcord_ids.json`; a variant with no
  entry of its own falls back to the base chip, so `"m4"` alone covers an M4
  Max.
- **macOS releases.** Add `"macos": "<application id>"` to the `distro`
  section.

Until those exist the generic application is used, and the real model name is
still shown as text.

## Adding your hardware

Icons and application names come from
[`fetch_cord/resources/fetchcord_ids.json`](fetch_cord/resources/fetchcord_ids.json).
Matching lives in `fetch_cord/system/naming.py` (raw string → lookup key) and
`fetch_cord/ids.py` (lookup key → Discord application id and icon).

Reading the machine is one module per platform under
`fetch_cord/system/platforms/`, each exposing a single `collect(info)`.
Everything above them is platform-neutral.

All of it is covered by tests that run anywhere, by faking each platform's
boundary - the registry on Windows, captured sysfs trees under
`tests/fixtures/linux/`, and `sysctl` plus CoreGraphics on macOS:

```
python -m unittest discover -s tests -t .
```

## Examples

### Operating systems
![Windows](Examples/windows.png)
### CPUs
![Ryzen 9](Examples/ryzencpu.png) ![Intel i7](Examples/intelcpu.png) ![Intel Pentium](Examples/pent.png)
### Hosts
![HP laptop](Examples/hp.png) ![TUF gaming laptop](Examples/tuf.png) ![Lenovo desktop](Examples/len.png)
