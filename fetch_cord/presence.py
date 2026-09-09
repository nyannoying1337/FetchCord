"""The Discord Rich Presence loop."""

import time
from typing import List, Optional

from pypresence import Presence, exceptions

from .cycles import Payload, build_payloads
from .ids import IdTable
from .system.info import SystemInfo

# Errors that mean "Discord isn't reachable right now" rather than "this
# request was wrong". These are worth waiting out.
#
# InvalidID must always be caught *before* this tuple: it is a subclass of
# DiscordError, and retrying a client id Discord has rejected would spin
# forever.
_CONNECTION_ERRORS = (
    exceptions.DiscordNotFound,
    exceptions.DiscordError,
    exceptions.InvalidPipe,
    exceptions.PipeClosed,
    exceptions.ResponseTimeout,
    exceptions.ConnectionTimeout,
    exceptions.ServerError,
    # Covers ConnectionReset/Refused, BrokenPipe and FileNotFound from the
    # named pipe itself.
    OSError,
)

RETRY_DELAYS = (5, 10, 20, 30, 60)
SLEEP_CHUNK = 1


class PresenceRunner:
    """Rotates through the configured cycles, one Discord app at a time."""

    def __init__(
        self,
        info: SystemInfo,
        ids: IdTable,
        cycles: List,
        poll_rate: int = 3,
        time_override: Optional[int] = None,
        pause: bool = False,
        debug: bool = False,
    ):
        self.info = info
        self.ids = ids
        self.cycles = cycles
        self.poll_rate = max(1, poll_rate)
        self.time_override = time_override
        self.pause = pause
        self.debug = debug

        self._rpc: Optional[Presence] = None
        self._client_id: Optional[str] = None
        self._warned_offline = False

    # -- plumbing --------------------------------------------------------

    def _log(self, message: str):
        if self.debug:
            print("[fetchcord] {}".format(message))

    def _sleep(self, seconds: int):
        """Sleep in short chunks so Ctrl+C is always responsive."""
        remaining = max(0, seconds)
        while remaining > 0:
            time.sleep(min(SLEEP_CHUNK, remaining))
            remaining -= SLEEP_CHUNK

    def disconnect(self):
        """Drop the current presence so it stops showing on the profile."""
        if self._rpc is None:
            return

        try:
            self._rpc.close()
        except Exception as error:  # closing a dead pipe should never be fatal
            self._log("close failed: {}".format(error))
        finally:
            self._rpc = None
            self._client_id = None

    def connect(self, client_id: str) -> bool:
        """Connect to Discord for ``client_id``, waiting for it if necessary."""
        if self._rpc is not None and self._client_id == client_id:
            return True

        self.disconnect()

        attempt = 0
        while True:
            try:
                rpc = Presence(client_id)
                rpc.connect()
            except exceptions.InvalidID:
                print(
                    "ERROR: Discord rejected application id {}. "
                    "Try 'fetchcord --update' to refresh the id database.".format(client_id)
                )
                return False
            except _CONNECTION_ERRORS as error:
                self._log("connect failed: {!r}".format(error))
                if not self._warned_offline:
                    print(
                        "Waiting for Discord... (is the desktop client running? "
                        "the browser version has no Rich Presence)"
                    )
                    self._warned_offline = True

                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                attempt += 1
                self._sleep(delay)
                continue

            self._rpc = rpc
            self._client_id = client_id
            if self._warned_offline:
                print("Connected to Discord.")
                self._warned_offline = False

            return True

    def show(self, payload: Payload) -> bool:
        """Push one cycle's presence, reconnecting once if the pipe died."""
        for attempt in range(2):
            if not self.connect(payload.client_id):
                return False

            try:
                self._log("{}: {}".format(payload.name, payload.as_update()))
                self._rpc.update(**payload.as_update())

                return True
            except exceptions.InvalidID:
                print(
                    "ERROR: Discord rejected application id {} for the {} cycle.".format(
                        payload.client_id, payload.name
                    )
                )
                return False
            except _CONNECTION_ERRORS as error:
                self._log("update failed ({}), reconnecting: {!r}".format(attempt, error))
                self.disconnect()

        return False

    # -- main loop -------------------------------------------------------

    def run(self):
        shown = 0

        try:
            while True:
                payloads = build_payloads(self.cycles, self.info, self.ids)
                if not payloads:
                    print("ERROR: nothing to show, all cycles are disabled or empty.")
                    return 1

                for payload in payloads:
                    seconds = self.time_override or payload.seconds
                    if self.show(payload):
                        self._sleep(seconds)

                    shown += 1
                    if shown % self.poll_rate == 0:
                        self.info.refresh()

                if self.pause:
                    self._log("pause cycle")
                    self.disconnect()
                    self._sleep(self.time_override or payloads[0].seconds)
        except KeyboardInterrupt:
            print("\nClosing connection.")

            return 0
        finally:
            self.disconnect()

        return 0
