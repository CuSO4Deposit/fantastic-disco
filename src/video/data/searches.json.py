"""Search history, accumulated across snapshots.

Not filtered by the denylist: a query is what was typed, and has no uploader to
match against.
"""

import json
import sys
from pathlib import Path

# A loader runs with only its own directory on sys.path, so src/lib needs adding.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

import fandoms
from _shared import SERVICE_NAMES, exports
from cuso4d import pipepipe as pp


def main() -> None:
    rows = [
        {
            "service": SERVICE_NAMES.get(s.service_id, str(s.service_id)),
            "query": s.query,
            "when": s.when.isoformat(),
            "fandoms": fandoms.tags(s.query),
        }
        for s in pp.searches(exports())
    ]
    json.dump(rows, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
