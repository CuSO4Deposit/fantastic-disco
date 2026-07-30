"""Re-run loaders when the denylist changed behind Framework's back.

Framework treats a cached loader output as fresh whenever it is newer than the
loader script, and knows nothing about files a loader reads at runtime. The denylist
is exactly that, so without this the page would keep showing uploaders that were
just excluded — the one failure this feature must not have.

Comparing mtimes is not enough, because deleting the denylist has to restore the
full data just as reliably. So the effective list is recorded and compared by value.

Runs from `prebuild`/`predev`, before Framework looks at any timestamps.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
CACHE = SRC / ".observablehq" / "cache"
# Gitignored alongside the cache it describes.
STAMP = SRC / ".observablehq" / "denylist.stamp"

sys.path.insert(0, str(SRC / "lib"))
from _shared import blocklist_fingerprint  # noqa: E402


def main() -> None:
    current = blocklist_fingerprint()
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

    n = len(current.splitlines()) if current else 0
    print(f"denylist changed ({n} uploaders), re-running loaders", file=sys.stderr)


if __name__ == "__main__":
    main()
