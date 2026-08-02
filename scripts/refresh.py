"""Re-run loaders when their local configuration changed behind Framework's back.

Framework treats a cached loader output as fresh whenever it is newer than the loader
script, and knows nothing about files a loader reads or environment it consults at run
time. The uploader denylist and the fandom keyword list are both exactly that, so
without this the page would keep showing uploaders that were just excluded — the one
failure these features must not have. So is `CPI_LOCAL_TZ`, where a stale cache is
worse than a visible error: every daily total remains a plausible number, just cut on
the wrong boundary. The rhythm games add two more of the same kind: which chart
catalogue rates the plays, and which player's records are read.

Comparing mtimes is not enough, because *deleting* a config file has to restore the
full data just as reliably as adding one narrows it. So the effective configuration is
recorded and compared by value.

## Per source, not all at once

Each source gets its own fingerprint and its own stamp, and only its own loaders are
invalidated. A single stamp over everything looks simpler and is wrong: configuring one
source then drops every other source's cached output, and that output is not always
reproducible. A loader reads an archive that may not be mounted, or may have been
rotated away — the band buffers about a week and overwrites — so discarding a cached
result can destroy data no later build can recover. This is not hypothetical; it
happened here when the rhythm section was added.

An input shared between sources still invalidates all of them, because it genuinely
changed what each emits. `CPI_LOCAL_TZ` is the case that matters: band, Firefox and
rhythm all cut days on it. What this avoids is the *unrelated* invalidation — pointing
`ARCSONG_DB` somewhere new must not touch the band.

Runs from `prebuild`/`predev`, before Framework looks at any timestamps.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
CACHE = SRC / ".observablehq" / "cache"
# Gitignored alongside the cache it describes. A directory now rather than one file:
# one stamp per source, so a source whose configuration is untouched keeps its cache.
STAMPS = SRC / ".observablehq" / "stamps"
# Written by earlier versions of this script: `config.stamp` kept a single fingerprint
# for every source, and `denylist.stamp` predates even that, holding just the uploader
# denylist. Both are removed on the first run — a stale stamp nobody reads still sits
# there looking authoritative, and the denylist one holds personal names for no reason.
LEGACY_STAMPS = (
    SRC / ".observablehq" / "config.stamp",
    SRC / ".observablehq" / "denylist.stamp",
)

sys.path.insert(0, str(SRC / "lib"))
sys.path.insert(0, str(SRC / "video" / "data"))
sys.path.insert(0, str(SRC / "rhythm" / "data"))
from _shared import blocklist_fingerprint  # noqa: E402

# Both of these live inside a source's own directory, and a source directory is
# optional: `observable-cuso4d-build` deletes the ones whose environment is unset, so a
# machine archiving only some sources still publishes a site. Importing either
# unconditionally makes this script — which runs from `prebuild`, before Framework does
# anything — fail outright on such a machine, taking the whole build with it.
#
# Guarded rather than reordered: there is nothing to fingerprint for a source that is
# not being built, so an absent module is the correct answer and not a degraded one.
try:
    import fandoms
except ImportError:
    fandoms = None

try:
    import catalogues
except ImportError:
    catalogues = None


def _env(*names: str) -> list[str]:
    """Environment variables as `NAME=value` lines, absent ones included as empty.

    Included rather than skipped so that unsetting a variable changes the fingerprint
    as reliably as setting it — the same reason the config files are compared by value.
    """
    return [f"{name}={os.environ.get(name, '')}" for name in names]


def _video() -> list[str]:
    """The denylist and the fandom keywords, both of which only video reads."""
    return [
        "[denylist]",
        blocklist_fingerprint(),
        "[fandoms]",
        fandoms.fingerprint() if fandoms is not None else "",
        *_env("CPI_PIPEPIPE_EXPORTS"),
    ]


def _band() -> list[str]:
    return _env("CPI_LOCAL_TZ", "CPI_GADGETBRIDGE_EXPORTS")


def _firefox() -> list[str]:
    return _env("CPI_LOCAL_TZ", "CPI_FIREFOX_EXPORTS")


def _rhythm() -> list[str]:
    """The catalogues and the player, listed by `catalogues.fingerprint`.

    Delegated rather than spelled out here, so that adding a game means touching one
    file. `CPI_LOCAL_TZ` is added because the rhythm loaders split days on it too.
    """
    return [
        *_env("CPI_LOCAL_TZ"),
        "[catalogues]",
        catalogues.fingerprint() if catalogues is not None else "",
    ]


#: What each source's output depends on, beyond its own loader scripts. Keyed by the
#: directory under `src/`, which is also where its loaders live — so a fingerprint and
#: the files it governs cannot drift apart.
SOURCES = {
    "video": _video,
    "band": _band,
    "firefox": _firefox,
    "rhythm": _rhythm,
}


def fingerprint(source: str) -> str:
    """One source's run-time inputs, as text."""
    return "\n".join([f"[{source}]", *SOURCES[source]()])


def refresh(source: str) -> bool:
    """Invalidate `source`'s cached loader output if its configuration changed.

    Returns whether anything was invalidated. A source with no directory is skipped:
    the build command deletes those, and there is nothing of its to re-run.
    """
    directory = SRC / source
    if not directory.is_dir():
        return False

    current = fingerprint(source)
    stamp = STAMPS / f"{source}.stamp"
    if stamp.exists():
        previous = stamp.read_text(encoding="utf-8")
        if current == previous:
            return False
        first_run = False
    else:
        # No stamp: either a fresh checkout, or a tree whose cache predates this
        # mechanism. Both must not invalidate. A cached output can be the only copy of
        # an archive that is no longer readable — the band buffers about a week and
        # overwrites — so the conservative move is to record the configuration and keep
        # what is there. A genuine later change still gets caught, because the stamp
        # now exists to compare against.
        first_run = True

    STAMPS.mkdir(parents=True, exist_ok=True)
    stamp.write_text(current, encoding="utf-8")
    if first_run:
        if _cached_outputs(directory):
            print(
                f"{source}: recording configuration, keeping existing cache",
                file=sys.stderr,
            )
        return False

    for loader in sorted(directory.rglob("*.json.py")):
        # Bumping the loader's mtime is what `preview` looks at; dropping the cached
        # file covers `build`, which ignores timestamps and only asks whether the
        # output is already cached.
        loader.touch()
        cached = CACHE / loader.relative_to(SRC).with_suffix("")
        cached.unlink(missing_ok=True)
    print(f"{source}: configuration changed, re-running its loaders", file=sys.stderr)
    return True


def _cached_outputs(directory: Path) -> list[Path]:
    """Cached outputs that exist for a source's loaders."""
    return [
        cached
        for loader in directory.rglob("*.json.py")
        if (cached := CACHE / loader.relative_to(SRC).with_suffix("")).exists()
    ]


def main() -> None:
    for source in SOURCES:
        refresh(source)
    for legacy in LEGACY_STAMPS:
        legacy.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
