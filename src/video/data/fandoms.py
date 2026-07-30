"""Tagging videos by which thing I follow they belong to.

Keyword substring matching over title and uploader, case-insensitive. Crude, and
crude in a known direction: it can only find videos that *say* the name, so a
release whose title is just a song name goes untagged. Every per-fandom number is
therefore a floor, never a total.

Verified against a real export before settling on these lists: `mea` alone pulls in
~70 videos and every one is genuine (MeAqua, mea酱, clips) — the CJK-heavy titles
mean it never hits `meat` or `means`. `qk` matched exactly one video, which also
said `QuizKnock`, so it earns nothing and is left out to keep the list honest.
"""

# Ordered so the first entry reads as the display name.
FANDOMS: dict[str, tuple[str, ...]] = {
    "Mea": ("kaguramea", "mea", "咩", "神乐", "神楽"),
    "QuizKnock": ("quizknock", "quiz", "山本"),
}


def tags(*fields: str | None) -> list[str]:
    """Which fandoms the given text fields mention."""
    haystack = " ".join(f for f in fields if f).lower()
    return [
        name
        for name, keywords in FANDOMS.items()
        if any(k in haystack for k in keywords)
    ]
