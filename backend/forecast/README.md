# Demand Forecast & Allocation

**What phase is each site in, when does that phase end, and what should you do
about the machines?**

---

## The idea in one table

`check_in` is when a machine is rented; `check_out` is when the rent **expires**.
So there are two clocks, set by different people, and they do not line up:

| clock | span | status |
|---|---|---|
| **contract** | `check_in` → `check_out` | known exactly |
| **work** | phase start → phase end | **predicted** |

Every mismatch is money, and which way it misses decides what to do:

| condition | meaning | action |
|---|---|---|
| rent expires **before** the phase ends | the machine walks off mid-work | extend, or line up a replacement |
| phase ends **before** the rent expires | you are paying for a machine nobody needs | **move it to a site that does** |

The second row is the product. A machine whose phase has finished but whose
contract runs another three weeks is capacity you have **already bought** —
moving it costs haulage, leaving it costs the full day rate for nothing.

A machine therefore comes free at:

```
freed_at = min( end of the phase it is working , contract expiry )
```

Both bounds matter, and the answer records which one bit — "free in 9 days
because foundation finishes" and "free in 9 days because the rent runs out" are
different conversations.

## Three components, two models

| # | Question | How |
|---|---|---|
| 1 | Which phase is this site in? | `XGBClassifier`, 6 classes |
| 2 | When does that phase end? | `XGBRegressor`, quantile objectives → a **range** |
| 3 | What does the next phase need? | Lookup table — **no model** |

One library, used twice, on the only two things that are genuinely uncertain.
Question 3 is six rows measured from history; fitting a learner to it would be
memorising a table and inviting the question of why a model was used at all.

## Measured results

Everything below is out-of-fold, folded over **whole phase windows** — never
individual weeks. `GET /api/phase/model` returns all of it.

| | |
|---|---|
| Phase classification accuracy | **0.746** (chance = 0.167) |
| …within one phase | **0.997** |
| Phase-end error | **2.25 weeks** |
| …schedule-only baseline | 2.75 weeks |
| …skill vs baseline | **+18.1%** |
| Interval coverage @ 80% | **0.801** (raw 0.395, conformal pad 1.89 w) |
| Training data | 60 completed phase windows · 1,159 site-weeks |

**Demobilisation is refused, not predicted.** It is the last phase, so no site
has been observed finishing one, and `insufficient_data` is the correct answer.
A fabricated number there would be acted on by the allocator.

## The three things that were wrong before they were right

Worth knowing, because each one produced a plausible-looking number that meant
nothing.

**1. Predicting "weeks remaining" directly.** Remaining = total − elapsed, and
elapsed is a *known input*, so the model was being asked to learn a subtraction —
which tree ensembles approximate with a staircase of splits. It lost to the
baseline by 63%. Predicting the phase's **total** length and subtracting elapsed
ourselves put the arithmetic where arithmetic belongs.

**2. Slip drawn independently per phase.** If each phase's overrun is an
independent coin flip, nothing observable predicts it and *no* model can beat
"the average phase takes N weeks" — correctly, because there is genuinely
nothing to know. Real schedule performance is autocorrelated within a project:
the same crew, ground and client are there in month nine as in month two. So
slip is now mostly a persistent per-site `pace`, which makes a site's own track
record predictive — and `site_pace_observed` is what lets the model win.

**3. An 80% interval that covered 40%.** Quantile regression fits its quantiles
on the training data, and on a few hundred rows the P10/P90 collapse toward the
median. Bands are now widened by conformalized quantile regression (Romano,
Patterson & Candès 2019), calibrated on out-of-fold conformity scores, giving
0.801 measured coverage. Both figures are reported — `interval_coverage` and
`interval_coverage_before_calibration`.

## Leakage — why any of these numbers mean anything

Two rules, both enforced by tests.

**Nothing the simulator knows reaches a model.** Not `Site.pace`, not the drawn
durations, not the true phase boundary. Features come from the rental records
and the calendar, which is what a real deployment has.
`test_no_generator_parameter_reaches_the_models` checks the feature lists by
name, since that is the boundary a future edit is most likely to cross.

**Splits hold out whole phase windows.** Weeks inside one window are
near-duplicates — same site, same machines, a mix that moved slightly. Split at
random and week 3 lands in train while week 4 lands in test; the model
recognises the site rather than the pattern and the score is a fiction.
`test_splits_hold_out_whole_windows_not_weeks` asserts it.

`site_pace_observed` is deliberately the most dangerous feature and gets its own
test: it is built strictly from phases that had **already finished** when the
row was observed, and `test_pace_feature_only_uses_already_finished_phases`
recomputes it from scratch to confirm.

## Why the classifier exists at all

The generator writes the true phase onto every rental row, so the pipeline runs
end to end from minute one and the anomaly detector is never blocked waiting on
this module.

But "we know what phase your site is in" has to be a *capability*, not a column
read. If the only answer to *"how would this work on real data?"* is "our own
simulator told us", the claim collapses. So the classifier recovers the label
from the equipment on the ground — the same signal a real deployment would
have — and its accuracy is published next to every prediction, including the
per-phase breakdown that shows where it is weak.

The signal it lives on, measured from the generated history:

| phase | Excavator | Wheel Loader | Backhoe | Telehandler | Compactor |
|---|---|---|---|---|---|
| clearing | **43%** | 26% | 24% | 6% | 2% |
| excavation | 40% | 24% | 26% | 8% | 2% |
| foundation | 32% | 25% | 26% | 12% | 4% |
| erection | 18% | 19% | 31% | 20% | 12% |
| grading | 8% | 9% | 30% | **28%** | 25% |
| demobilisation | 2% | 8% | 40% | 19% | **31%** |

Machines *arriving* matter more than machines *standing there*: a 25-day
excavator rental taken in week 2 of excavation is still on site in week 5 of
foundation, so the standing mix lags by roughly a rental length and smears every
boundary. Arrival mix turns a phase change from a drift into a step, and it is
the second-strongest feature after site age.

## Deciding with money, not a threshold

"Wait if the delay is under ten days" is a number nobody can defend. Two costs
are computed instead, the cheaper wins, and **both are returned**:

```
rent      = day_rate x days + mobilisation
redeploy  = haulage (road km x rate + handling)
          + waiting (days blocked x blocked-day cost)
          + any extension past the existing contract expiry
```

Redeployment does **not** pay hire — that contract is already running and the
money is spent whether the machine works or sits. That asymmetry is the entire
economic case, and it is why the answer is usually "move it".

Shortfalls are filled one machine at a time, so an answer can be **mixed** —
move the two going spare nearby, rent the third — rather than forced one way.
Donors are consumed as assigned, so no machine is ever promised to two sites
(`test_no_machine_is_promised_to_two_sites`).

## The trained models on disk

Two models, two files:

```
models/phase_classifier.pkl    which phase is this site in?    1 XGBClassifier
models/phase_end.pkl           when does that phase end?       3 XGBRegressors
```

Four fitted estimators; the three quantile regressors are one *model* because a
single interval prediction needs all three plus the conformal pad.

```bash
python scripts/train_models.py                 # both, ~4 s
python scripts/train_models.py --only end      # retrain one, leave the other
python scripts/train_models.py --no-write      # score without writing
```

You never have to run it — `service.build()` trains whatever is missing at
startup. The files exist so the models can be inspected, handed over and
retrained independently, not to save four seconds.

**Each file records the fingerprint of the data it was trained on**, and a
mismatch is treated as no artifact at all: the model is refitted and the file
rewritten, loudly. That is the whole reason a checked-in `.pkl` is safe here.
Regenerate the dataset and forget to retrain, and nothing silently serves
predictions fitted to data that no longer exists.

`phase_end.pkl` must carry `interval_pad`. Without it the P10–P90 band is the
raw fitted quantiles, coverage drops from 0.80 to 0.40, and nothing looks
broken — so the loader rejects an artifact missing it rather than shrugging.

## Data contract

`data/forecast_cache/rental_history_*.csv` — one row per rental.

| Column | Source |
|---|---|
| `equipment_id` `type` `site_id` `operator_id` | Supplied schema |
| `check_in` `check_out` `rental_days` | Supplied schema — see the two clocks above |
| `engine_hours_per_day` `idle_hours_per_day` | Supplied schema. Disjoint, so `engine + idle` is engine-on time and validity is `engine + idle ≤ 24` |
| **`phase`** | **Added.** The phase the site was in when the machine was rented |
| **`fuel_l_per_day`** `lat` `lon` | **Added.** Required outcomes the schema omits |
| `rental_id` `is_ground_truth` `source` | Bookkeeping |

A small share of rows carry a blank `site_id` (and therefore a blank `phase`) or
a blank `operator_id` — ordinary bookkeeping failures, injected at
`RATE_UNASSIGNED_SITE` and `RATE_NO_OPERATOR`, which the anomaly detector's
`unassigned_equipment` and `no_accountability` rules exist to catch. They had
nothing to find before. Consumers must tolerate a null site: the modelling
panels drop those rows, because a site-less rental cannot belong to a site-week.

`data/site_phases.csv` — one row per (site, phase) window: `start_date`,
`end_date`, `is_complete`, `start_censored`, `duration_weeks`. This is the
ground truth the phase models train on and are scored against; without it the
prediction is unfalsifiable. `end_date` is **null** for the phase a site is
currently in, because that end has not happened yet.

Both files are the handoff to the anomaly detector. `phase` is what lets it
compare a machine against same-type-same-phase peers instead of a global
average — 20% utilisation is unremarkable during erection and alarming during
excavation, and only the phase tells you which.

## Running it

```bash
pip install pandas numpy scikit-learn xgboost fastapi pytest

python -m pytest backend/forecast/tests/test_phase.py -q     # phase + allocation (~3 min)
python -m pytest backend/forecast/tests/test_history.py -q   # the data gate (~2 s)
python -m pytest backend/forecast/tests/ -q                  # everything (~10 min)
```

```python
from backend.forecast import service

service.warm()                     # build once at startup (~60 s)
service.get_phase("S006")          # one site: phase, predicted end, next phase
service.get_phase_timeline()       # all sites + observed phase windows
service.get_phase_model()          # the evidence panel
service.get_allocation()           # the decision board
```

| Endpoint | Returns |
|---|---|
| `GET /api/phase/{site_id}` | current phase, predicted end + range, next phase |
| `GET /api/phase/timeline` | every site's state and the observed windows |
| `GET /api/phase/model` | accuracy, error, coverage, feature importances |
| `GET /api/allocation` | shortfalls, spare machines, priced recommendations |

Mount in `backend/main.py`:

```python
from backend.forecast.api import router as forecast_router
app.include_router(forecast_router)

@app.on_event("startup")
async def _warm_forecast():
    from backend.forecast import service
    service.warm()
```

## Pipeline

| Step | File | Does |
|---|---|---|
| 1 | `calibration.py` | Fits duration / usage distributions to `data/seed_assets.csv` |
| 2 | `history.py` | Draws per-site phase schedules, then ~7,200 rental events from them |
| 3 | `phase.py` | Site-week panel → classifier + quantile duration model + the lookup |
| 4 | `allocate.py` | Ledger of who frees when → shortfalls → priced recommendations |
| 5 | `service.py` | Builds and caches all of it; answers queries |
| 6 | `api.py` | The four endpoints above |

Sites are positioned by **which phase they are in at `now`**, not by a start
week — phase durations slip, so a start week cannot be written down in advance,
and the fleet must guarantee four sites in each of the six phases at `now` or
the product has nothing to show.

## Invariants

- **No `datetime.now()`.** `clock_adapter.py` is the only source of `now`.
  Enforced by an AST walk over the package in `test_phase.py` — every date in
  the source data is historical, so a real clock makes nothing active and the
  allocation board empties out.
- **Deterministic.** Same seed + same clock → identical schedules, models,
  scores and recommendations. RNGs are spawned per (site, type), so adding a
  site does not perturb another cell's draws.
- **Refuses rather than fabricates.** Demobilisation has no completed
  observations and returns `insufficient_data`.
- **Derived values are never persisted.** Phase state, freed-at dates and every
  cost are computed on read.
- **No row claims more hours than a day has.** `engine + idle > 24` is injected
  deliberately as a bad record for the detector to find, but capped — a row
  claiming 40 idle hours in a 24-hour day is not a finding, it is a generator
  bug, and it was one until `test_no_row_claims_more_hours_than_a_day_has`
  caught it.

## Known gaps

**`data/seed_assets.csv` is not committed.** Rental durations are meant to be
fitted to the supplied rows; without the file the generator runs on documented
fallbacks, `calibrated_to_seed_rows` is `false` in every response, and
`test_durations_match_the_seed_rows` **skips rather than passing** — a generator
reporting green while uncalibrated is exactly the failure mode that skip exists
to prevent. Drop the file in and regenerate; nothing else is blocked by it.

**Grading and demobilisation are the weak phases.** Late-life windows are the
rarest in the history, so the classifier is weakest there (see
`per_phase_accuracy`) and the duration model refuses demobilisation outright.
More history or more sites is the fix; both are cheap.

**The weekly-count forecaster (`model.py`, `backtest.py`) is out of scope.** It
predicts new rentals per (type × site) per week — a question this pipeline never
asks. It still runs and still passes its tests, but it gets no further work and
is not part of the story.

**Censored demand is not modelled.** Real rental history only records requests
that could be filled, so observed demand is biased down by your own stockouts.
The generator sizes the fleet to meet demand rather than modelling refusals.
