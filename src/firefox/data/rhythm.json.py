"""When the browsing happens, and how long a page holds attention.

Two aggregates that need the row level rather than daily totals: the hour-of-week grid,
and the distribution of view times. Both are emitted pre-binned — 84k visits and 38k
engagement rows would be a several-megabyte download to draw two charts the browser
would then have to bin anyway.

Bin edges are a presentation choice, so they live here rather than in CPI.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

# A loader runs with only its own directory on sys.path, so src/lib needs adding.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from _shared import exports, local_tz
from cuso4d import firefox as ff

#: Log-spaced edges for view time, in seconds, from a second to about six hours.
#: Linear bins are wrong here rather than merely coarse: the median engagement is
#: under six seconds while the longest is over two hours, so any linear width that
#: shows the tail puts almost everything in the first bar.
VIEW_BINS = [round(0.5 * 2 ** (i / 2), 3) for i in range(29)]


def main() -> None:
    tz = local_tz()
    archive = exports("CPI_FIREFOX_EXPORTS", "Firefox places.sqlite snapshots")

    # (weekday, hour) with Monday as 0, matching `date.weekday()`.
    visits: defaultdict[tuple[int, int], int] = defaultdict(int)
    typed: defaultdict[tuple[int, int], int] = defaultdict(int)
    view_ms: defaultdict[tuple[int, int], int] = defaultdict(int)
    engagements: defaultdict[tuple[int, int], int] = defaultdict(int)

    # Distinct local dates per slot, so a busy slot can be reported per occurrence
    # rather than as a total. The archive covers 61 Mondays and 62 Saturdays; a raw
    # total would make whichever weekday it holds most of look like the busiest.
    #
    # Counted separately for the two series: engagement covers a shorter window than
    # history, so pooling the dates would divide visits by a number that includes days
    # only engagement saw.
    visit_dates: defaultdict[tuple[int, int], set[str]] = defaultdict(set)
    view_dates: defaultdict[tuple[int, int], set[str]] = defaultdict(set)

    for visit in ff.visits(archive):
        when = visit.when.astimezone(tz)
        slot = (when.weekday(), when.hour)
        visits[slot] += 1
        visit_dates[slot].add(when.date().isoformat())
        if visit.visit_type is ff.VisitType.TYPED:
            typed[slot] += 1

    if not visits:
        sys.exit("no visits in the archive; refusing to emit an empty rhythm")

    hist: defaultdict[float, int] = defaultdict(int)
    zero = 0
    over_span = 0
    keys = 0
    scroll_px = 0
    typing_ms = 0
    with_keys = 0
    with_scroll = 0
    doc_types: defaultdict[str, int] = defaultdict(int)
    total_view_ms = 0
    rows = 0

    for record in ff.engagement(archive):
        when = record.created_at.astimezone(tz)
        slot = (when.weekday(), when.hour)
        view_ms[slot] += record.total_view_time_ms
        engagements[slot] += 1
        view_dates[slot].add(when.date().isoformat())

        rows += 1
        total_view_ms += record.total_view_time_ms
        keys += record.key_presses
        scroll_px += record.scrolling_distance
        typing_ms += record.typing_time_ms
        with_keys += bool(record.key_presses)
        with_scroll += bool(record.scrolling_distance)
        kind = record.document_type
        doc_types[
            kind.name if kind is not None else f"({record.document_type_raw})"
        ] += 1

        seconds = record.total_view_time_ms / 1000
        if seconds <= 0:
            # Kept out of the log-scaled histogram, which has no bin for zero, and
            # reported separately. A row with no view time is a page that was opened
            # and never in the foreground long enough to accumulate any.
            zero += 1
        else:
            hist[_bin(seconds)] += 1
        # Documented upstream as normally below the wall-clock span but not bounded
        # by it. Counted so the page can say so from this archive rather than
        # repeating the claim.
        if record.total_view_time_ms > record.updated_at_ms - record.created_at_ms:
            over_span += 1

    json.dump(
        {
            "timezone": str(tz),
            "view_bins": VIEW_BINS,
            "slots": [
                {
                    "weekday": weekday,
                    "hour": hour,
                    "visits": count,
                    "typed": typed.get((weekday, hour), 0),
                    # Per occurrence of the slot, not a total: slots differ in how
                    # many times the archive covers them.
                    "visits_per_day": count / len(visit_dates[(weekday, hour)]),
                    "view_minutes": round(view_ms.get((weekday, hour), 0) / 60_000, 1),
                    # Per occurrence too, and over the engagement window's own days
                    # rather than the history window's, which is longer.
                    "view_minutes_per_day": (
                        round(
                            view_ms[(weekday, hour)]
                            / 60_000
                            / len(view_dates[(weekday, hour)]),
                            2,
                        )
                        if view_dates.get((weekday, hour))
                        else None
                    ),
                    "engagements": engagements.get((weekday, hour), 0),
                    "days": len(visit_dates[(weekday, hour)]),
                    "engagement_days": len(view_dates.get((weekday, hour), ())),
                }
                for (weekday, hour), count in sorted(visits.items())
            ],
            "view_time": [
                {"seconds": edge, "count": count}
                for edge, count in sorted(hist.items())
            ],
            "engagement": {
                "rows": rows,
                "view_hours": round(total_view_ms / 3_600_000, 1),
                "zero_view_time": zero,
                "over_wall_clock_span": over_span,
                "key_presses": keys,
                "typing_minutes": round(typing_ms / 60_000, 1),
                "rows_with_keys": with_keys,
                "rows_with_scroll": with_scroll,
                # Firefox's own unit, CSS pixels. Left raw rather than converted to
                # anything physical, which would need a DPI this file does not hold.
                "scroll_px": scroll_px,
                "document_types": dict(
                    sorted(doc_types.items(), key=lambda kv: -kv[1])
                ),
            },
        },
        sys.stdout,
        ensure_ascii=False,
    )


def _bin(seconds: float) -> float:
    """The largest edge at or below `seconds`, clamped into the outermost bins."""
    edge = VIEW_BINS[0]
    for candidate in VIEW_BINS:
        if candidate > seconds:
            break
        edge = candidate
    return edge


if __name__ == "__main__":
    main()
