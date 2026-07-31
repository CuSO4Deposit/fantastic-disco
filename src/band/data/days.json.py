"""One row per local day of band data, plus one row per night of sleep.

Two series rather than one, because a night and a day do not share a boundary. Steps
belong to the calendar day they were taken; a night of sleep starts before midnight
about as often as after, so splitting it at midnight reports two half-nights and no
whole one. Nights are keyed by the date the sleep *started*, which is what "Tuesday
night" means.

Everything is flattening and renaming over CPI. The activity-kind carry-forward, the
heart rate sentinels and the timestamp units are all handled upstream, where they are
tested.
"""

import itertools
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

# A loader runs with only its own directory on sys.path, so src/lib needs adding.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from _shared import exports, local_tz
from cuso4d import gadgetbridge as gb

#: Sessions shorter than this are naps or misdetections, kept out of the nightly
#: series so a 20-minute doze does not become a data point beside an 8-hour night.
#: A presentation choice, unlike the session-splitting rule itself, which is device
#: semantics and lives in CPI.
MIN_SESSION = timedelta(hours=3)


def main() -> None:
    tz = local_tz()
    archive = exports("CPI_GADGETBRIDGE_EXPORTS", "Gadgetbridge backups")

    samples = list(gb.activity(archive))
    if not samples:
        sys.exit("no activity samples in the archive; refusing to emit an empty day")

    # Per local calendar day. Minutes are counted distinctly: sub-minute realtime
    # rows would otherwise inflate coverage past 100%.
    minutes: defaultdict[date, set[int]] = defaultdict(set)
    steps: defaultdict[date, int] = defaultdict(int)
    worn: defaultdict[date, set[int]] = defaultdict(set)
    hr_awake: defaultdict[date, list[int]] = defaultdict(list)

    for sample in samples:
        day = sample.when.astimezone(tz).date()
        minute = sample.timestamp_s // 60

        minutes[day].add(minute)
        if sample.steps:
            steps[day] += sample.steps
        if sample.worn:
            worn[day].add(minute)
        if sample.heart_rate is not None and sample.worn and not sample.asleep:
            hr_awake[day].append(sample.heart_rate)

    goal = next(
        (u.steps_goal for u in reversed(list(gb.user_attributes(archive)))),
        None,
    )

    days = [
        {
            "date": day.isoformat(),
            "steps": steps.get(day, 0),
            # Distinct minutes with any sample at all, against the 1440 a full day
            # would hold. A page needs this to say whether a low step count means a
            # quiet day or a day the band spent in a drawer.
            "recorded_minutes": len(mins),
            "worn_minutes": len(worn.get(day, ())),
            "heart_rate_awake": _median(hr_awake.get(day, [])),
        }
        for day, mins in sorted(minutes.items())
    ]

    # Sessions come from CPI, which cuts them on the band's own semantics. Which ones
    # count as nights, and which local date each belongs to, are decided here.
    nights = []
    for session in gb.parser.sleep_sessions(samples):
        if session.asleep < MIN_SESSION:
            continue
        start = session.start.astimezone(tz)
        end = session.end.astimezone(tz)
        nights.append(
            {
                # The date sleep began, so a night is one row whichever side of
                # midnight it starts.
                "date": start.date().isoformat(),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "light_minutes": session.light_minutes,
                "deep_minutes": session.deep_minutes,
                # Wall-clock span, which exceeds light+deep by the awakenings in
                # between. Both are wanted: one is time in bed, the other asleep.
                "span_minutes": round(session.span.total_seconds() / 60),
                # Lowest sustained heart rate while asleep is the closest this band
                # gets to a resting rate; it records no resting-HR series of its own.
                "heart_rate_low": _percentile(list(session.heart_rates), 0.05),
                "heart_rate_median": _median(list(session.heart_rates)),
            }
        )

    json.dump(
        {
            "timezone": str(tz),
            "steps_goal": goal,
            "days": days,
            "nights": nights,
            # Stated so a page can qualify totals instead of implying the record is
            # continuous. The band buffers about a week, so an unsynced stretch is
            # simply missing rather than empty.
            "gaps": _gaps(sorted(minutes)),
        },
        sys.stdout,
        ensure_ascii=False,
    )


def _median(values: list[int]) -> float | None:
    return _percentile(values, 0.5)


def _percentile(values: list[int], q: float) -> float | None:
    """Nearest-rank percentile, or None for no data. Avoids importing statistics for
    one call and keeps the no-data case explicit rather than raising."""
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(q * len(ordered)))
    return ordered[index]


def _gaps(days: list[date]) -> list[dict[str, object]]:
    """Runs of consecutive calendar days with no data at all."""
    out: list[dict[str, object]] = []
    for previous, following in itertools.pairwise(days):
        missing = (following - previous).days - 1
        if missing > 0:
            out.append(
                {
                    "after": previous.isoformat(),
                    "before": following.isoformat(),
                    "days": missing,
                }
            )
    return out


if __name__ == "__main__":
    main()
