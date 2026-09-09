"""FetchCord entry point."""

import sys

from . import __version__, config as config_module
from .args import parse_args
from .config import MIN_CYCLE_TIME, load_config
from .cycles import build_payloads
from .ids import IdTable
from .presence import PresenceRunner
from .system import collect, platforms
from .system.info import LINE_NAMES
from .update import update

# Command line flags that switch off a cycle from the config.
_DISABLED_BY = {
    "os": "no_os",
    "hardware": "no_hardware",
    "host": "no_host",
    "terminal": "no_terminal",
}


def _require_supported_platform() -> bool:
    if platforms.SUPPORTED:
        return True

    print(
        "FetchCord {} has no collector for {} yet - supported platforms are "
        "Windows and Linux.".format(__version__, platforms.name())
    )

    return False


def _print_dry_run(payloads, info, warnings):
    print("FetchCord {} - dry run, nothing was sent to Discord.\n".format(__version__))

    for warning in warnings:
        print(warning)
    if warnings:
        print()

    print("Detected:")
    for name in LINE_NAMES:
        print("  {:<11} {}".format(name, info.line(name)))

    if not payloads:
        print("\nNo cycles would be shown.")
        return

    print("\nCycles:")
    for payload in payloads:
        print("  [{}] application {} for {}s".format(payload.name, payload.client_id, payload.seconds))
        for key, value in payload.as_update().items():
            print("      {:<12} {}".format(key, value))


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.update:
        return update()

    if args.gen_config:
        path = config_module.write_default_config()
        print("Config: {}".format(path))
        return 0

    if args.install_startup or args.uninstall_startup or args.startup_status:
        if not _require_supported_platform():
            return 1

        from . import startup

        if args.install_startup:
            print("FetchCord will start at sign-in: {}".format(startup.install()))
        elif args.uninstall_startup:
            print("Autostart removed." if startup.uninstall() else "Autostart was not set up.")
        else:
            current = startup.status()
            print("Autostart: {}".format(current if current else "not set up"))

        return 0

    if not _require_supported_platform():
        return 1

    if args.time is not None and args.time < MIN_CYCLE_TIME:
        print("ERROR: --time must be at least {} seconds.".format(MIN_CYCLE_TIME))
        return 1

    config = load_config(args.config)
    for warning in config.warnings:
        print(warning)

    info = collect(memory_unit=args.memtype or "gb")
    ids = IdTable()

    cycles = []
    for cycle in config.cycles.values():
        enabled = cycle.enabled
        if getattr(args, _DISABLED_BY[cycle.name], False):
            enabled = False
        if cycle.name == "terminal" and args.with_terminal:
            enabled = True
        if enabled:
            cycles.append(cycle)

    # Keep the configured display order.
    cycles.sort(key=lambda cycle: config_module.CYCLE_NAMES.index(cycle.name))

    if args.dry_run:
        _print_dry_run(build_payloads(cycles, info, ids), info, config.warnings)
        return 0

    if not cycles:
        print("ERROR: every cycle is disabled, there is nothing to show.")
        return 1

    runner = PresenceRunner(
        info,
        ids,
        cycles,
        poll_rate=args.poll_rate or config.poll_rate,
        time_override=args.time,
        pause=args.pause_cycle,
        debug=args.debug,
    )

    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
