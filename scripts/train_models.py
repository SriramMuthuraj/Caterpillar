"""Train the phase models and write them to models/.

    python scripts/train_models.py                  # both
    python scripts/train_models.py --only end       # just the phase-end model
    python scripts/train_models.py --no-write       # score only, touch nothing

Two models, two files:

    models/phase_classifier.pkl   which phase is this site in?
    models/phase_end.pkl          when does that phase end?

You do not have to run this. ``service.build()`` trains whatever is missing or
stale at startup anyway — the artifacts exist so the models can be inspected,
handed to someone else, or retrained on their own, not to save the four seconds
training actually takes.

Each file records the fingerprint of the dataset it was trained on. Regenerate
the data without retraining and the app notices, says so, and refits rather than
serving a model fitted to data that no longer exists.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.forecast import (  # noqa: E402
    artifacts, clock_adapter, config, history, phase as phase_mod,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--only", choices=("classifier", "end", "both"), default="both",
        help="which model to train (default: both)",
    )
    parser.add_argument(
        "--no-write", action="store_true",
        help="train and report scores without writing any file",
    )
    parser.add_argument(
        "--refresh-data", action="store_true",
        help="regenerate the rental history before training",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    now = clock_adapter.now_date()
    print(f"clock       {now}  (config.DEMO_NOW, never the wall clock)")

    started = time.perf_counter()
    rentals = history.cached_history(
        seed=config.MASTER_SEED, now=now, weeks=config.HISTORY_WEEKS,
        refresh=args.refresh_data,
    )
    site_phases = history.site_phase_windows(
        now=now, weeks=config.HISTORY_WEEKS, seed=config.MASTER_SEED
    )
    panel = phase_mod.build_panel(rentals, site_phases, now=now)
    fingerprint = history.dgp_fingerprint()

    print(f"dataset     {len(rentals):,} rentals · {len(site_phases)} phase "
          f"windows · {len(panel):,} panel rows")
    print(f"fingerprint {fingerprint}")
    print()

    if args.only in ("classifier", "both"):
        t0 = time.perf_counter()
        clf = phase_mod.PhaseClassifier().fit(panel)
        elapsed = time.perf_counter() - t0
        report = clf.report
        print(f"phase_classifier   fitted in {elapsed:.1f}s")
        if report is not None:
            chance = 1.0 / len(config.PHASE_NAMES)
            print(f"  accuracy         {report.accuracy:.3f}  "
                  f"(chance {chance:.3f})")
            print(f"  within one phase {report.within_one_phase:.3f}")
            print(f"  held-out windows {report.n_test_windows}")
        if not args.no_write:
            print(f"  -> {artifacts.save_classifier(clf, fingerprint)}")
        print()

    if args.only in ("end", "both"):
        t0 = time.perf_counter()
        end = phase_mod.PhaseEndModel().fit(panel, site_phases)
        elapsed = time.perf_counter() - t0
        report = end.report
        print(f"phase_end          fitted in {elapsed:.1f}s")
        if report is not None:
            print(f"  MAE              {report.mae_weeks:.2f} weeks")
            print(f"  baseline MAE     {report.baseline_mae_weeks:.2f} weeks")
            print(f"  skill            {report.skill:+.1%}")
            print(f"  coverage @{config.INTERVAL_LEVEL:.0%}     "
                  f"{report.coverage:.3f}  "
                  f"(raw {report.raw_coverage:.3f}, "
                  f"pad {report.interval_pad_weeks:.2f} w)")
        refused = sorted(set(config.PHASE_NAMES) - end.trainable_phases)
        if refused:
            print(f"  refuses          {', '.join(refused)} "
                  f"(too few completed windows — insufficient_data)")
        if not args.no_write:
            print(f"  -> {artifacts.save_phase_end(end, fingerprint)}")
        print()

    print(f"done in {time.perf_counter() - started:.1f}s"
          + ("  (nothing written: --no-write)" if args.no_write else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
