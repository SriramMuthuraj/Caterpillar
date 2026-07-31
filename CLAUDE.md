# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository State

**This repository is pre-implementation.** It currently contains only design documents:

- [docs/PRD.md](docs/PRD.md) — product requirements, `FR-1`…`FR-15`, the `INT-01`…`INT-08` rule spec, data model, frozen API contract, and the `MOD-01`…`MOD-17` module decomposition (§8.1)
- [docs/TEAM_SPLIT.md](docs/TEAM_SPLIT.md) — module ownership per member, hour-by-hour schedule, working rules

**These two documents are authoritative.** Read them before writing code. The PRD's §8.1 module map states each module's path, purpose, and interface signature — build to that, not to your own decomposition.

## Build Commands

The toolchain is not yet scaffolded, so there are no build, test, or lint commands to document. The planned stack is **FastAPI + pandas + scikit-learn** (backend) and **Next.js** (frontend). Once the hour-0/1 scaffolding lands, replace this section with the real commands — including how to run a single test, since the integrity rule suite is the highest-value test target in the project.

## Project Context

FleetTrust is a smart equipment-rental tracking system built for a 24-hour Caterpillar hackathon.

**The user is the renter, and only the renter** — the equipment/plant manager of a multi-site construction or mining contractor that rents machinery through Cat dealers. This was derived from the brief's wording ("help *companies*", "remind users when *return* time is approaching", "usage per *site*", "*unassigned* equipment") and settled by the dataset: **it has no customer column**, but it does have `Site ID` and `Last Operator ID` — both internal to a single organisation. A dealer's rental dataset without a customer field is impossible.

**There is no dealer console** (`MOD-16` was considered and dropped). The dealer exists only as a counterparty actor in the custody ledger (`DELIVERED_BY_DEALER`, `RETURNED_TO_DEALER`), so the handoff story appears in the asset timeline at zero UI cost. Do not reintroduce a dealer-side dashboard.

The competitive premise matters for design decisions: five of the seven outcomes Caterpillar asked for are **already shipped Cat products** (VisionLink, the Cat Rental Store portal, RentalMan, Cat App). The Cat Rental Store customer portal is *already renter-facing* — it is the direct incumbent for this exact persona, not adjacent competition. **Only outcomes 6 (forecasting) and 7 (anomaly detection) are genuinely unsolved, so that is where all engineering effort goes.** The other five are built to full quality and treated as table stakes.

**Product thesis:**

> FleetTrust knows what phase each project is in — and uses that to predict what equipment you will need next, and to judge whether a machine's behaviour is actually abnormal.

**The phase model (`MOD-06`) is the spine of both differentiators.** Construction demand is a *sequence*, not a season: clear → excavate → found → erect → grade → demobilise. The end of one phase is the leading indicator of demand for the next — a **causal** signal, which is why it holds up under questioning where seasonality does not. The same model makes anomaly detection **phase-relative**: 20% utilization is normal during structural erection and alarming during earthworks, so peers are same-type-same-phase, never a global average.

If a proposed change makes the product more like a conventional fleet dashboard, or scores anomalies against a global baseline instead of a phase-relative one, it is the wrong change.

## Architecture

Four layers. The presentation layer has **no hard dependencies** — it builds against `frontend/mocks/` so UI work never blocks on backend readiness.

```
Foundation (M1)     MOD-01 Data · MOD-02 Clock · MOD-03 Custody
                    MOD-04 Telemetry · MOD-05 QR · MOD-08 Alerts
Intelligence (M2)   MOD-07 KPI · MOD-09 Anomaly ⭐ · MOD-10 Economics
                    MOD-13 Recommendations
Predictive (M3)     MOD-06 Phase ⭐ · MOD-11 Forecast ⭐
                    MOD-12 Redeployment · MOD-14 Narration
Presentation (M4)   MOD-15 Contractor Console · MOD-17 Scan App
                    (MOD-16 dropped — renter-only, no dealer console)
```

**Critical path: `MOD-01 → MOD-06 → MOD-11 / MOD-09`.** The phase model feeds both differentiators; if it slips, FR-6 and FR-7 degrade to generic implementations and the submission loses its argument.

`MOD-09` (M2) depends on `MOD-06` (M3) — the only cross-member dependency on the critical path. It is neutralised by construction: **`MOD-01`'s generator writes the `phase` label onto every rental row**, so `MOD-09` and `MOD-11` read a column rather than calling `MOD-06`. Phase *inference* (for the 7 unlabelled seed rows) is a later refinement, never a blocker. Phase *definitions* live in `data/phases.yaml`, which `MOD-01` and `MOD-06` both read — config, not a code dependency.

## Invariants — violating these breaks the product's thesis

**The 7 seed rows in `data/seed_assets.csv` are ground truth and are never edited.** They are the supplied hackathon dataset, and they contain deliberate defects (see PRD §3) that the integrity engine must detect. Correcting the data destroys the entire demo. Synthetic history is generated *around* them and flagged `is_ground_truth=false`.

**Never call `datetime.now()` anywhere.** `MOD-02` (Virtual Clock) is the single source of `now`. Overdue alerting, telemetry, and the demo time-travel scrubber all depend on this. A stray real-clock call silently breaks `FR-5`, because every date in the source dataset is in the past and no rental is naturally active.

**Custody state is a pure fold over an append-only event log.** `MOD-03` stores `CustodyEvent` rows; asset status is *derived*, never stored or mutated in place. Replaying the log twice must yield identical state. Do not add a mutable `status` column to the asset table.

**Integrity rules emit `{rule_id, severity, evidence, remediation}` — never a bare boolean.** The explanation *is* the feature. A rule that returns `True` without evidence is unfinished.

**Column semantics are settled — do not re-litigate.** The Caterpillar mentor confirmed: `Engine Hours/Day` = **working hours**; `Idle Hours/Day` = engine on but **not** working. They are **disjoint**. Therefore `utilization = engine / (engine + idle)`, total engine-on hours (= SMU accrued) = `engine + idle`, and validity is just `engine + idle ≤ 24` with each value in `[0, 24]`. The `IDLE_SEMANTICS` dual-compute flag is **cancelled** — do not build it.

**Never claim the seed telemetry is "physically impossible" or "corrupt."** `idle > engine` is legal and means under-utilization. All 7 seed rows pass every range check (sums are 8–12 h). This is the one claim a Cat engineer could refute on the spot, so it must not appear in code comments, UI copy, the deck, or any submission text.

**There is no trust layer, audit layer, or confidence score.** Cancelled in PRD v3.0. All validity checking lives as tier-1 rules (`AN-01`…`AN-08`) inside `MOD-09` (Anomaly Engine). Do not reintroduce a standalone integrity module or a 0–100 asset score.

**`MOD-11` must be able to return `insufficient_data`.** Refusing to forecast where n is too small is a feature. Never fabricate a number to fill the response, and always emit prediction intervals alongside point estimates.

**Derived values are never persisted.** Asset status, confidence scores, and all KPIs are computed on read.

**`MOD-14` output must be pre-cached to disk.** The demo has to run with the network disabled, so no LLM call may sit on the critical path. Free-form SQL generation is out of scope — narration queries go through a fixed set of pandas-backed tools.

## Collaboration Constraints

This is a four-person parallel build with strict boundaries:

- **`backend/schemas.py` and `openapi.yaml` are locked shared files.** The API contract is frozen at hour 1; changes require agreement from all four members. Do not edit them unilaterally.
- **Exclusive file ownership per member** — see the ownership table in [docs/TEAM_SPLIT.md](docs/TEAM_SPLIT.md). Merge conflicts are prevented by construction, so stay inside the owning module's paths.
- **`main` must always run.** A push that breaks the demo is reverted, not debugged.
- **Feature freeze at hour 16.** After that, only polish, deck, rehearsal. No new dependencies after hour 14.
