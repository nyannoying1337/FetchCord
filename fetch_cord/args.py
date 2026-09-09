"""Command line arguments."""

import argparse

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fetchcord",
        description="Show your Windows system info as Discord Rich Presence.",
        epilog="https://github.com/nyannoying1337/FetchCord",
    )

    cycles = parser.add_argument_group("cycles")
    cycles.add_argument(
        "--no-os", action="store_true", help="Don't show the Windows version cycle."
    )
    cycles.add_argument(
        "--no-hardware", action="store_true", help="Don't show the CPU/GPU cycle."
    )
    cycles.add_argument(
        "--no-host", action="store_true", help="Don't show the PC/motherboard cycle."
    )
    cycles.add_argument(
        "--with-terminal",
        action="store_true",
        help="Show the terminal/shell cycle (off by default).",
    )
    cycles.add_argument(
        "--pause-cycle",
        "-p",
        action="store_true",
        help="Add a cycle that clears the presence, so other activities can show.",
    )
    # Pre-3.0 spellings, kept so existing shortcuts and scripts still work.
    cycles.add_argument("--nodistro", dest="no_os", action="store_true", help=argparse.SUPPRESS)
    cycles.add_argument("--nohardware", dest="no_hardware", action="store_true", help=argparse.SUPPRESS)
    cycles.add_argument("--nohost", dest="no_host", action="store_true", help=argparse.SUPPRESS)
    cycles.add_argument("--noshell", dest="no_terminal", action="store_true", help=argparse.SUPPRESS)

    display = parser.add_argument_group("display")
    display.add_argument(
        "--time",
        "-t",
        type=int,
        metavar="SECONDS",
        help="Seconds to show each cycle (minimum 15). Overrides the config file.",
    )
    display.add_argument(
        "--poll-rate",
        "-r",
        type=int,
        metavar="CYCLES",
        help="Refresh memory/disk/battery every N cycles.",
    )
    display.add_argument(
        "--memtype",
        "-m",
        choices=("gb", "mb"),
        help="Show memory in GiB (default) or MiB.",
    )

    config = parser.add_argument_group("configuration")
    config.add_argument(
        "--config", "-c", metavar="PATH", help="Use a specific config file."
    )
    config.add_argument(
        "--gen-config",
        action="store_true",
        help="Write a starter config to %%APPDATA%%\\FetchCord and exit.",
    )
    config.add_argument(
        "--update", action="store_true", help="Update the hardware id database and exit."
    )

    startup = parser.add_argument_group("startup")
    startup.add_argument(
        "--install-startup",
        action="store_true",
        help="Start FetchCord automatically when you sign in.",
    )
    startup.add_argument(
        "--uninstall-startup",
        action="store_true",
        help="Stop starting FetchCord automatically.",
    )
    startup.add_argument(
        "--startup-status", action="store_true", help="Show whether autostart is set up."
    )

    parser.add_argument(
        "--report-hardware",
        action="store_true",
        help="Print a hardware report to paste into a GitHub issue, and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be sent to Discord and exit, without connecting.",
    )
    parser.add_argument("--debug", "-d", action="store_true", help="Print debug output.")
    parser.add_argument(
        "--version", "-v", action="version", version="FetchCord {}".format(__version__)
    )

    return parser


def parse_args(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # --with-terminal wins over the suppressed --noshell alias.
    if args.with_terminal:
        args.no_terminal = False

    return args
