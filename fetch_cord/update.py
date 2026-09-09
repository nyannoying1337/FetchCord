"""Refreshing the hardware id database.

The updated copy is written next to the user's config rather than into the
installed package, so it works without administrator rights and survives
reinstalling FetchCord.
"""

import json
import os
import urllib.error
import urllib.request

from .config import config_dir
from .ids import IDS_FILE

IDS_URL = (
    "https://raw.githubusercontent.com/nyannoying1337/FetchCord/master/"
    "fetch_cord/resources/fetchcord_ids.json"
)

TIMEOUT = 15


def user_ids_path() -> str:
    return os.path.join(config_dir(), IDS_FILE)


def update() -> int:
    """Download a fresh id database. Returns a process exit code."""
    print("Updating hardware id database from {}...".format(IDS_URL))

    try:
        with urllib.request.urlopen(IDS_URL, timeout=TIMEOUT) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, OSError, UnicodeDecodeError) as error:
        print("ERROR: could not download the id database: {}".format(error))
        return 1

    # Only replace the local copy once we know the download parses, so a bad
    # response can't leave FetchCord unable to start.
    try:
        data = json.loads(body)
    except json.JSONDecodeError as error:
        print("ERROR: downloaded id database is not valid JSON: {}".format(error))
        return 1

    if "map" not in data:
        print("ERROR: downloaded id database is missing the 'map' section.")
        return 1

    target = user_ids_path()
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=1)
    except OSError as error:
        print("ERROR: could not write {}: {}".format(target, error))
        return 1

    print("Saved {} ({} sections).".format(target, len(data)))

    return 0
