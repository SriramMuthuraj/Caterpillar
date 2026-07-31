"""Regenerate the Cat_SRTS seed files from the generated rental history.

    python scripts/build_demo_data.py            # write the four seed files
    python scripts/build_demo_data.py --dry-run  # report what would change

Cat_SRTS shipped with a hand-written 20-machine fixture in its own id space
(``EQ-001``, free-text ``siteName``). The forecast models and the anomaly
detector run on a 677-machine generated history (``EQX2001``, ``S001``-``S024``).
Two fleets, no shared ids: the dashboard would say "20 machines" while the
forecast page said "296 active", and a judge notices that immediately.

This rewrites his seeds as a projection of the same history — every machine in
the operational store is there because it has a rental spanning ``DEMO_NOW``. It
is a change of *contents*, not of schema: the documents keep his exact camelCase
field names, so no service, route or React type on his side changes.

The originals are preserved as ``*_seed.original.json`` on first run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.forecast import clock_adapter  # noqa: E402
from backend.integration import dataset  # noqa: E402

SEED_DIR = REPO_ROOT / "Cat_SRTS" / "database"

FILES = {
    "equipment": "equipment_seed.json",
    "operators": "operators_seed.json",
    "assignments": "assignments_seed.json",
    "usage_logs": "usage_logs_seed.json",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="report counts without writing anything")
    parser.add_argument("--no-backup", action="store_true",
                        help="skip preserving the original seed files")
    args = parser.parse_args()

    now = clock_adapter.now_date()
    print(f"clock  {now}  (config.DEMO_NOW)")

    snapshot = dataset.live_snapshot(now)

    print()
    print(f"{'collection':14s} {'existing':>9s} {'new':>7s}")
    for key, filename in FILES.items():
        path = SEED_DIR / filename
        existing = len(json.loads(path.read_text(encoding="utf-8"))) \
            if path.exists() else 0
        print(f"{key:14s} {existing:9d} {len(snapshot[key]):7d}")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    print()
    for key, filename in FILES.items():
        path = SEED_DIR / filename
        backup = SEED_DIR / filename.replace("_seed.json", "_seed.original.json")

        # Preserve his fixture once, on the first run only — a second run must
        # not overwrite the backup with our own generated output.
        if path.exists() and not backup.exists() and not args.no_backup:
            backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"  preserved  {backup.name}")

        path.write_text(
            json.dumps(snapshot[key], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  wrote      {filename}  ({len(snapshot[key])} documents)")

    print()
    print("Seeds now describe the same fleet as the forecast and anomaly views.")
    print("To load them into Atlas:  python Cat_SRTS/database/seed.py")
    print("Without Atlas they are served from memory — see database.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
