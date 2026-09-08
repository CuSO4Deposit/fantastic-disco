"""Per-game summary, potential over time, and rating bands, from Y-Offline.

Everything here is flattening and renaming over `y_offline.base.analysis`. The pool is
replayed by the SDK's own `replay_best` — Arcaea v7 dropped the recent pool that once
sat beside it — so this file never decides what enters a pool, and a second copy of that
truth table would let these pages disagree with the `y` CLI while both looked right.

Two things this loader does decide, both presentation:

- Which timezone splits a day. The SDK takes `tz` and defaults to UTC; a dashboard that
  also counts days from the band must pass the same zone, so `CPI_LOCAL_TZ` is used
  here as everywhere else.
- Which trend series a page gets. `best_trend` is keyed on plays and `daily_trend` on
  calendar days; both are emitted because they answer different questions, and
  resampling in the page is how two charts end up disagreeing.

The rating caveat travels with the data: ratings come from each catalogue *as it stands
today*, so a replayed history scores old plays with today's numbers. `rating_basis`
comes straight from the SDK and every page prints it.
"""

import datetime
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from _shared import die, local_tz, rhythm_user
from catalogues import games
from y_offline.base.analysis import as_json

#: Plays on one chart before it appears in the progress table. One play has no gain to
#: report — `gain` is best minus first — so a table of them would be mostly zeros.
MIN_PROGRESS_PLAYS = 2

#: A run of unplayed days this long is reported as a break rather than left to the eye.
#: Both games here have a hiatus over a year long, across which `daily_trend` carries
#: the last value forward — correct, since the pool really did hold, but a flat line
#: spanning a third of the chart reads as a plateau of skill rather than absence.
BREAK_DAYS = 30


def _breaks(daily: list[dict]) -> list[dict]:
    """Runs of at least `BREAK_DAYS` consecutive days with no play.

    Derived from `daily_trend`'s `played` flag rather than recomputed from records, so
    a break is by construction the same stretch the trend line carries across.
    """
    out = []
    for played, group in itertools.groupby(daily, key=lambda d: d["played"]):
        if played:
            continue
        days = [d["day"] for d in group]
        if len(days) >= BREAK_DAYS:
            out.append({"from": days[0], "to": days[-1], "days": len(days)})
    return out


def _sessions(activity: object, tz: datetime.tzinfo) -> list[dict]:
    """The SDK's sittings, each labelled with the local day and hour it began.

    Computed here rather than in a page because a page reading `getHours` off a `Date`
    gets whatever timezone the browser is in, which is not where these were played —
    on a UTC build machine a 01:00 session would display as an evening.

    A sitting is attributed to the day it *started*, the same convention the band's
    nights use: a session that runs past midnight is one sitting, and splitting it
    would report two half-sittings and no whole one.

    The hour is when a sitting began, not when each play happened. That is the honest
    version of "when does play happen": `time` is written by `y ... add`, and `--back`
    shifts a backfilled play by whole days while keeping the clock time it was typed
    at, so a per-play hour would mix playing time with data-entry time.
    """
    out = []
    for session in activity["sessions"]:
        start = datetime.datetime.fromtimestamp(session["started_at"], tz)
        out.append(
            {
                **session,
                "day": start.date().isoformat(),
                "hour": start.hour,
            }
        )
    return out


def main() -> None:
    tz = local_tz()
    user = rhythm_user()

    out = {}
    for game in games():
        manager = game.manager
        activity = manager.activity(user, tz=tz)
        if activity is None:
            # No records at all for this player in a configured game. Emitted as an
            # explicit null rather than omitted, so a page can say "configured but
            # never played" instead of leaving the game silently off the site.
            out[game.key] = None
            continue

        summary = manager.summary(user, tz=tz)
        activity_json = as_json(activity)
        activity_json["sessions"] = _sessions(activity_json, tz)
        daily = as_json(manager.daily_trend(user, tz=tz))
        out[game.key] = {
            "name": game.name,
            "metric_label": game.metric_label,
            "metric_note": game.metric_note,
            "best_capacity": manager.best_capacity,
            "rating_basis": summary["rating_basis"],
            "timezone": str(tz),
            "activity": activity_json,
            "current_average": summary["current_average"],
            # Each judgement with the denominator it is actually a share of, rather than
            # raw counts a page would have to divide itself. Arcaea's `max_pure` is a
            # subdivision of `pure` — it counts how many pure notes were perfectly
            # timed — so dividing it by the sum of all judgements double-counts every
            # pure note. The SDK carries the nesting; see `judgement_parents`.
            "judgements": as_json(manager.judgement_shares(user)),
            "bands": as_json(manager.rating_bands(user)),
            # Only the plays that moved the pool. The unchanged ones are a flat line
            # between them and inflate the series by an order of magnitude — on the
            # Arcaea archive most plays never enter the pool at all.
            #
            # Emitted separately from `potential` below rather than derived from it:
            # `trend` is the plain pool average, while that series keeps the points
            # where the headline number moved, and Arcaea's headline is not its pool
            # average — v7 counts the pool's top ten twice.
            "trend": as_json(manager.best_trend(user, only_changes=True)),
            # One value per calendar day, carried across days not played, because the
            # pool genuinely holds when nobody plays. `played` marks which is which.
            "daily": daily,
            "breaks": _breaks(daily),
            "progress": [
                {**as_json(c), "difficulty": game.difficulty_names.get(c.rating_class)}
                for c in manager.chart_progress(user, min_plays=MIN_PROGRESS_PLAYS)
            ],
            # Judgements that cannot have happened. Zero on this archive, and emitted
            # anyway: it is the number that says whether the averages above can be
            # trusted, and a page that never mentions it cannot report it appearing.
            "implausible": [
                {
                    "name": r.name,
                    "song_id": r.song_id,
                    "difficulty": game.difficulty_names.get(r.rating_class),
                    "at": r.time,
                    "accuracy": r.accuracy(),
                }
                for r in manager.implausible(user)
            ],
            "difficulty_names": game.difficulty_names,
            # Arcaea alone has a headline number distinct from its pool average — v7
            # counts the pool's best ten twice — so this is the real potential the app
            # displays rather than a pool average. Absent for every other game rather
            # than faked from their pool.
            "potential": (
                as_json(manager.potential_trend(user))
                if hasattr(manager, "potential_trend")
                else None
            ),
        }

    if not any(out.values()):
        die(
            f"no records for {user!r} in any configured game; refusing to emit an "
            "empty dashboard (is YOFFLINE_USER the right player?)"
        )

    json.dump(out, sys.stdout, ensure_ascii=False, default=_plain)


def _plain(value: object) -> object:
    """Last resort for a type `as_json` passed through untouched.

    Raises rather than stringifying: a silently str()-ed number would reach a chart as
    a category and draw one band per value.
    """
    if isinstance(value, datetime.date):
        return value.isoformat()
    raise TypeError(f"cannot serialise {type(value).__name__}")


if __name__ == "__main__":
    main()
