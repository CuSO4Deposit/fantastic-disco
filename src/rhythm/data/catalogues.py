"""Building Y-Offline managers without a config.toml, and naming their difficulties.

Y-Offline's own entry point is `get_config_info`, which reads `config.toml` from the
*Y-Offline checkout* and exits if it is absent. That is right for the `y` CLI and wrong
here: this build has no checkout of its own to configure, the paths it needs come from
the environment like every other source's do, and a game section missing from someone
else's config file would silently drop a game from the site. So the config models are
constructed directly — they are pydantic models with public fields, not internals.

Which games appear is decided by which catalogues are pointed at. A game whose
catalogue is unset is left out entirely rather than emitted empty: Y-Offline cannot
rate a single play without one, so "no catalogue" and "never played" would otherwise
render identically.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from _shared import die, env_path, rhythm_db


@dataclass(frozen=True)
class Game:
    """One game's manager, plus what a page needs to label it."""

    key: str
    name: str
    manager: object
    difficulty_names: dict[int, str]
    metric_label: str
    """What `metric()` means for this game, for an axis label. The pools rank on it
    and the number is not comparable across games — Arcaea's is a play potential on
    the same 0-13 scale as a chart's rating, PJSK's is a level plus an accuracy bonus
    on a 5-33 scale."""

    metric_note: str
    """One sentence a page can print to say what the metric is, so a chart of it is
    not an unexplained number."""


def _arcaea() -> Game | None:
    """Arcaea, if `ARCSONG_DB` names a catalogue."""
    if not os.environ.get("ARCSONG_DB"):
        return None
    from y_offline.arcaea.utils import (
        DIFFICULTY_NAMES,
        ArcaeaChartRepository,
        ArcaeaManager,
    )

    path = env_path("ARCSONG_DB", "arcsong.db from ArcaeaSongDatabase")
    return Game(
        key="arcaea",
        name="Arcaea",
        manager=ArcaeaManager(
            chart_repo=ArcaeaChartRepository(arcsong_path=path),
            userdb_path=rhythm_db(),
        ),
        difficulty_names=DIFFICULTY_NAMES,
        metric_label="Play potential",
        metric_note=(
            "a play's potential: the chart's rating plus a bonus above 98% accuracy, "
            "which is the number b30 averages"
        ),
    )


def _pjsk() -> Game | None:
    """Project SEKAI, if both master-db files are pointed at.

    Two files rather than one because the catalogue is split: `musics.json` carries
    titles and `musicDifficulties.json` the levels and note counts. Requiring both
    together keeps a half-configured game from producing charts with no note count,
    which is what every accuracy here divides by.
    """
    if not os.environ.get("PJSK_MUSICS_JSON"):
        return None
    from y_offline.pjsk.utils import (
        DIFFICULTY_NAMES,
        PjskJsonChartRepository,
        PjskManager,
    )

    musics = env_path("PJSK_MUSICS_JSON", "musics.json from sekai-master-db-diff")
    difficulties = env_path(
        "PJSK_DIFFICULTIES_JSON",
        "musicDifficulties.json from sekai-master-db-diff",
    )
    return Game(
        key="pjsk",
        name="Project SEKAI",
        manager=PjskManager(
            chart_repo=PjskJsonChartRepository(
                musics_path=musics, difficulties_path=difficulties
            ),
            userdb_path=rhythm_db(),
        ),
        difficulty_names={k: v.title() for k, v in DIFFICULTY_NAMES.items()},
        metric_label="Play score",
        metric_note=(
            "the chart's level plus an accuracy bonus mapping 99%-100% onto 0-2, "
            "which is the number b30 averages"
        ),
    )


def _cytus2() -> Game | None:
    """Cytus II, if a hand-maintained charts.json is pointed at.

    Optional like the others, and in practice usually absent: the public chart source
    it is bootstrapped from was archived in 2026-05, so this file is maintained by
    hand rather than pulled.
    """
    if not os.environ.get("CYTUS2_CHARTS_JSON"):
        return None
    from y_offline.cytus2.utils import (
        DIFFICULTY_NAMES,
        Cytus2JsonChartRepository,
        Cytus2Manager,
    )

    path = env_path("CYTUS2_CHARTS_JSON", "a Cytus II charts.json")
    return Game(
        key="cytus2",
        name="Cytus II",
        manager=Cytus2Manager(
            chart_repo=Cytus2JsonChartRepository(charts_json_path=path),
            userdb_path=rhythm_db(),
        ),
        difficulty_names=DIFFICULTY_NAMES,
        metric_label="Play score",
        metric_note=(
            "the chart's level plus a bonus mapping 90%-100% TP onto 0-1; zero for "
            "the beta and gamma charts, which have no numeric level"
        ),
    )


def games() -> list[Game]:
    """Every game this build can rate, in the order pages should list them.

    Empty is a hard error rather than an empty site: reaching a rhythm loader at all
    means `src/rhythm/` was kept, and keeping it without a single catalogue would
    publish pages that silently claim nothing was ever played.
    """
    present = [g for g in (_arcaea(), _pjsk(), _cytus2()) if g is not None]
    if not present:
        die(
            "no rhythm game catalogues configured; set at least one of ARCSONG_DB, "
            "PJSK_MUSICS_JSON or CYTUS2_CHARTS_JSON, or drop src/rhythm/"
        )
    return present


def fingerprint() -> str:
    """The configured catalogues and player, for detecting changes between runs.

    Framework compares a cached output's mtime against the loader script only, so it
    cannot see that a catalogue was repointed or that the player changed. Both change
    every number on these pages. See `scripts/refresh.py`.
    """
    names = (
        "YOFFLINE_DB",
        "YOFFLINE_USER",
        "ARCSONG_DB",
        "PJSK_MUSICS_JSON",
        "PJSK_DIFFICULTIES_JSON",
        "CYTUS2_CHARTS_JSON",
    )
    return "\n".join(f"{n}={os.environ.get(n, '')}" for n in names)
