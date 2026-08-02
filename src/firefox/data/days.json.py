"""One row per local day per machine, plus the windows each machine can speak for.

Two things make this different from the band's daily series, and both are about what a
day's absence means.

Firefox expires history when the database exceeds its size limit, so an early day with
few visits may be a quiet day or the remains of a pruned one — there is no way to tell
from the file. And engagement rows are expired on age, much sooner than the matching
visits, so view time simply does not exist before some date that differs per machine.
Both windows are emitted per host so the pages can draw each series only where it is
real rather than letting a chart imply a year of zero reading.

Rows are keyed by machine as well as date: `moz_places.id` is profile-local, so two
snapshots are two records of two browsers, never one merged history.
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
from urls import scheme_of, site_of


def main() -> None:
    tz = local_tz()
    archive = exports("CPI_FIREFOX_EXPORTS", "Firefox places.sqlite snapshots")

    # Per (machine, local date). Reloads are counted separately rather than dropped:
    # Firefox leaves them out of `moz_places.visit_count`, so a page that wants to
    # agree with the browser's own numbers needs to know how many there were.
    total: defaultdict[tuple[str, date], int] = defaultdict(int)
    counted: defaultdict[tuple[str, date], int] = defaultdict(int)
    reloads: defaultdict[tuple[str, date], int] = defaultdict(int)
    typed: defaultdict[tuple[str, date], int] = defaultdict(int)
    sites: defaultdict[tuple[str, date], set[str]] = defaultdict(set)

    types: defaultdict[str, int] = defaultdict(int)
    sources: defaultdict[str, int] = defaultdict(int)
    schemes: defaultdict[str, int] = defaultdict(int)
    history_days: defaultdict[str, set[date]] = defaultdict(set)
    no_referrer = 0

    for visit in ff.visits(archive):
        machine = visit.snapshot.host
        day = visit.when.astimezone(tz).date()
        key = (machine, day)

        total[key] += 1
        history_days[machine].add(day)
        if visit.counted:
            counted[key] += 1
        sites[key].add(site_of(visit.url))

        kind = visit.visit_type
        types[kind.name if kind is not None else f"({visit.visit_type_raw})"] += 1
        if kind is ff.VisitType.RELOAD:
            reloads[key] += 1
        elif kind is ff.VisitType.TYPED:
            typed[key] += 1

        source = visit.source
        sources[source.name if source is not None else f"({visit.source_raw})"] += 1
        schemes[scheme_of(visit.url)] += 1
        if visit.referrer_url is None:
            no_referrer += 1

    if not total:
        sys.exit("no visits in the archive; refusing to emit an empty history")

    # View time per day, from the engagement table rather than from visits. Sparse
    # against the history above, which is what the windows below are for.
    view_ms: defaultdict[tuple[str, date], int] = defaultdict(int)
    engagements: defaultdict[tuple[str, date], int] = defaultdict(int)
    engagement_days: defaultdict[str, set[date]] = defaultdict(set)
    for record in ff.engagement(archive):
        day = record.created_at.astimezone(tz).date()
        view_ms[(record.snapshot.host, day)] += record.total_view_time_ms
        engagements[(record.snapshot.host, day)] += 1
        engagement_days[record.snapshot.host].add(day)

    # Sorted by (date, machine) so a chart reads chronologically whichever machine
    # wrote the row.
    rows = [
        {
            "date": day.isoformat(),
            "machine": machine,
            "visits": count,
            # Firefox's own rule, so a page can quote either number and say which.
            "counted_visits": counted[(machine, day)],
            "reloads": reloads[(machine, day)],
            "typed": typed[(machine, day)],
            "sites": len(sites[(machine, day)]),
            # None rather than 0 outside this machine's engagement window: no
            # engagement row is not zero seconds of reading.
            "view_minutes": (
                round(view_ms[(machine, day)] / 60_000, 1)
                if (machine, day) in view_ms
                else None
            ),
            "engagements": engagements.get((machine, day), 0),
        }
        for (machine, day), count in sorted(
            total.items(), key=lambda kv: (kv[0][1], kv[0][0])
        )
    ]

    json.dump(
        {
            "timezone": str(tz),
            "machines": _machines(archive, history_days, engagement_days),
            "days": rows,
            "visit_types": dict(sorted(types.items(), key=lambda kv: -kv[1])),
            "visit_sources": dict(sorted(sources.items(), key=lambda kv: -kv[1])),
            "schemes": dict(sorted(schemes.items(), key=lambda kv: -kv[1])),
            # Stated so a page can describe how pages were reached without reading a
            # missing referrer as "typed the URL", which it is not: it means no
            # referrer, an expired referring visit, or a page since deleted.
            "visits_without_referrer": no_referrer,
        },
        sys.stdout,
        ensure_ascii=False,
    )


def _machines(
    archive: str,
    history: dict[str, set[date]],
    engagement: dict[str, set[date]],
) -> list[dict[str, object]]:
    """What each machine's snapshots can and cannot answer for.

    Both windows are the *observed* extent of the data, not a retention policy: the
    history one starts wherever expiration last cut, and the engagement one wherever
    `QUERY_EXPIRE_INTERACTIONS` last ran. Per host because they differ per host — 134
    days of engagement against 288 of history on one machine, 230 against 427 on the
    other.
    """
    taken: defaultdict[str, list[str]] = defaultdict(list)
    for _, snapshot in ff.snapshots(archive):
        taken[snapshot.host].append(snapshot.taken_at.isoformat())

    out: list[dict[str, object]] = []
    for machine in sorted(history):
        days = history[machine]
        seen = engagement.get(machine, set())
        out.append(
            {
                "machine": machine,
                "history_from": min(days).isoformat(),
                "history_to": max(days).isoformat(),
                "days_with_history": len(days),
                "engagement_from": min(seen).isoformat() if seen else None,
                "engagement_to": max(seen).isoformat() if seen else None,
                "days_with_engagement": len(seen),
                # Every snapshot's timestamp, so a page can say how much of the record
                # rests on a single export rather than on an accumulated series.
                "snapshots": sorted(taken.get(machine, [])),
            }
        )
    return out


if __name__ == "__main__":
    main()
