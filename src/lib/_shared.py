"""Shared loader plumbing: locating exports and applying the denylist.

The denylist lives here rather than in CPI on purpose. CPI's job is to report what
the archive says; hiding rows is a presentation choice, and putting it upstream
would mean the library lies about the data it was given.
"""

import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SERVICE_NAMES = {0: "YouTube", 5: "bilibili", 6: "niconico"}


def die(message: str) -> None:
    """Exit non-zero, naming the loader that failed.

    Framework reports a failed loader as `loader exited with code 1` plus whatever went
    to stderr, and nothing in its traceback says which loader that was. With nine of
    them reading `CPI_LOCAL_TZ`, a bare "not set" leaves the reader to guess whether the
    band, Firefox or rhythm pages asked for it — and therefore which of several
    variables they actually need.

    `sys.argv[0]` is the loader's own path, which Framework invokes directly. Public
    rather than underscored because loaders and their helper modules call it too, for
    failures that are theirs rather than a missing variable's.
    """
    who = Path(sys.argv[0]).name or "loader"
    sys.exit(f"{who}: {message}")


def local_tz() -> ZoneInfo:
    """Which local midnight splits a day, or exit.

    Configuration rather than a constant, and for the same reason the denylist is:
    where someone sleeps is personal, and a tracked default would publish it. So
    would the evidence for one — a note reading "the quiet block runs 01:00 to
    09:00" describes a daily routine, whatever timezone it justifies.

    Not the build machine's timezone either, which is UTC on this one. That would
    put the day boundary at 08:00 local, mid-morning, cutting every night in half.
    And not CPI's business: it reports what the archive says, and the archive is
    in UTC.

    Fails rather than defaulting to UTC, because a wrong boundary does not look
    wrong. Every daily total stays a plausible number; the sleep ones are just
    quietly split across two dates.
    """
    value = os.environ.get("CPI_LOCAL_TZ")
    if not value:
        die(
            "CPI_LOCAL_TZ is not set; set it to the IANA zone the data was "
            "recorded in, e.g. CPI_LOCAL_TZ=Asia/Tokyo. Every source except video "
            "needs it — see the environment table in README.md"
        )
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        die(f"CPI_LOCAL_TZ={value!r} is not a known IANA timezone")


# Sits next to the loaders, gitignored. See blocked.example.txt.
BLOCKLIST = Path(__file__).parent / "blocked.txt"


def exports(var: str = "CPI_PIPEPIPE_EXPORTS", what: str = "PipePipe exports") -> str:
    """Where the archived exports are, or exit.

    Loaders run at build time with no terminal, so this must fail rather than
    return nothing: an empty dataset renders as a plausible "nothing watched", or
    an equally plausible "never wore the band".
    """
    value = os.environ.get(var)
    if not value:
        die(f"{var} is not set; point it at archived {what}")
    return value


def blocked_uploaders() -> frozenset[str]:
    """Uploader names to leave out of the generated data, matched exactly.

    Exact matching keeps this predictable: a substring rule would silently take out
    unrelated channels as the archive grows.
    """
    if not BLOCKLIST.exists():
        return frozenset()
    names = set()
    for line in BLOCKLIST.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.add(line)
    return frozenset(names)


def blocklist_fingerprint() -> str:
    """The effective denylist as text, for detecting changes between runs.

    Framework only compares a cached output's mtime against its loader script, and
    knows nothing about files a loader reads at runtime. `scripts/refresh.py` uses
    this to notice denylist edits and drop the affected cache entries.

    By value rather than by mtime, so that deleting the denylist restores the full
    data as reliably as adding one hides part of it.
    """
    return "\n".join(sorted(blocked_uploaders()))


def env_path(var: str, what: str) -> Path:
    """A path from the environment that must exist, or exit.

    Separate from `exports` because these are single files rather than a glob, and
    because a missing chart catalogue has a distinct failure mode: Y-Offline reads a
    chart's rating and note count from it, and every rating band, accuracy and
    potential figure is derived from those. Pointing at a catalogue that is not there
    must stop the build rather than yield a page of empty bands.
    """
    value = os.environ.get(var)
    if not value:
        die(f"{var} is not set; point it at {what}")
    path = Path(value).expanduser()
    if not path.exists():
        die(f"{var}={value!r} does not exist; expected {what}")
    return path


def rhythm_db() -> Path:
    """The Y-Offline score database, or exit.

    Its own variable rather than a path under the exports glob: Y-Offline writes this
    database live from the `y` CLI, so it is not an archived export and does not
    accumulate one file per snapshot the way the band and Firefox archives do.
    """
    return env_path("YOFFLINE_DB", "the Y-Offline score database (y_offline.db)")


def rhythm_user() -> str:
    """Whose records to read.

    Every table there is keyed `(time, user)` and the reference database holds a second
    user with 40 rows, so a loader that ignored this would pool two players' records
    into one potential curve. No default: guessing wrong produces a complete-looking
    dashboard for the wrong person.
    """
    value = os.environ.get("YOFFLINE_USER")
    if not value:
        die("YOFFLINE_USER is not set; set it to the player whose records to read")
    return value
