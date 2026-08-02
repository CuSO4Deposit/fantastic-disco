"""Which sources this build actually includes.

The landing page cannot ask the filesystem itself — a page runs in the browser — and
Framework has no API for reading the configured nav from a page. So the question is
answered here, at build time, where the directories are visible.

Exists because the band pages are optional: `observable-cuso4d-build` deletes
`src/band/` when the band's environment is unset, and a card left pointing at pages
that were never rendered would fail the build on link validation.
"""

import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]

# Kept in step with `observablehq.config.js`, which builds the nav from the same facts.
# Duplicated rather than shared because the config is JS and this is Python; the pair
# is small and a mismatch fails the build loudly, since Framework validates every link.
SOURCES = [
    {
        "dir": "video",
        "name": "Video",
        "blurb": "Watch history, searches and subscriptions from PipePipe.",
        "pages": [
            {"name": "Overview", "path": "/video/"},
            {"name": "Fandoms", "path": "/video/fandoms"},
            {"name": "Raw", "path": "/video/raw"},
        ],
    },
    {
        "dir": "band",
        "name": "Band",
        "blurb": (
            "Steps, sleep, heart rate and stress from a fitness band, via Gadgetbridge."
        ),
        "pages": [
            {"name": "Overview", "path": "/band/"},
            {"name": "Sleep", "path": "/band/sleep"},
            {"name": "Device", "path": "/band/device"},
        ],
    },
    {
        "dir": "firefox",
        "name": "Firefox",
        "blurb": (
            "Browsing history, reading time, bookmarks and downloads, from archived "
            "copies of places.sqlite."
        ),
        "pages": [
            {"name": "Overview", "path": "/firefox/"},
            {"name": "Attention", "path": "/firefox/attention"},
            {"name": "Library", "path": "/firefox/library"},
        ],
    },
    {
        "dir": "rhythm",
        "name": "Rhythm",
        "blurb": (
            "Rhythm game scores recorded by hand in Y-Offline: where the standing "
            "stands, where the ceiling is, and how much of the rise was borrowed."
        ),
        "pages": [
            {"name": "Overview", "path": "/rhythm/"},
            {"name": "Charts", "path": "/rhythm/charts"},
            {"name": "Practice", "path": "/rhythm/practice"},
        ],
    },
]


def main() -> None:
    present = [s for s in SOURCES if (SRC / s["dir"]).is_dir()]
    if not present:
        sys.exit(
            "no source directories found under src/; refusing to build a bare site"
        )
    json.dump(present, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
