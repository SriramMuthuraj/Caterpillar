# MOD-01 — Data Foundation

**Layer:** Foundation · **Owner:** M1 · **Implements:** A2, A4 · **Depends on:** nothing · **Window:** H1–H3, seed pass at H16–18
**Consumed by:** every other module. This is the root of the dependency graph.

---

## 1. Purpose

Produce the single canonical fleet dataset the whole system reads. Three jobs:

1. Load the 7 supplied rows **verbatim** and never mutate them.
2. Grow a defensible synthetic fleet and history around them so forecasting, anomaly baselines and a live-feeling demo are possible.
3. Place the timeline so that active, due-soon, overdue and unaccounted rentals all exist right now.

Nothing else in the system reads a CSV. Everything reads `MOD-01`'s output.

## 2. The central design problem

The supplied data cannot support the demo as given, for three independent reasons:

| Problem | Consequence |
|---|---|
| All dates are Jan–May 2025 | Zero active rentals → `FR-5` cannot fire |
| Seed rentals barely overlap in time | A single uniform date shift produces **one** active rental, not the mix we need |
| 7 rows, 4 types, 5 sites | No forecasting baseline, no anomaly distribution |

And yet: **the 7 rows and their defects are the product's whole argument.** They cannot be edited, smoothed, or regenerated.

### The resolution — two-layer history

> **Each seed row becomes a closed historical rental with its original numbers intact. Each seed asset then gets a *current* open rental, generated, whose telemetry profile is inherited from that asset's seed behaviour.**

Why this works:

- The integrity engine fires on the **real ground-truth rows**, provably, in front of judges. *"That finding is on the data you gave us, unmodified."*
- The same defect **also** appears live on the same asset now, so the dashboard is interesting without faking anything.
- We get complete control of the demo timeline without touching a single measurement.
- Every synthetic record is flagged `is_ground_truth=false` and is visually distinguishable in the UI.

The alternative — one uniform shift of all 7 rows — is simpler to explain but yields one active rental and no forecast history. Rejected.

### Honesty mechanic

Rebased rows keep `check_in_original` and `check_out_original`. The asset detail screen shows both:

> `Check-in 2026-07-02` · *original dataset value 2025-04-01 — calendar shifted, measurements unchanged*

When a judge asks "did you modify the data?", the screen has already answered.

## 3. Demo casting (declarative, not magic)

The current open rentals for the 7 seed assets are cast to guarantee every demo state exists. This lives in `data/gen_config.yaml` so it is auditable, not buried in code.

| Asset | Seed defect carried forward | Cast as | Serves |
|---|---|---|---|
| EQX1007 | engine 0, idle 12, site + operator NULL | **UNACCOUNTED**, 19 days overdue | The demo villain, `INT-03/04` |
| EQX1002 | engine 0, idle 11, site + operator NULL | **OVERDUE** 6 days, ghost asset | `INT-03/04`, economics |
| EQX1001 | idle 10 > engine 1.5 | **ACTIVE, due in 2 days** | `INT-02`, approaching-due alert |
| EQX1005 | idle exactly 0.0 for 30 days | **ACTIVE**, healthy-looking | `INT-05` stuck sensor — the subtle one |
| EQX1004 | idle 9 > engine 2 | **ACTIVE**, low utilization | `INT-02`, redeployment candidate |
| EQX1003 | rental_days 25 vs 24 actual | **RETURNED** recently | `INT-01` billing mismatch |
| EQX1006 | none | **ACTIVE**, healthy | The control case — proves we don't flag everything |

EQX1006 matters as much as EQX1007. A system that flags all seven assets has no credibility.

## 4. Synthetic fleet parameters

| Parameter | Value | Reason |
|---|---|---|
| Total assets | **45** (7 ground truth + 38 synthetic) | Big enough to look like a mid-size contractor's rented fleet, small enough to render fast |
| Equipment types | **6** — Excavator, Crane, Bulldozer, Grader, Loader, Compactor | 4 from seed + 2; keeps forecast cells populated |
| Sites | **8** — S001…S008 | The contractor's own project sites. Seed uses S001–S004, S006. **S005 is absent from the seed** — included so the fleet isn't suspiciously seed-shaped |
| Operators | **25** — OP101… | Seed uses OP101/106/114/203/301 |
| History | **12 months** ending at `T0` | Enough for weekly seasonality; one full annual cycle |
| Rentals generated | **~350** | ≈ 8 per asset-year |
| Telemetry ticks | daily per active rental, ≈ 16k rows | Trivial volume; no DB needed |
| Defect injection rate | **12%** of synthetic rentals | Gives the anomaly engine positives to find |
| Seed | **42**, single constant in config | `NFR-3` determinism |

### Forecast density — deliberately uneven

6 types × 8 sites = 48 cells over 52 weeks. ~350 rentals spread across 48 cells averages 7 rentals per cell — **thin**. That is intentional and correct:

- Aggregated **by type**, there is enough signal to forecast with tight intervals.
- Per **(type × site)**, many cells are too sparse → `MOD-11` legitimately returns `insufficient_data`.

This is not a limitation to hide. It is what makes `FR-6`'s refusal-to-forecast behaviour real rather than decorative.

### Hour profiles

Synthetic telemetry is drawn from per-type profiles **calibrated against the healthy seed rows**, not invented:

| Profile | engine h/day | idle h/day | Calibrated from |
|---|---|---|---|
| High utilization | 7.0–8.5 | 0.3–1.2 | EQX1003 (7.5 / 0.5) |
| Moderate | 4.0–6.5 | 1.5–3.5 | interpolated |
| Low utilization | 1.5–3.5 | 5.0–9.0 | EQX1004 (2 / 9), EQX1006 (3 / 6) |

Seasonality: monsoon months suppress engine hours ~30% and lift idle; year-end pushes demand up. Applied as a multiplicative factor per week-of-year so `MOD-11` has something genuine to learn.

## 5. The answer key — `defect_labels.csv`

The generator records every defect it injects: `{rental_id, equipment_id, defect_class, injected_at}`.

**This file is never read by `MOD-06`, `MOD-07` or `MOD-09`.** It exists solely to score them:

> *"Our rule engine recalls 94% of known injected defects at 2% false-positive rate — here is the harness."*

That sentence is worth more to an engineering panel than another chart. Injected classes mirror the real `INT-xx` rules: `idle_exceeds_engine`, `ghost_asset`, `orphan_custody`, `frozen_sensor`, `days_mismatch`, `stale_telemetry`, `day_budget_exceeded`.

Guard this boundary in review. If any engine imports `defect_labels`, the metric is worthless.

## 6. Storage decision — pandas in memory, no database

**Recommended: load Parquet/CSV into pandas at startup; expose a thin repository. No SQLite, no ORM, no migrations.**

| | Why |
|---|---|
| Volume | 45 assets, 350 rentals, 16k ticks. Kilobytes. A DB earns nothing |
| Setup cost | Four people on four machines — zero install steps, no schema drift, no "works on mine" |
| Determinism | Regenerating from a seed is trivially reproducible; a mutated DB is not |
| Speed of change | Column changes in hour 9 cost nothing. A migration costs 40 minutes |

The one append target is `CustodyEvent` (`MOD-03`), handled as an in-memory list mirrored to `data/generated/custody_events.jsonl` for durability across restarts.

**Committed artefacts:** generated Parquet files are committed. If the generator breaks at hour 20, the demo still runs from the snapshot. This is the cheapest insurance in the plan.

## 7. Interface

```python
# backend/ingest/schema.py
@dataclass(frozen=True)
class FleetData:
    assets:        pd.DataFrame   # equipment_id, type, model, site_id, is_ground_truth
    rentals:       pd.DataFrame   # rental_id, equipment_id, site_id, operator_id,
                                  # check_in, check_out, rental_days_stated,
                                  # rental_days_computed, day_rate, status,
                                  # is_ground_truth, check_in_original, check_out_original
    telemetry:     pd.DataFrame   # equipment_id, rental_id, ts, engine_hours,
                                  # idle_hours, fuel_l, lat, lon, source
    sites:         pd.DataFrame   # site_id, name, lat, lon, region
    operators:     pd.DataFrame   # operator_id, name
    defect_labels: pd.DataFrame   # EVALUATION ONLY — never read by engines

# backend/ingest/loader.py
def load_seed() -> pd.DataFrame          # exactly 7 rows, typed, unmodified
def load_fleet() -> FleetData            # the single entry point every module calls

# backend/ingest/generator.py
def generate(seed: int = 42, cfg: GenConfig | None = None) -> FleetData

# backend/ingest/rebase.py
def rebase(df: pd.DataFrame, t0: datetime, casting: dict) -> pd.DataFrame
```

`load_fleet()` is the only function other modules import. Everything else is internal to `MOD-01`.

## 8. Files owned

```
data/seed_assets.csv                  # the 7 rows, verbatim, NEVER EDITED
data/sites.yaml                       # S001..S008 with coords and region
data/gen_config.yaml                  # seed, fleet size, profiles, demo casting
data/generated/assets.parquet
data/generated/rentals.parquet
data/generated/telemetry.parquet
data/generated/defect_labels.csv      # the answer key
data/generated/custody_events.jsonl   # written by MOD-03
backend/ingest/{__init__,schema,loader,generator,rebase,profiles}.py
scripts/generate_data.py              # CLI: python scripts/generate_data.py --seed 42
```

## 9. Tests — write these first, they are cheap and they protect the thesis

| Test | Asserts |
|---|---|
| `test_seed_row_count` | exactly 7 rows |
| `test_seed_values_unmodified` | every cell equals the raw CSV byte-for-byte |
| `test_eqx1003_days_mismatch` | `rental_days_computed == 24` while `rental_days_stated == 25` |
| `test_nulls_preserved` | EQX1002 and EQX1007 still have null `site_id` **and** `operator_id` |
| `test_hours_preserved` | EQX1001 still has `idle 10 > engine 1.5`; EQX1005 still has `idle == 0.0` |
| `test_determinism` | `generate(42)` twice → identical dataframe hashes |
| `test_ground_truth_flag` | exactly 7 rentals have `is_ground_truth == True` |
| `test_originals_retained` | every rebased row has non-null `check_in_original` |
| `test_demo_casting` | all four demo states present at `T0`: active, due-soon, overdue, unaccounted |
| `test_defect_rate` | injection rate within ±3% of configured 12% |
| `test_forecast_density` | at least one (type × site) cell is sparse enough to trigger `insufficient_data` |

`test_seed_values_unmodified` is the most important test in the repository. It is the guard on the product's core claim.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Generator consumes the whole morning | **Hard timebox: H2:30.** If not working, commit a static 45-asset Parquet generated once by hand and move on. The generator is a means, not a deliverable |
| Synthetic data looks obviously fake | Profiles calibrated to seed rows; seasonality applied; nulls and defects distributed, not clustered |
| An engine imports `defect_labels` | Called out in review at H8 and H16 |
| Someone "fixes" the seed CSV | `test_seed_values_unmodified` fails loudly in CI |
| Rebasing confuses the team | One function, one config block, `*_original` columns retained |

## 11. Definition of Done

- [ ] `load_fleet()` returns a populated `FleetData` with all six frames
- [ ] All 11 tests pass
- [ ] `python scripts/generate_data.py --seed 42` is reproducible; artefacts committed
- [ ] At `T0` the fleet contains an active, a due-soon, an overdue and an unaccounted rental
- [ ] `MOD-04` and `MOD-06` can both consume the output without transformation
- [ ] Merged to `main` with `main` still running
