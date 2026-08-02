"""One row per site, with visits, attention and Firefox's own relevance score.

Sites rather than pages: 46363 pages against 2598 sites, and a page-level file would be
most of the archive shipped to the browser. The pages that do get named are the handful
each machine spent the most time on, which is a different question from which site was
busiest.

Grouping is by hostname parsed from the URL, which is a presentation choice and lives
in `urls.py`. `moz_origins` is read too, but only for frecency: it is Firefox's score
for a site, and it cannot be joined to visits without reimplementing the browser's own
normalisation.
"""

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

# A loader runs with only its own directory on sys.path, so src/lib needs adding.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from _shared import exports, local_tz
from cuso4d import firefox as ff
from urls import site_of

#: How many pages to name per machine. Enough to see what the time went on, few
#: enough that this stays a summary rather than a copy of the history.
TOP_PAGES = 40

#: A site counts as a search page only if Firefox marked at least this many of its
#: visits `SEARCHED`, and at least this share of them. The flag also lands on a site's
#: own in-page search, which the share test is what excludes — see `main`.
SEARCH_PAGE_MIN = 20
SEARCH_PAGE_SHARE = 0.2


def main() -> None:
    tz = local_tz()
    archive = exports("CPI_FIREFOX_EXPORTS", "Firefox places.sqlite snapshots")

    visits: defaultdict[str, int] = defaultdict(int)
    typed: defaultdict[str, int] = defaultdict(int)
    searched: defaultdict[str, int] = defaultdict(int)
    days: defaultdict[str, set[date]] = defaultdict(set)
    first: dict[str, date] = {}
    last: dict[str, date] = {}
    machines: defaultdict[str, set[str]] = defaultdict(set)
    # (referrer site, site), to answer which sites were arrived at *from* a search
    # page. Firefox's own `SEARCHED` source does not answer that — see below.
    referrals: defaultdict[tuple[str, str], int] = defaultdict(int)

    for visit in ff.visits(archive):
        site = site_of(visit.url)
        day = visit.when.astimezone(tz).date()
        visits[site] += 1
        days[site].add(day)
        machines[site].add(visit.snapshot.host)
        # Visits arrive oldest first, so the first write is the earliest and the last
        # wins for `last`.
        first.setdefault(site, day)
        last[site] = day
        if visit.visit_type is ff.VisitType.TYPED:
            typed[site] += 1
        if visit.source is ff.VisitSource.SEARCHED:
            # This marks a visit *to* a search page, not a visit that came from one:
            # every one of the 3647 in the reference archive lands on a search engine
            # itself. Counted under that reading.
            searched[site] += 1
        if visit.referrer_url is not None:
            referrals[(site_of(visit.referrer_url), site)] += 1

    if not visits:
        sys.exit("no visits in the archive; refusing to emit an empty site list")

    # Which sites act as search pages, taken from Firefox's own `SEARCHED` marking
    # rather than from a hardcoded list of engines: the browser knows which of its
    # configured engines a visit came through, and a list here would miss whichever
    # one this profile actually uses.
    #
    # A share threshold rather than any marking at all, because the flag also lands on
    # a site's own in-page search: `en.wikipedia.org` carries 2 such visits against
    # 3000-odd normal ones, and treating it as a search engine would file every link
    # followed out of an article as a search result.
    search_sites = {
        site
        for site, count in searched.items()
        if count >= SEARCH_PAGE_MIN and count / visits[site] >= SEARCH_PAGE_SHARE
    }
    from_search: defaultdict[str, int] = defaultdict(int)
    for (referrer, site), count in referrals.items():
        if referrer in search_sites and referrer != site:
            from_search[site] += count

    view_ms: defaultdict[str, int] = defaultdict(int)
    engagements: defaultdict[str, int] = defaultdict(int)
    page_view_ms: defaultdict[tuple[str, str], int] = defaultdict(int)
    page_engagements: defaultdict[tuple[str, str], int] = defaultdict(int)
    for record in ff.engagement(archive):
        site = site_of(record.url)
        view_ms[site] += record.total_view_time_ms
        engagements[site] += 1
        page_view_ms[(record.snapshot.host, record.url)] += record.total_view_time_ms
        page_engagements[(record.snapshot.host, record.url)] += 1

    # Frecency per site, taking the highest across prefixes and machines. `http://`
    # and `https://` for one site are separate origin rows, and summing them would
    # double-count a site that was reached both ways.
    frecency: dict[str, int] = {}
    origin_rows = 0
    unscored = 0
    for origin in ff.origins(archive):
        origin_rows += 1
        score = origin.frecency
        if score is None:
            # Negative means "needs recalculation", not a rank of zero.
            unscored += 1
            continue
        if score > frecency.get(origin.site, -1):
            frecency[origin.site] = score

    titles = {
        (page.snapshot.host, page.url): page.title
        for page in ff.pages(archive)
        if page.title
    }

    rows = [
        {
            "site": site,
            "visits": count,
            "typed": typed.get(site, 0),
            # Visits to this site that Firefox marked as search-page visits, which is
            # what `VisitSource.SEARCHED` means. Not arrivals from a search.
            "search_page_visits": searched.get(site, 0),
            # Arrivals whose referrer was one of the sites this archive shows acting
            # as a search page. Derived from referrers, so it undercounts: a referrer
            # is None for 24888 visits, including every one whose referring visit
            # Firefox has expired.
            "from_search": from_search.get(site, 0),
            "days": len(days[site]),
            "first": first[site].isoformat(),
            "last": last[site].isoformat(),
            "machines": sorted(machines[site]),
            # None where this site has no engagement row at all, which for anything
            # before the engagement window means "unknown", not "no time spent".
            "view_minutes": (
                round(view_ms[site] / 60_000, 1) if site in view_ms else None
            ),
            "engagements": engagements.get(site, 0),
            "frecency": frecency.get(site),
        }
        for site, count in sorted(visits.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    json.dump(
        {
            "timezone": str(tz),
            "sites": rows,
            # The sites Firefox marked as search pages, so a page can name what
            # `from_search` was derived from rather than implying a fixed list.
            "search_sites": sorted(search_sites, key=lambda s: -searched[s]),
            "pages": _top_pages(page_view_ms, page_engagements, titles),
            "typed_inputs": [
                {
                    "input": entry.input,
                    "site": site_of(entry.url),
                    "machine": entry.snapshot.host,
                    # A decaying weight, not a number of uses.
                    "weight": round(entry.use_count, 3),
                }
                for entry in ff.typed_inputs(archive)
            ],
            # Origin rows across each machine's newest snapshot, and how many carry
            # the recalculation sentinel instead of a score.
            "origins": origin_rows,
            "origins_unscored": unscored,
        },
        sys.stdout,
        ensure_ascii=False,
    )


def _top_pages(
    view_ms: dict[tuple[str, str], int],
    engagements: dict[tuple[str, str], int],
    titles: dict[tuple[str, str], str],
) -> list[dict[str, object]]:
    """The pages the most foreground time went to, per machine.

    Per machine rather than pooled, since `(host, url)` is the identity: the same URL
    on two machines is two records, and adding them would report a machine-independent
    total the archive cannot support.
    """
    by_machine: defaultdict[str, list[tuple[str, int]]] = defaultdict(list)
    for (machine, url), total in view_ms.items():
        by_machine[machine].append((url, total))

    out: list[dict[str, object]] = []
    for machine, entries in sorted(by_machine.items()):
        entries.sort(key=lambda kv: -kv[1])
        for url, total in entries[:TOP_PAGES]:
            out.append(
                {
                    "machine": machine,
                    "site": site_of(url),
                    # Firefox has no title for 3881 of 46363 pages — a redirect hop or
                    # a download target never gets one.
                    "title": titles.get((machine, url)),
                    "url": url,
                    "view_minutes": round(total / 60_000, 1),
                    "engagements": engagements[(machine, url)],
                }
            )
    return out


if __name__ == "__main__":
    main()
