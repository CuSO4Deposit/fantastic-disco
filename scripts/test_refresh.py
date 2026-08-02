"""Tests for per-source cache invalidation.

The behaviour under test is the one whose absence destroyed data: configuring one source
must not invalidate another's cached output, because that output is not always
reproducible — a loader reads an archive that may be unmounted or rotated away.

Run with `python scripts/test_refresh.py`. Standalone rather than pytest, since this
repo has no test suite to hang it on and the script under test is the only subject.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
failures: list[str] = []


def check(condition: bool, description: str) -> None:
    print(f"{'ok  ' if condition else 'FAIL'} {description}")
    if not condition:
        failures.append(description)


class Tree:
    """A throwaway copy of the repo's script, src layout and cache.

    A real directory tree rather than mocks: the script's whole job is deciding which
    files to unlink, and that is exactly what a mock would stub out.
    """

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="refresh-test-"))
        (self.root / "scripts").mkdir()
        shutil.copy(ROOT / "scripts" / "refresh.py", self.root / "scripts")
        # `_shared` and the two optional helper modules are imported by the script.
        for source in ("video", "band", "firefox", "rhythm"):
            (self.root / "src" / source / "data").mkdir(parents=True)
        (self.root / "src" / "lib").mkdir()
        (self.root / "src" / "lib" / "_shared.py").write_text(
            "def blocklist_fingerprint():\n    return ''\n"
        )
        (self.root / "src" / "video" / "data" / "fandoms.py").write_text(
            "def fingerprint():\n    return ''\n"
        )
        (self.root / "src" / "rhythm" / "data" / "catalogues.py").write_text(
            "import os\n"
            "def fingerprint():\n"
            "    return os.environ.get('ARCSONG_DB', '')\n"
        )
        for source in ("video", "band", "firefox", "rhythm"):
            loader = self.root / "src" / source / "data" / f"{source}.json.py"
            loader.write_text("print('{}')\n")

    def cache(self, source: str) -> Path:
        path = (
            self.root
            / "src"
            / ".observablehq"
            / "cache"
            / source
            / "data"
            / f"{source}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def seed_cache(self) -> None:
        """Pretend every source has been built before."""
        for source in ("video", "band", "firefox", "rhythm"):
            self.cache(source).write_text(f"{source} data")

    def run(self, **env: str) -> str:
        result = subprocess.run(
            [sys.executable, "scripts/refresh.py"],
            cwd=self.root,
            capture_output=True,
            text=True,
            env={**os.environ, **env},
        )
        if result.returncode != 0:
            raise AssertionError(f"refresh.py failed: {result.stderr}")
        return result.stderr

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def test_first_run_keeps_existing_cache() -> None:
    """No stamp yet must not discard a cache that may be irreplaceable."""
    tree = Tree()
    try:
        tree.seed_cache()
        tree.run(CPI_LOCAL_TZ="Asia/Tokyo")
        check(
            all(tree.cache(s).exists() for s in ("video", "band", "firefox", "rhythm")),
            "first run keeps every existing cached output",
        )
    finally:
        tree.cleanup()


def test_unrelated_change_leaves_other_sources_alone() -> None:
    """The regression this exists for: rhythm config must not touch the band."""
    tree = Tree()
    try:
        tree.seed_cache()
        tree.run(CPI_LOCAL_TZ="Asia/Tokyo", ARCSONG_DB="/one")
        # Second run with only the rhythm catalogue changed.
        output = tree.run(CPI_LOCAL_TZ="Asia/Tokyo", ARCSONG_DB="/two")
        check(
            not tree.cache("rhythm").exists(),
            "rhythm cache dropped when its own config changed",
        )
        check(tree.cache("band").exists(), "band cache survives a rhythm-only change")
        check(
            tree.cache("firefox").exists(),
            "firefox cache survives a rhythm-only change",
        )
        check(tree.cache("video").exists(), "video cache survives a rhythm-only change")
        check("rhythm" in output and "band" not in output, "only rhythm is reported")
    finally:
        tree.cleanup()


def test_shared_input_invalidates_every_reader() -> None:
    """`CPI_LOCAL_TZ` really does change what band, Firefox and rhythm emit."""
    tree = Tree()
    try:
        tree.seed_cache()
        tree.run(CPI_LOCAL_TZ="Asia/Tokyo")
        tree.run(CPI_LOCAL_TZ="Europe/Paris")
        check(not tree.cache("band").exists(), "band invalidated by a timezone change")
        check(
            not tree.cache("firefox").exists(),
            "firefox invalidated by a timezone change",
        )
        check(
            not tree.cache("rhythm").exists(),
            "rhythm invalidated by a timezone change",
        )
        check(
            tree.cache("video").exists(),
            "video survives a timezone change, which it does not read",
        )
    finally:
        tree.cleanup()


def test_unchanged_config_is_a_no_op() -> None:
    tree = Tree()
    try:
        tree.seed_cache()
        tree.run(CPI_LOCAL_TZ="Asia/Tokyo", ARCSONG_DB="/one")
        output = tree.run(CPI_LOCAL_TZ="Asia/Tokyo", ARCSONG_DB="/one")
        check(output.strip() == "", "an unchanged configuration says nothing")
        check(
            all(tree.cache(s).exists() for s in ("video", "band", "firefox", "rhythm")),
            "an unchanged configuration keeps every cache",
        )
    finally:
        tree.cleanup()


def test_unsetting_a_variable_invalidates() -> None:
    """Deleting config must restore full data as reliably as adding it narrows."""
    tree = Tree()
    try:
        tree.seed_cache()
        tree.run(CPI_LOCAL_TZ="Asia/Tokyo", ARCSONG_DB="/one")
        tree.run(CPI_LOCAL_TZ="Asia/Tokyo")
        check(
            not tree.cache("rhythm").exists(),
            "unsetting a catalogue invalidates the rhythm cache",
        )
    finally:
        tree.cleanup()


def test_absent_source_directory_is_skipped() -> None:
    """The build command deletes unconfigured sources; that must not be an error."""
    tree = Tree()
    try:
        tree.seed_cache()
        shutil.rmtree(tree.root / "src" / "band")
        tree.run(CPI_LOCAL_TZ="Asia/Tokyo")
        output = tree.run(CPI_LOCAL_TZ="Europe/Paris")
        check("band" not in output, "an absent source is not reported")
        check(not tree.cache("firefox").exists(), "present sources still invalidate")
    finally:
        tree.cleanup()


def main() -> int:
    for name, test in sorted(globals().items()):
        if name.startswith("test_") and callable(test):
            test()
    print()
    if failures:
        print(f"{len(failures)} failed")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
