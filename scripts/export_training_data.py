"""Export a ready-to-train panel, so training needs no repo code.

    python scripts/export_training_data.py

Writes ``data/training/`` — three files that are the *only* things Colab needs:

    phase_panel.csv     one row per site-week, features already computed
    site_phases.csv     the observed phase windows (the baseline is fitted here)
    train_meta.json     feature lists, hyperparameters, dataset fingerprint

Feature engineering stays in ``backend/forecast/phase.py``. A notebook that
recomputed it would be a second implementation of the trickiest code in the
project, free to drift from this one without anyone noticing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.forecast import (  # noqa: E402
    clock_adapter, config, history, phase as phase_mod,
)

OUT_DIR = REPO_ROOT / "data" / "training"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    now = clock_adapter.now_date()

    rentals = history.cached_history(
        seed=config.MASTER_SEED, now=now, weeks=config.HISTORY_WEEKS
    )
    site_phases = history.site_phase_windows(
        now=now, weeks=config.HISTORY_WEEKS, seed=config.MASTER_SEED
    )
    panel = phase_mod.build_panel(rentals, site_phases, now=now)
    fingerprint = history.dgp_fingerprint()

    panel.to_csv(OUT_DIR / "phase_panel.csv", index=False)
    site_phases.to_csv(OUT_DIR / "site_phases.csv", index=False)

    meta = {
        "fingerprint": fingerprint,
        "as_of": now.isoformat(),
        "seed": config.MASTER_SEED,
        "n_panel_rows": int(len(panel)),
        "n_phase_windows": int(len(site_phases)),
        "phase_names": list(config.PHASE_NAMES),
        "classifier_features": list(phase_mod.CLASSIFIER_FEATURES),
        "duration_features": list(phase_mod.DURATION_FEATURES),
        "quantiles": list(phase_mod.QUANTILES),
        "interval_level": config.INTERVAL_LEVEL,
        "n_folds": phase_mod.N_FOLDS,
        "min_completed_phases": phase_mod.MIN_COMPLETED_PHASES,
        "schema_version": 1,
    }
    (OUT_DIR / "train_meta.json").write_text(json.dumps(meta, indent=2))

    print(f"fingerprint {fingerprint}")
    print(f"panel       {len(panel):,} rows x {len(panel.columns)} cols")
    print(f"windows     {len(site_phases)}")
    print()
    print("Upload these three to Colab alongside train_phase_models.ipynb:")
    for name in ("phase_panel.csv", "site_phases.csv", "train_meta.json"):
        path = OUT_DIR / name
        print(f"  data/training/{name:20s} {path.stat().st_size / 1024:8.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
