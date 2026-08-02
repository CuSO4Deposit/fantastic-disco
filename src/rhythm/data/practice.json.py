"""Repertoire versus skill: the deflated trend, discovery, and the fixed basket.

A separate loader from `games.json` rather than more keys on it, because the overview
does not need any of this and `games.json` already ships ~500kB.

The question all of it serves: a full best-N pool can never fall, since a play only
enters by beating the weakest. So potential and b30 measure the best N things ever done,
and they rise whenever a harder chart is attempted for the first time — no improvement
required. Everything here separates that from actually playing better.

Flattening only. The deflator, the discovery split, the session-position effect and the
attempt-matched basket are all `AnalysisMixin` methods, where they are tested; a second
copy of any of them here would let this page disagree with the `y` CLI.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from _shared import die, local_tz, rhythm_user
from catalogues import games
from y_offline.base.analysis import as_json

#: Charts to name in the untouched list. Enough to see what the wall looks like, few
#: enough that this stays a summary rather than a copy of the catalogue.
TOP_UNTOUCHED = 30

#: Only count a chart as untouched-and-interesting if it is within reach. A catalogue
#: holds hundreds of easy charts nobody bothered with, and listing those answers a
#: different and duller question than what is unattempted near the ceiling. Expressed
#: as an offset below the hardest chart ever played, so it scales with each game's own
#: rating scale instead of hardcoding one game's numbers.
REACH_BELOW_BEST = 1.0


def main() -> None:
    tz = local_tz()
    user = rhythm_user()

    out = {}
    for game in games():
        manager = game.manager
        if manager.activity(user, tz=tz) is None:
            out[game.key] = None
            continue

        # The summary is computed over every point, so its endpoint means are over real
        # plays rather than over the sparse set that happened to move the pool.
        deflated = manager.deflated_trend(user)
        basket = manager.fixed_basket(user)

        # What is unattempted, but only near the ceiling — see REACH_BELOW_BEST. The
        # ceiling comes from the rating bands, which already carry each played rating on
        # the scale the game displays; `ChartProgress` does not carry a rating at all.
        bands = manager.rating_bands(user)
        hardest = max((b.rating for b in bands), default=None)
        floor = 0.0 if hardest is None else hardest - REACH_BELOW_BEST
        untouched = manager.untouched_charts(user, min_rating=floor)

        out[game.key] = {
            "name": game.name,
            "metric_label": game.metric_label,
            "rating_basis": "current",
            "timezone": str(tz),
            # The decomposition, per play that moved the pool. `mean_rating` is the
            # repertoire half and `bonus` the execution half; they sum to `average`
            # exactly, since a metric here is a rating plus a function of accuracy.
            #
            # Only the points where the pool moved: this is a step function, so the rest
            # repeat the previous value and carry no information. That drops ~90% of a
            # series which is otherwise 97% of this file.
            "deflated": as_json(manager.deflated_trend(user, only_changes=True)),
            "deflated_summary": _summarise(deflated),
            # Why the difficulty-neutral index moved. Needed because a fall in it looks
            # like playing worse and usually is not: on this archive every single fall
            # coincided with the pool getting harder, so the raw series cannot be read
            # as regression without this split beside it.
            "bonus_split": as_json(manager.bonus_split(user)),
            # The one series here that can fall. Everything derived from the pool holds
            # personal bests, which never regress, so a pool-based index stays silent
            # about a bad month; this averages plays instead.
            "execution": as_json(manager.execution_trend(user, tz=tz)),
            "discovery": as_json(manager.discovery(user, tz=tz)),
            "positions": as_json(manager.session_position(user)),
            "basket": as_json(basket),
            "untouched": [
                {
                    "song_id": c.song_id,
                    "difficulty": game.difficulty_names.get(c.rating_class),
                    "rating": manager._chart_rating(c),
                    "name": _chart_name(c),
                }
                for c in untouched[:TOP_UNTOUCHED]
            ],
            "untouched_total": len(untouched),
            "untouched_floor": floor,
            "hardest_played": hardest,
            "catalogue_charts": len(manager.all_charts()),
        }

    if not any(out.values()):
        die(f"no records for {user!r} in any configured game")

    json.dump(out, sys.stdout, ensure_ascii=False)


def _chart_name(chart: object) -> str:
    """A chart's display name, whichever field this game's catalogue keeps it in.

    Arcaea's entries carry `name_en` and an optional `name_jp`; PJSK's and Cytus II's
    carry a single `name`. Falls back to the id rather than raising, since a missing
    title should cost a label and not the build.
    """
    for attribute in ("name", "name_jp", "name_en"):
        value = getattr(chart, attribute, None)
        if value:
            return value
    return chart.song_id


def _summarise(deflated: list) -> dict | None:
    """The headline split: how much of the rise was difficulty, how much execution.

    Endpoints are the mean of the first and last tenth rather than single points, so one
    unusual play cannot set the answer. Returns None below a length where a tenth is not
    a meaningful average.
    """
    if len(deflated) < 20:
        return None
    tenth = max(1, len(deflated) // 10)
    head, tail = deflated[:tenth], deflated[-tenth:]

    def mean(rows: list, key: str) -> float:
        return sum(getattr(r, key) for r in rows) / len(rows)

    return {
        "from_at": deflated[0].at,
        "to_at": deflated[-1].at,
        "points": len(deflated),
        "window": tenth,
        "average_change": mean(tail, "average") - mean(head, "average"),
        "rating_change": mean(tail, "mean_rating") - mean(head, "mean_rating"),
        "bonus_change": mean(tail, "bonus") - mean(head, "bonus"),
        "average_start": mean(head, "average"),
        "average_end": mean(tail, "average"),
    }


if __name__ == "__main__":
    main()
