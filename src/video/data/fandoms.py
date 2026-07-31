"""Tagging videos by which thing I follow they belong to.

Keyword substring matching over title and uploader, case-insensitive. Crude, and
crude in a known direction: it can only find videos that *say* the name, so a
release whose title is just a song name goes untagged. Every per-group number is
therefore a floor, never a total.

The groups themselves live in a gitignored `fandoms.txt` rather than here. Naming
what someone follows is personal in a way the matching mechanism is not — the same
split as the uploader denylist. See fandoms.example.txt for the format.
"""

from pathlib import Path

# Sits with the other local configuration, beside the denylist.
CONFIG = Path(__file__).resolve().parents[2] / "lib" / "fandoms.txt"


def groups() -> dict[str, tuple[str, ...]]:
    """Configured groups, as display name to keywords. Empty if unconfigured."""
    if not CONFIG.exists():
        return {}
    out: dict[str, tuple[str, ...]] = {}
    for line in CONFIG.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        name, _, rest = line.partition("=")
        keywords = tuple(k.strip().lower() for k in rest.split(",") if k.strip())
        if name.strip() and keywords:
            out[name.strip()] = keywords
    return out


def fingerprint() -> str:
    """The effective configuration as text, for cache invalidation.

    Framework only re-runs a loader when the loader itself changed, so anything read
    at run time must be compared by value. See `scripts/refresh.py`.
    """
    return "\n".join(f"{name}={','.join(kw)}" for name, kw in sorted(groups().items()))


def tags(*fields: str | None) -> list[str]:
    """Which configured groups the given text fields mention."""
    haystack = " ".join(f for f in fields if f).lower()
    return [
        name
        for name, keywords in groups().items()
        if any(k in haystack for k in keywords)
    ]
