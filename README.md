# FleetTrust

Smart equipment-rental tracking for a contractor who rents plant from Cat
dealers across multiple sites.

> FleetTrust knows what phase each project is in — and uses that to predict what
> equipment you will need next, and to judge whether a machine's behaviour is
> actually abnormal.

---

## Run it

```bash
pip install -r requirements.txt

# 1. the backend — one process, one port, everything on it
uvicorn backend.main:app --port 8000

# 2. the frontend
cd Cat_SRTS/frontend && npm install && npm run dev      # :3000
```

Open <http://127.0.0.1:3000>. No database, no network and no API keys are
required: if MongoDB Atlas is unreachable the seed files are served from memory,
the Gemini narration layer is off, and email alerts dry-run.

First start takes about 40 seconds — the forecast bundle and the anomaly scores
are built during startup, deliberately, so nothing is computed on a click.

## What is here

| Module | Owns | Runs |
|---|---|---|
| `backend/forecast/` | Phase detection, phase-end prediction, allocation | FastAPI router |
| `anomaly_detection/` | 13 rules over the rental history | FastAPI router + standalone Streamlit |
| `Cat_SRTS/` | Equipment, operators, assignments, usage, dashboard, alerts | Flask, mounted inside FastAPI |
| `Cat_SRTS/frontend/` | The UI — 10 pages | React + Vite |
| `backend/integration/` | The joins between all of the above | — |
| `alert/`, `qr/` | SMTP and QR helpers | wrapped as endpoints |

Everything is served from **:8000**. FastAPI hosts, its routes match first, and
the Flask app catches the rest — so the frontend has one base URL and CORS never
becomes a question. `Cat_SRTS/backend/app.py` still runs standalone on :5000 if
you want it to.

## One dataset, three views

This is the idea the whole integration rests on. The generated rental history is
the single source of truth; everything else is a **projection** of it, so no two
screens can contradict each other.

```
data/forecast_cache/rental_history_*.csv     7,209 rentals · 677 machines · 3 years
   │
   ├─ HISTORY   all rows          →  forecast models, anomaly rules
   ├─ LIVE      active at `now`   →  MongoDB / in-memory store   (296 on hire)
   └─ ANOMALY   renamed columns   →  the detector's 9-column schema
```

The operational store is *derived*, never authored: a machine is in it because
it has a rental spanning the demo clock. Seed it by hand instead and the
dashboard says "20 machines" while the forecast page says "296 active" — a
contradiction anyone spots in five seconds.

```bash
python scripts/build_demo_data.py     # rebuild the operational store from the history
python scripts/train_models.py        # retrain the two phase models
```

## The two differentiators

**Demand forecast.** `check_in` is when a machine is rented; `check_out` is when
the rent *expires*. Two clocks, set by different people, that do not line up:

| condition | meaning | action |
|---|---|---|
| rent expires **before** the phase ends | the machine walks off mid-work | extend, or line up a replacement |
| phase ends **before** the rent expires | you are paying for a machine nobody needs | **move it to a site that does** |

A machine comes free at `min(phase end, contract expiry)`, and the answer says
which bound bit. Redeployment does not pay hire — that contract is already
running — which is why moving usually beats renting, and why both prices are
always shown.

**Anomaly detection.** Peers are compared within machine type, site and
operator; none of those knows what stage the project is at. Every finding
carries the project phase, because 20% utilisation is unremarkable during
structural erection and alarming during earthworks, and the rule cannot tell you
which.

## Measured

| | |
|---|---|
| Phase classification | **0.746** accuracy (chance 0.167), 0.997 within one phase |
| Phase-end error | **2.25 weeks** vs 2.75 baseline → **+18.1%** skill |
| Interval coverage @ 80% | **0.801** (0.395 before conformal calibration) |
| Anomaly scoring | 7,209 rows in **8 s**, 1,321 flagged, 120 critical |
| Allocation | 61 recommendations, **₹14.8L** saving, 66 machines running past need |

Demobilisation returns `insufficient_data` rather than a number: no site has
been observed finishing one, and a fabricated figure there would be acted on by
the allocator.

## Tests

```bash
python -m pytest backend/forecast/tests/ -q       # models, leakage, determinism  (~10 min)
python -m pytest backend/integration/tests/ -q    # the joins between modules     (~1 min)
python -m pytest anomaly_detection/tests/ -q      # the detector's golden fixture (~1 s)
```

The integration suite covers the seams — the places where two people's
assumptions meet and a mistake is silent rather than loud. The sharpest is the
naming inversion: Cat_SRTS's `checkOutTime` is the machine *leaving the yard*,
while the forecast module's `check_out` is the *contract expiring*. Same word,
opposite ends of a rental, and it gets its own test.

## Invariants

- **No `datetime.now()`.** Every date in the dataset is historical; the wall
  clock makes nothing active, empties the allocation board and fills the alerts
  page with false overdues. `clock_adapter` is the only source of "now",
  enforced by an AST walk in the test suite.
- **Derived values are never persisted.** Asset status, phase state, freed-at
  dates and every cost are computed on read.
- **Models never outlive their data.** Each `.pkl` records the fingerprint of
  the dataset it was fitted to; a mismatch retrains rather than serves.
- **Refuse rather than fabricate.** `insufficient_data` is a 200, not an error.
- **The detector's rules were not edited.** The dataset is renamed on the way in
  and the phase is joined on the way out; its golden test passes byte-identical.

## Known gaps

`data/seed_assets.csv` is absent, so rental durations run on documented fallback
distributions and `calibrated_to_seed_rows` is `false` in every response. Drop
the file in and regenerate; nothing else is blocked by it.

The Gemini narration layer in `anomaly_detection/` is off by default and
imported lazily — it needs network and sleeps 40 seconds on rate limits, so it
has no place on a demo path.
