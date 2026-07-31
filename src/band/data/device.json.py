"""The band as a device: battery history and what it says about itself.

Separate from the body-facing loaders because it answers a different question — how
the hardware is holding up, rather than anything about the wearer. Small enough to
emit raw, unlike the minute series.
"""

import json
import sys
from pathlib import Path

# A loader runs with only its own directory on sys.path, so src/lib needs adding.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from _shared import exports, local_tz
from cuso4d import gadgetbridge as gb

#: Discharge runs losing fewer points than this are emitted but flagged as too short
#: to read a rate from — a run of one or two points is mostly the band's own rounding.
#: A presentation choice; where a run *begins and ends* is device semantics and lives
#: in CPI.
MIN_INFORMATIVE_DROP = 10

#: And a floor on elapsed time, because the rate depends on it. Drain measured over a
#: short window reflects whatever the band was doing in those hours — continuous heart
#: rate, screen wakes — rather than a baseline: runs under a day come out near
#: 14 %/day against 3 %/day for runs over four. The last run in an archive is always
#: partial, so without this the most recent point is also the most misleading one.
#: The aging trend holds either way (r ≈ 0.49 with or without), so this narrows what
#: is claimed rather than propping up the claim.
MIN_INFORMATIVE_HOURS = 48


def main() -> None:
    tz = local_tz()
    archive = exports("CPI_GADGETBRIDGE_EXPORTS", "Gadgetbridge backups")

    readings = list(gb.battery(archive))
    if not readings:
        sys.exit("no battery readings in the archive; refusing to emit an empty page")

    levels = [
        {
            "when": reading.when.astimezone(tz).isoformat(),
            "level": reading.level,
        }
        for reading in readings
    ]

    # Segmentation is CPI's; this only flattens. `percent_per_day` is deliberately not
    # extrapolated to "days a full charge lasts" — see the model for why that number
    # is unusable.
    runs = [
        {
            "start": run.start.astimezone(tz).isoformat(),
            "hours": round(run.duration.total_seconds() / 3600, 2),
            "from_level": run.from_level,
            "to_level": run.to_level,
            "drop": run.drop,
            "percent_per_day": round(rate, 3),
        }
        for run in gb.parser.discharge_runs(readings)
        if (rate := run.percent_per_day) is not None
    ]

    device = next(iter(gb.devices(archive).values()), None)

    json.dump(
        {
            "timezone": str(tz),
            "device": (
                None
                if device is None
                else {
                    "name": device.name,
                    "manufacturer": device.manufacturer,
                    "model": device.model,
                    # Deliberately not the identifier: it is a MAC address, and this
                    # file ends up in a published build.
                }
            ),
            "levels": levels,
            "discharge_runs": runs,
            "min_informative_drop": MIN_INFORMATIVE_DROP,
            "min_informative_hours": MIN_INFORMATIVE_HOURS,
        },
        sys.stdout,
        ensure_ascii=False,
    )


if __name__ == "__main__":
    main()
