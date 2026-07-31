"""Aggregates over the whole series that a per-day row cannot answer.

Three things, all needing the minute-level series rather than daily totals: what the
day looks like hour by hour, how heart rate is distributed, and how stress relates to
it. Emitted pre-binned because the raw series is 891k rows for two years — sending
that to the browser to bin it there would be a 30MB download to draw four charts.

Binning here is a presentation choice, so the bin edges live in this file rather than
in CPI.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

# A loader runs with only its own directory on sys.path, so src/lib needs adding.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from _shared import exports, local_tz
from cuso4d import gadgetbridge as gb

#: Heart rate bin width, in bpm. Five is fine enough to show the shape and coarse
#: enough that every bin holds real counts.
HR_BIN = 5

#: Stress bin width, on the documented 0-100 scale.
STRESS_BIN = 10


def main() -> None:
    tz = local_tz()
    archive = exports("CPI_GADGETBRIDGE_EXPORTS", "Gadgetbridge backups")

    # Per (weekday, hour) so the page can show a weekday-vs-weekend split without a
    # second pass. Weekday 0 is Monday, matching `date.weekday()`.
    steps_by_slot: defaultdict[tuple[int, int], int] = defaultdict(int)
    minutes_by_slot: defaultdict[tuple[int, int], int] = defaultdict(int)
    asleep_by_slot: defaultdict[tuple[int, int], int] = defaultdict(int)
    hr_by_slot: defaultdict[tuple[int, int], list[int]] = defaultdict(list)

    hr_hist: defaultdict[int, int] = defaultdict(int)
    hr_hist_asleep: defaultdict[int, int] = defaultdict(int)
    kind_minutes: defaultdict[str, int] = defaultdict(int)

    # Heart rate per minute, kept to join the stress series against. Only minutes
    # with a valid reading, so the dict doubles as the "was it measured" test.
    hr_by_minute: dict[int, int] = {}

    for sample in gb.activity(archive):
        when = sample.when.astimezone(tz)
        slot = (when.weekday(), when.hour)

        minutes_by_slot[slot] += 1
        if sample.steps:
            steps_by_slot[slot] += sample.steps
        if sample.asleep:
            asleep_by_slot[slot] += 1

        kind = sample.kind
        kind_minutes[kind.name if kind is not None else "UNKNOWN"] += 1

        rate = sample.heart_rate
        if rate is not None:
            hr_by_slot[slot].append(rate)
            hr_hist[rate // HR_BIN * HR_BIN] += 1
            if sample.asleep:
                hr_hist_asleep[rate // HR_BIN * HR_BIN] += 1
            if sample.worn:
                hr_by_minute[sample.timestamp_s // 60 * 60] = rate

    if not minutes_by_slot:
        sys.exit("no activity samples in the archive; refusing to emit empty rhythm")

    # Stress against the heart rate recorded in the same minute. The two series use
    # different timestamp units, which is why the join goes through `minute_s`.
    stress_hist: defaultdict[int, int] = defaultdict(int)
    paired: defaultdict[tuple[int, int], int] = defaultdict(int)
    stress_total = stress_unmatched = 0
    for reading in gb.stress(archive):
        value = reading.stress_pct
        if value is None:
            continue
        stress_total += 1
        stress_hist[value // STRESS_BIN * STRESS_BIN] += 1
        rate = hr_by_minute.get(reading.minute_s)
        if rate is None:
            stress_unmatched += 1
            continue
        paired[(value // STRESS_BIN * STRESS_BIN, rate // HR_BIN * HR_BIN)] += 1

    json.dump(
        {
            "timezone": str(tz),
            "hr_bin": HR_BIN,
            "stress_bin": STRESS_BIN,
            "slots": [
                {
                    "weekday": weekday,
                    "hour": hour,
                    "minutes": minutes,
                    "steps": steps_by_slot.get((weekday, hour), 0),
                    "asleep_minutes": asleep_by_slot.get((weekday, hour), 0),
                    # Per minute rather than a total: slots do not hold equal numbers
                    # of minutes, since the record starts and ends mid-week and has
                    # gaps. A raw total would make whichever weekday the archive
                    # happens to cover most look like the busiest.
                    "steps_per_minute": steps_by_slot.get((weekday, hour), 0) / minutes,
                    "heart_rate_median": _median(hr_by_slot.get((weekday, hour), [])),
                }
                for (weekday, hour), minutes in sorted(minutes_by_slot.items())
            ],
            "heart_rate": [
                {
                    "bpm": bpm,
                    "minutes": count,
                    "asleep_minutes": hr_hist_asleep.get(bpm, 0),
                }
                for bpm, count in sorted(hr_hist.items())
            ],
            "stress": [
                {"value": value, "count": count}
                for value, count in sorted(stress_hist.items())
            ],
            "stress_vs_heart_rate": [
                {"stress": stress, "bpm": bpm, "count": count}
                for (stress, bpm), count in sorted(paired.items())
            ],
            # So a page can say what the stress chart is drawn from rather than
            # implying every reading is represented.
            "stress_readings": stress_total,
            "stress_without_heart_rate": stress_unmatched,
            "kind_minutes": dict(sorted(kind_minutes.items())),
        },
        sys.stdout,
        ensure_ascii=False,
    )


def _median(values: list[int]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


if __name__ == "__main__":
    main()
