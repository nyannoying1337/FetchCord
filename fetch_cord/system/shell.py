"""Working out which terminal and shell FetchCord was started from.

The mechanism is the same everywhere - walk up the process tree and look for
names we recognise - so only the name tables differ per platform.
"""

from typing import Dict, List, Optional, Set

import psutil

MAX_DEPTH = 8


def parent_chain(limit: int = MAX_DEPTH) -> List[psutil.Process]:
    """Our ancestor processes, nearest first, or an empty list."""
    try:
        return psutil.Process().parents()[:limit]
    except Exception:
        return []


def detect(
    terminals: Dict[str, str],
    shells: Dict[str, str],
    ignore: Set[str],
    terminal: str = "",
    shell: str = "",
):
    """Return the (terminal, shell) we appear to be running under.

    ``terminal`` and ``shell`` seed the result from something already known -
    an environment variable, say - and are returned untouched if the walk finds
    nothing better.

    A process we can't inspect (it exited, or it belongs to another user) is
    skipped rather than abandoning the walk: one unreadable ancestor shouldn't
    lose the terminal sitting behind it.
    """
    for process in parent_chain():
        if terminal and shell:
            break

        try:
            name = process.name().lower()
        except Exception:
            continue

        if not shell and name in shells:
            shell = shells[name]
        elif not terminal and name in terminals:
            terminal = terminals[name]
            break
        elif name in ignore or name in shells:
            continue
        elif not terminal:
            # Something we have no name for; stop rather than guess.
            break

    return terminal, shell


def basename(path: Optional[str]) -> str:
    """The program name from a $SHELL-style path."""
    if not path:
        return ""

    return path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
