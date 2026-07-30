"""Shared loader plumbing: locating exports and applying the denylist.

The denylist lives here rather than in CPI on purpose. CPI's job is to report what
the archive says; hiding rows is a presentation choice, and putting it upstream
would mean the library lies about the data it was given.
"""

import os
import sys
from pathlib import Path

SERVICE_NAMES = {0: "YouTube", 5: "bilibili", 6: "niconico"}

# Sits next to the loaders, gitignored. See blocked.example.txt.
BLOCKLIST = Path(__file__).parent / "blocked.txt"


def exports() -> str:
    """Where the archived exports are, or exit.

    Loaders run at build time with no terminal, so this must fail rather than
    return nothing: an empty dataset renders as a plausible "nothing watched".
    """
    value = os.environ.get("CPI_PIPEPIPE_EXPORTS")
    if not value:
        sys.exit(
            "CPI_PIPEPIPE_EXPORTS is not set; point it at archived PipePipe exports"
        )
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
