"""Turning a URL into the site it belongs to.

Not in CPI: `places.sqlite` stores whole URLs and CPI reports them as stored, so
choosing what to group by is a presentation decision. Not in `src/lib` either, since
nothing else needs it yet.

`moz_origins` already holds Firefox's own idea of a site, but it cannot be used for
grouping visits — a visit row carries a URL, and joining back to an origin would mean
reimplementing Firefox's `rev_host` normalisation. Parsing the URL is what the other
half of that table is derived from anyway.
"""

from __future__ import annotations

from urllib.parse import urlsplit

#: What a URL with no host is filed under. `file://` and `about:` URLs are real
#: navigations — 268 `file:` visits in the reference archive — and dropping them
#: would make the visit total disagree with the history total for no stated reason.
NO_HOST = {"file": "(local files)", "about": "(browser pages)"}


def site_of(url: str) -> str:
    """The hostname a URL belongs to, or a label for the schemes that have none.

    Ports and userinfo are stripped by `hostname`; `www.` is deliberately *not*,
    since Firefox treats `www.example.com` and `example.com` as separate origins and
    stripping it here would make the site counts disagree with `moz_origins`.

    A URL sqlite hands back that does not parse yields the empty string rather than
    raising: one unparseable row must not abort a build.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return "(unparseable)"
    if parts.hostname:
        return parts.hostname
    return NO_HOST.get(parts.scheme, f"({parts.scheme or 'no scheme'})")


def scheme_of(url: str) -> str:
    try:
        return urlsplit(url).scheme or "(none)"
    except ValueError:
        return "(unparseable)"


def filename_of(destination: str) -> str:
    """The last path component of a `file://` download destination.

    Only the basename, never the directory: `Download.destination` is a local path
    that carries the account name, and a page listing full paths would publish it.
    Percent-escapes are left as they are — decoding them is presentation, and the
    page shows this verbatim.
    """
    return destination.rstrip("/").rsplit("/", 1)[-1]


def extension_of(filename: str) -> str:
    """Lowercased final suffix, or `(none)`. Grouping downloads by kind."""
    _, dot, suffix = filename.rpartition(".")
    if not dot or not suffix or len(suffix) > 12:
        return "(none)"
    return suffix.lower()
