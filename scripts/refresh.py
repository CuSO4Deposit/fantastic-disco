"""Re-run loaders when their local configuration changed behind Framework's back.

Framework treats a cached loader output as fresh whenever it is newer than the loader
script, and knows nothing about files a loader reads or environment it consults at run
time. The uploader denylist and the fandom keyword list are both exactly that, so
without this the page would keep showing uploaders that were just excluded — the one
failure these features must not have. So is `CPI_LOCAL_TZ`, where a stale cache is
worse than a visible error: every daily total remains a plausible number, just cut on
the wrong boundary.

Comparing mtimes is not enough, because *deleting* a config file has to restore the
full data just as reliably as adding one narrows it. So the effective configuration is
recorded and compared by value.

Runs from `prebuild`/`predev`, before Framework looks at any timestamps.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
CACHE = SRC / ".observablehq" / "cache"
# Gitignored alongside the cache it describes.
STAMP = SRC / ".observablehq" / "config.stamp"

sys.path.insert(0, str(SRC / "lib"))
sys.path.insert(0, str(SRC / "video" / "data"))
import fandoms  # noqa: E402
from _shared import blocklist_fingerprint  # noqa: E402

# Environment that changes what a loader emits. Framework cannot see these any more
# than it can see a config file: the loader script's mtime does not move when they do.
# `CPI_LOCAL_TZ` decides which local midnight splits a day, so changing it changes
# every daily figure while leaving all of them looking equally plausible. The export
# paths are here for the same reason — pointing them at a different archive must not
# serve the previous archive's cached output.
TRACKED_ENV = (
    "CPI_LOCAL_TZ",
    "CPI_PIPEPIPE_EXPORTS",
    "CPI_GADGETBRIDGE_EXPORTS",
)


def fingerprint() -> str:
    """Every run-time input that changes what the loaders emit."""
    return "\n".join(
        [
            "[denylist]",
            blocklist_fingerprint(),
            "[fandoms]",
            fandoms.fingerprint(),
            "[env]",
            *(f"{name}={os.environ.get(name, '')}" for name in TRACKED_ENV),
        ]
    )


def main() -> None:
    current = fingerprint()
    previous = STAMP.read_text(encoding="utf-8") if STAMP.exists() else ""
    if current == previous:
        return

    # Loaders live beside the pages that use them, so search the whole tree.
    for loader in sorted(SRC.rglob("*.json.py")):
        # Bumping the loader's mtime is what `preview` looks at; dropping the cached
        # file covers `build`, which ignores timestamps and only asks whether the
        # output is already cached.
        loader.touch()
        cached = CACHE / loader.relative_to(SRC).with_suffix("")
        cached.unlink(missing_ok=True)

    STAMP.parent.mkdir(parents=True, exist_ok=True)
    STAMP.write_text(current, encoding="utf-8")
    print("local configuration changed, re-running loaders", file=sys.stderr)


if __name__ == "__main__":
    main()
