"""Arcaea's potential timeline: which score raised it, from what to what.

Composed here out of the SDK's existing pieces rather than added to it. Neither piece
answers the question alone: `potential_trend` gives the value after every play but not
which play moved it, and a play record carries the song, difficulty and score but not
what the pool was. Pairing them is the whole of this loader.

The pairing is positional because `potential_trend` replays exactly `_records_asc` in
order, one point per record — the same list, so index `i` of one is index `i` of the
other. `only_changes=False` is required for that alignment; the default drops unchanged
plays and with them the correspondence. Points where the value did not move are dropped
after the pairing, which is what `only_changes=True` would have done anyway.

No pool rule is reimplemented. `replay_best`, Arcaea's top-10 double weight and the
notion of "entered the pool" all stay in the SDK; this only diffs consecutive values and
names the play behind each step.

A second series, `plays`, is every play's accuracy against its own chart's median — the
per-play form the Practice page averages by month, here at play resolution. The rating
can only show the best ever; this is what a page rolls and trims to show a usual level.
"""

import datetime
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from _shared import local_tz, rhythm_user
from catalogues import games


def _moves(
    records: list,
    points: list,
    tz: datetime.tzinfo,
    difficulty_names: dict[int, str],
    capacity: int,
) -> list[dict]:
    """Every play that changed the potential, oldest first, each naming its record.

    A `from` of 0 on the first row is the empty pool, not a real potential — there was
    nothing to come from. Rises before the pool fills are partly slots being occupied
    rather than playing better; `full` marks which is which and the page says so.
    """
    if len(records) != len(points):
        raise RuntimeError(
            f"potential_trend returned {len(points)} points for "
            f"{len(records)} records; they are paired by position"
        )

    out = []
    previous = 0.0
    previous_size = 0
    # Per chart, the state needed to say how long and how many tries it took to beat the
    # last personal best: the best score so far, when it was set, and which play of the
    # chart it was. Updated for every play, not only the moves — a play that did not
    # enter the pool still sets the record the next one has to beat.
    best_score: dict[tuple[str, int], int] = {}
    best_at: dict[tuple[str, int], int] = {}
    best_play: dict[tuple[str, int], int] = {}
    plays: dict[tuple[str, int], int] = {}
    for record, point in zip(records, points, strict=True):
        chart = (record.song_id, record.rating_class)
        previous_score = best_score.get(chart)
        # Index of this play among the chart's plays, 0-based: attempts before it.
        seen = plays.get(chart, 0)
        previous_at = best_at.get(chart)
        days_since_best = (
            None if previous_at is None else (record.time - previous_at) / 86400
        )
        # Plays after the previous best, this one included: tries to get here. None on
        # the chart's first play, which had no best to beat.
        plays_since_best = None if previous_at is None else seen - best_play[chart]
        delta = point.potential - previous
        if delta != 0:
            out.append(
                {
                    "at": point.at,
                    # Offset-bearing, built here because a page reading `getHours` off a
                    # Date gets the browser's zone, which is not where the play was
                    # recorded. The page slices this string instead.
                    "at_local": datetime.datetime.fromtimestamp(
                        point.at, tz
                    ).isoformat(),
                    "song_id": record.song_id,
                    "difficulty": difficulty_names.get(record.rating_class),
                    "name": record.name,
                    # The play's score, and the one it beat on this chart — null on the
                    # chart's first play, since there was nothing to come from.
                    "score": record.score,
                    "score_before": previous_score,
                    # Since that previous best: days elapsed and plays of this chart;
                    # both null when the chart had no earlier best.
                    "days_since_best": days_since_best,
                    "plays_since_best": plays_since_best,
                    "play_ptt": record.play_ptt,
                    "accuracy": record.accuracy(),
                    "from": previous,
                    "to": point.potential,
                    "delta": delta,
                    "b50_size": point.b50_size,
                    "full": point.full,
                    # Whether the pool was already full *before* this play. Size holds
                    # between moves, so the previous move's size is the size this play
                    # faced. The distinction matters for any "largest gain" claim: a
                    # slot filling while the pool is short moves the average by whole
                    # points, while a play beating a full pool is capped by what it
                    # displaced, so the two are not the same kind of move.
                    "full_before": previous_size >= capacity,
                }
            )
        previous = point.potential
        previous_size = point.b50_size
        if previous_score is None or record.score > previous_score:
            best_score[chart] = record.score
            best_at[chart] = record.time
            best_play[chart] = seen
        plays[chart] = seen + 1
    return out


def _performance(
    records: list, tz: datetime.tzinfo, min_chart_plays: int = 3
) -> list[dict]:
    """Every play's accuracy against its own chart's median, oldest first.

    The per-play quantity `AnalysisMixin.execution_trend` averages by month; this is the
    same at play resolution, so a page can roll a window over it and trim the tails.
    Centring on each chart's own median keeps windows comparable — without it a stretch
    on easy charts reads as good. The median and three-play floor match the SDK, so the
    two views agree; a chart below the floor has no stable median and is left out.
    """
    by_chart: dict[tuple[str, int], list[float]] = {}
    for record in records:
        by_chart.setdefault((record.song_id, record.rating_class), []).append(
            record.accuracy()
        )
    medians = {
        key: statistics.median(values)
        for key, values in by_chart.items()
        if len(values) >= min_chart_plays
    }

    out = []
    for record in records:
        median = medians.get((record.song_id, record.rating_class))
        if median is None:
            continue
        out.append(
            {
                "at": record.time,
                "at_local": datetime.datetime.fromtimestamp(
                    record.time, tz
                ).isoformat(),
                "delta": record.accuracy() - median,
            }
        )
    return out


def main() -> None:
    tz = local_tz()
    user = rhythm_user()

    arcaea = next((g for g in games() if g.key == "arcaea"), None)
    if arcaea is None:
        # A build with only another catalogue. Emitted as null rather than dropped: the
        # page is present either way and can say so, where a missing key would render as
        # a broken figure.
        json.dump(None, sys.stdout)
        return

    manager = arcaea.manager
    records = manager._records_asc(user)
    points = manager.potential_trend(user, only_changes=False)
    moves = _moves(records, points, tz, arcaea.difficulty_names, manager.best_capacity)
    performance = _performance(records, tz)

    json.dump(
        {
            "name": arcaea.name,
            "metric_label": arcaea.metric_label,
            "metric_note": arcaea.metric_note,
            "best_capacity": manager.best_capacity,
            # Arcaea ratings are always scored with the catalogue as it stands today.
            "rating_basis": "current",
            "timezone": str(tz),
            # Every play that moved the number, up as well as down. The downs are what
            # a pool does while it is still filling — a weak play taking an empty slot
            # drags the average down — so the page needs them to say when the pool
            # settled; it filters to the raises for the timeline itself.
            "moves": moves,
            # Every play, for the usual-level curve: a pool of personal bests can only
            # show the best ever, never a normal night.
            "plays": performance,
        },
        sys.stdout,
        ensure_ascii=False,
    )


if __name__ == "__main__":
    main()
