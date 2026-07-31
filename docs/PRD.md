# FleetTrust — Product Requirements Document

**Product:** FleetTrust — Smart Asset Rental Tracking for the multi-site contractor
**Event:** Caterpillar Hackathon (24 hours, 4-member team, 180+ competing teams)
**Version:** 3.0
**Status:** Approved for build

**Changelog:** v2.0 — user changed from dealer to renter (§6). v3.0 — column semantics confirmed by mentor (§7 A7); differentiator moved from a standalone trust layer to **phase-aware demand forecasting + anomaly detection**; the integrity rules are now tier 1 *inside* anomaly detection, and `MOD-06` is repurposed as the **Phase Engine**.

---

## 1. Problem Statement

Caterpillar dealers rent machinery to construction and mining companies. Rental management — where the equipment is, who is using it, when it is due back, and what will be needed next — is still largely manual or spreadsheet-based. This produces three named failures:

1. Equipment lost or unaccounted for
2. Delays and downtime due to misallocation
3. Unexpected rental extensions and costs

## 2. Why the Obvious Solution Loses

Five of the seven mandated outcomes are **already shipped Caterpillar products**:

| Cat product | Already delivers |
|---|---|
| Product Link | On-machine telematics: GPS, hours, fuel, health (Cat + retrofit non-Cat) |
| VisionLink | Location, operating hours, fuel, health, maintenance, utilization across owned/leased/rented |
| Cat Rental Store portal | Past/current/upcoming rental dashboard, per-rental utilization + telematics + billing, configurable return alerts, self-service call-offs and transfers |
| RentalMan (Wynne) | Dealer-side rental ERP |
| Cat App | Mobile fleet management |
| Cat AI Assistant | Being integrated into the rental site |

A dashboard, a check-in form, a usage log and a return reminder are **table stakes**. An LLM chatbot bolted on top is the single most-converged idea available to 180 AI-assisted teams — and Caterpillar already ships one.

**This bites harder now that the renter is our user, not the dealer.** The Cat Rental Store customer portal is *already renter-facing* — it gives contractors past/current/upcoming rental dashboards, per-rental utilization and billing, and configurable return alerts. It is not adjacent competition; it is the direct incumbent for our exact persona. Rebuilding it is not a submission, it is a re-implementation.

What that portal does **not** do — and what nothing on the market does — is understand *what stage each project is at*, and use that to predict what the contractor will need next or to judge whether a machine's behaviour is actually abnormal.

**Only outcomes 6 (forecasting) and 7 (anomaly/misuse detection) are genuinely unsolved in Cat's stack. Those two are therefore where all of our engineering goes.** The other five are built to full quality and treated as table stakes.

## 3. The Insight: demand is phase-driven, and phase context is what everyone is missing

### Confirmed column semantics (answered by the Caterpillar mentor)

The dataset was ambiguous about `Engine Hours/Day` and `Idle Hours/Day`. **We asked rather than guessed.** The confirmed definition:

| Column | Meaning |
|---|---|
| `Engine Hours/Day` | **Working hours** — engine on *and* doing productive work |
| `Idle Hours/Day` | Engine on but **not** working |

They are therefore **disjoint**, and:

```
Total engine-on hours = Engine Hours + Idle Hours     (= SMU accrued)
Utilization %         = Engine Hours / (Engine Hours + Idle Hours)
Valid range check     = Engine + Idle ≤ 24,  and 0 ≤ each value ≤ 24
```

Consequences, stated plainly:

- **`idle > engine` is legal.** It means a badly under-utilized machine, not corrupt data.
- **All 7 seed rows pass the day-budget check.** Their sums are 8–12 h — a plausible shift. There are no physics violations in the seed data, and we must not claim any.
- **Idle hours still accrue SMU**, so idle pulls maintenance forward and burns fuel. Idle is expensive, just not invalid.

### What the 7 rows actually show

Every figure below was verified by hand. Utilization = engine ÷ (engine + idle).

| Asset | Engine (working) | Idle | Total on | **Utilization** | Finding |
|---|---|---|---|---|---|
| EQX1003 | 7.5 | 0.5 | 8.0 | **94%** | Healthy — but `Rental Days` states **25** while its dates give **24** → `AN-01` |
| EQX1005 | 8.0 | 0.0 | 8.0 | **100%** | Idle *exactly* 0.0 for 30 consecutive days → frozen sensor, `AN-05` |
| EQX1006 | 3.0 | 6.0 | 9.0 | **33%** | Below industry benchmark — under-utilized |
| EQX1004 | 2.0 | 9.0 | 11.0 | **18%** | Severely under-utilized |
| EQX1001 | 1.5 | 10.0 | 11.5 | **13%** | Severely under-utilized |
| EQX1002 | **0.0** | 11.0 | 11.0 | **0%** | **Ghost asset** — 220 engine-on hours across 20 billed days, **zero** work. `Site=NULL`, `Operator=NULL` → `AN-03`, `AN-04` |
| EQX1007 | **0.0** | 12.0 | 12.0 | **0%** | **Ghost asset** — 144 engine-on hours, zero work, no site, no operator. **Pain #1, literally in the data** → `AN-03`, `AN-04` |

**Five of seven machines fall below the industry idle benchmark** (construction fleets typically run 25–40% idle, i.e. 60–75% utilization). Two did no work at all.

This is a *stronger* position than a data-quality complaint. The data is valid, and it says: you are paying rent, burning diesel, and consuming service-meter life on machines that are not working. That is exactly what the brief asks us to surface — "flag under-utilized assets", "long idle hours".

**The headline finding, now unambiguous:**

> EQX1002 was billed for 20 rental days. Its engine ran 11 hours a day — **220 engine-on hours** — and delivered **zero** hours of work. You paid the rental, burned the diesel, and took 220 hours off the maintenance clock, for nothing. Nobody was recorded as accountable, and no site was recorded at all.

Three further structural gaps in the brief itself:

- **Fuel usage and location are required outputs but absent from the schema.** Only a nullable `Site ID` exists.
- **Every date falls in 2025.** There are zero active rentals, so outcome #5 (overdue / approaching-return alerts) is unsatisfiable against raw data.
- **Seven rows cannot train a model.** Any claim of a trained forecaster on this data collapses under expert questioning.

### Product thesis

> **FleetTrust knows what phase each of your projects is in — and uses that to predict what equipment you will need next, and to judge whether a machine's behaviour is actually abnormal.**

Every other tool treats a machine as an isolated row of hours. That forces two mistakes:

- **Demand gets modelled as seasonality.** It isn't. Construction demand is a *sequence*: a site clears → excavates → founds → erects → grades → demobilises. Each phase consumes a different machine class, and **the end of one phase is the leading indicator of demand for the next.** When bulldozer hours at a site start tapering, that site needs excavators in about two weeks — because clearing is finishing, not because of the month. That is a **causal** signal, which is why it survives cross-examination where a seasonality curve does not.
- **Anomalies get scored against a global average.** Also wrong. 20% utilization on an excavator is entirely normal during structural erection and alarming during earthworks. Global scoring floods the user with false alarms; **peer-relative scoring within the same type and same phase** does not.

**One model powers both differentiators.** That is stronger architecture than two bolted-on ML features, and it explains in fifteen seconds.

The economics land on top of it, and are now exact because engine hours mean *working* hours: every idle hour costs three ways at once — rental paid for no output, diesel burned while stationary, and a service-meter hour consumed that pulls the next maintenance interval forward.

## 4. Goals

| ID | Goal |
|---|---|
| G1 | Deliver all seven mandated outcomes to demonstrable quality |
| G2 | Model **project phase** explicitly, and use it to drive both forecasting and anomaly detection |
| G3 | Make accountability a first-class object — every asset always has a named custodian |
| G4 | Convert every finding into a **priced, approvable action** |
| G5 | Produce forecasts that are honest about their own uncertainty |
| G6 | Survive a live demo with no network and no cold-start |

## 5. Non-Goals

- Real telematics hardware integration (the brief permits simulation)
- Authentication, multi-tenancy, RBAC, production security
- Real payment or invoicing
- Mobile native apps (responsive web only)
- Non-Cat equipment onboarding flows

## 6. User — the renter, and only the renter

**Primary and sole user: the equipment / plant manager of a multi-site construction or mining contractor that rents machinery through Cat dealers.**

They care about: which machines they currently hold, at which of their sites, doing productive work or not; what each idle hour is costing them; whether a machine should be returned, extended or moved to another of their own sites; and whether the hours they are being **billed for** can be trusted.

### Why the renter — the evidence

This was re-derived from the brief and the dataset, not from Caterpillar's commercial interest.

| Evidence | Reading |
|---|---|
| "companies often rent machinery... **through our registered dealers**" | Cat narrates; dealers are the *channel*; "companies" are the renters. This sentence defines "companies" for the whole brief |
| "Design a system that can help **companies**" | Same "companies" — the renters |
| "Remind **users** when **return time** is approaching" | The party that *returns* equipment is the renter |
| "pre-position equipment... needed at certain **sites**/times" | "Sites" are construction sites. Dealers pre-position across branches and yards, not sites |
| "usage **per site**" | A contractor's view of its own projects |
| "misuse... **unassigned equipment**" | The renter assigns operators to machines; the dealer does not |
| "unexpected rental extension **and costs**" | Extensions are a *cost* to the renter and *revenue* to the dealer |

**Decisive: the dataset has no customer column.** No customer ID, no contract number, no rate, no branch, no delivery address. A dealer's rental dataset without a customer field is impossible — you cannot bill or chase a return without it. A *renter's* internal equipment sheet with no customer column is entirely natural, because there is only one customer: themselves. What it tracks instead is `Site ID` and `Last Operator ID`, both internal to a single organisation.

### The dealer is a counterparty, not a user

**There is no dealer console.** Building one was considered and deliberately dropped — one excellent console beats two half-built ones.

The dealer survives as an **actor in the custody ledger** (`DELIVERED_BY_DEALER`, `RETURNED_TO_DEALER`). The handoff — the exact moment accountability transfers, and where "equipment unaccounted for" originates — therefore still appears as events in the asset timeline, at zero UI cost.

### Naming the ambiguity is itself a scoring moment

The brief's ambiguity is most likely accidental rather than a trap, which means judges will accept either persona **provided the choice is justified out loud**. The risk is not choosing wrong; it is choosing silently. Say this on stage:

> *"The brief says 'help companies.' That could mean the dealer or the renter. The dataset settles it — there is no customer column, but there is a site column and an operator column. So we built for the contractor."*

## 7. Assumptions & Constraints

| # | Assumption |
|---|---|
| A1 | Telemetry may be simulated — the brief states "you can assume the data is real time" |
| A2 | Synthetic history may be generated. **The 7 supplied rows are preserved verbatim as ground truth** and visibly flagged as such |
| A3 | Dates are rebased onto a virtual clock so that active, approaching-due, overdue and unaccounted states all exist |
| A4 | Fuel and geo-coordinates are simulated and **labelled as simulated** in the UI |
| A5 | Currency is ₹, configurable; all rates live in `data/rates.yaml` with a visible Assumptions page |
| A6 | Venue network may fail — the critical demo path must run fully offline |

### A7 — The idle-hours ambiguity: RESOLVED by the Caterpillar mentor

The dataset did not define whether `Idle Hours/Day` sits **inside** `Engine Hours/Day` or **beside** it. The two readings invert the meaning of utilization, so we raised it rather than guessing.

**Confirmed answer:** `Engine Hours/Day` = **working hours**. `Idle Hours/Day` = engine on but **not** working. They are **disjoint**. See §3 for the derived formulas.

**Consequences — these are binding:**

- The `IDLE_SEMANTICS` dual-compute flag is **cancelled**. Do not build it. Compute one way.
- **`idle > engine` is legal** and means under-utilization, not corrupt data.
- **No seed row violates any range check.** Never claim the supplied telemetry is "physically impossible" or "corrupt" — it is valid, and it is reporting something expensive. This is the one claim a Cat engineer could refute, so it must not appear anywhere in the product, the deck, or the submission.
- Validity checking reduces to `engine + idle ≤ 24` and `0 ≤ each value ≤ 24`, which now live as tier-1 rules inside `MOD-09` (Anomaly), not in a separate layer.

The *process* remains a credibility point worth stating on stage: we found the ambiguity, we asked, and we built to the confirmed definition.

## 8. Functional Requirements

Priority: **P0** must be complete by hour 16. **P1** hours 16–20. **P2** only if all P0/P1 are green.

| ID | Requirement | Maps to | Pri | Owner |
|---|---|---|---|---|
| **FR-1** | **Asset Dashboard** — every machine currently held, derived live status, grouped by site, filter/sort, drill-through to detail | Outcome 1 | P0 | M4 |
| **FR-2** | **Check-in / Check-out** — real QR code per asset, phone-camera scan triggers custody transfer; manual entry fallback | Outcome 2 | P0 | M1+M4 |
| **FR-3** | **Usage Logging** — runtime hours, idle hours, fuel (simulated, labelled), location/site, streamed live over SSE | Outcome 3 | P0 | M1 |
| **FR-4** | **Summaries** — total rented hours, usage per site, downtime, utilization %, cost per working hour | Outcome 4 | P0 | M2+M4 |
| **FR-5** | **Overdue Alerts** — approaching-due, due-today, overdue; escalating severity; driven by the virtual clock | Outcome 5 | P0 | M1 |
| **FR-6** | **Demand Forecasting** ⭐ — weekly demand per (equipment_type × site) via **XGBoost** on phase-derived features. **Quantile objectives → P10/P50/P90 prediction intervals**, an explicit `insufficient_data` verdict, a **backtest MAPE displayed in the UI**, and inspectable feature importances so the product can show *why* | Outcome 6 | P0 | M3 |
| **FR-7** | **Anomaly Detection** ⭐ — **phase-aware**: peers are same-type-same-phase, not a global average. Tier 1 deterministic rules (§9) + Tier 2 IsolationForest on engineered features; every anomaly ships its evidence and remediation | Outcome 7 | P0 | M2 |
| **FR-8** | **Project Phase Model** ⭐ — archetype → ordered phase sequence → sampled durations → per-phase equipment requirement profile. Powers **both** FR-6 and FR-7. *Repurposed from the cancelled trust-layer slot; this is the actual differentiator and needed a named owner* | Differentiator | P0 | M3 |
| **FR-9** | **Custody Ledger** — append-only event log; asset state derived by folding the log, never mutated in place; `UNACCOUNTED` is a real state with escalation SLA and recovery playbook | Pain #1 | P0 | M1 |
| **FR-10** | **Virtual Clock** — single source of `now` for the whole system, plus a UI time-travel scrubber | Enables FR-5 | P0 | M1+M4 |
| **FR-11** | **Economics** — idle burn ₹/day, projected overrun exposure, redeployment savings, visible Assumptions page | Pain #3 | P1 | M2 |
| **FR-12** | **Recommendation Cards** — each finding becomes a priced action with Approve/Dismiss writing back to the ledger | G4 | P1 | M2+M4 |
| **FR-13** | **Return-or-Extend Decision** — for each active rental, the projected cost of holding vs. returning vs. extending at the current run-rate, with a recommended action. *Repurposed from the dropped renter-view slot; this is the brief's third stated pain ("unexpected rental extension and costs") finally having a named owner. Mostly a UI composition of `MOD-08` + `MOD-10` output — cut it first if H16 is tight* | Pain #3 | P1 | M2+M4 |
| **FR-14** | **Narration** — LLM morning briefing + NL query over a **fixed set of pandas-backed tools** (no free-form SQL); deterministic template fallback pre-cached at build time | Polish | P2 | M3 |
| **FR-15** | **Redeployment Matching** — idle asset at site A ↔ forecast demand at site B, with transport cost netted out | Gap G5 | P2 | M3 |

## 8.1 Module Decomposition

Every requirement above is allocated to exactly one **owning module**. A module is a unit with one clear purpose, a defined interface, and the ability to be built and tested independently. Where an FR spans backend logic and UI, the compute module owns the requirement and the UI module *renders* it — the split is stated explicitly.

### Module map

| ID | Module | Layer | Implements | Owner | Depends on |
|---|---|---|---|---|---|
| `MOD-01` | Data Foundation | Foundation | A2, A4 | M1 | — |
| `MOD-02` | Virtual Clock | Foundation | FR-10 (service) | M1 | — |
| `MOD-03` | Custody Ledger | Foundation | FR-9, FR-2 (API) | M1 | 01, 02 |
| `MOD-04` | Telemetry Stream | Foundation | FR-3 | M1 | 01, 02 |
| `MOD-05` | QR Identity | Foundation | FR-2 (codes) | M1 | 03 |
| `MOD-06` | **Phase Engine** ⭐ | Predictive | **FR-8** | M3 | 01 |
| `MOD-07` | KPI & Summary Engine | Intelligence | FR-4 (compute) | M2 | 04 |
| `MOD-08` | Alert Engine | Intelligence | FR-5 | M1 | 02, 03 |
| `MOD-09` | Anomaly Engine ⭐ | Intelligence | FR-7 | M2 | 01, 04, 06 |
| `MOD-10` | Economics Engine | Intelligence | FR-11 | M2 | 04, 07 |
| `MOD-11` | Forecast Engine ⭐ | Predictive | FR-6 | M3 | 01, 06 |
| `MOD-12` | Redeployment Optimizer | Predictive | FR-15 | M3 | 07, 10, 11 |
| `MOD-13` | Recommendation Engine | Intelligence | FR-12 (logic) | M2 | 06, 08, 09, 10 |
| `MOD-14` | Narration | Predictive | FR-14 | M3 | 06, 07, 09, 11 |
| `MOD-15` | Contractor Console | Presentation | FR-1, FR-4/5/8/12/13 (render), FR-10 (scrubber) | M4 | all APIs |
| ~~`MOD-16`~~ | ~~Renter View~~ — **dropped**, see §6 | — | — | — | — |
| `MOD-17` | Scan App | Presentation | FR-2 (UI) | M4 | 03, 05 |

### Dependency order — what must exist before what

```
MOD-01 Data ──┬─> MOD-06 Phase ⭐ ──┬─> MOD-11 Forecast ⭐ ──> MOD-12 Redeploy
   (labels     │                    └─> MOD-09 Anomaly ⭐ ──┐
    phase)     ├─> MOD-04 Telemetry ──> MOD-07 KPI ──> MOD-10 Economics
MOD-02 Clock ──┼─> MOD-03 Custody ──┬─> MOD-05 QR          │        │
               │                    └─> MOD-08 Alerts ─────┴────────┴─> MOD-13 Recommend
               └────────────────────────────────────────────────────> MOD-14 Narration

  ALL ──> MOD-15 / MOD-17 Presentation  (built against mocks from hour 1, never blocked)
```

**Critical path:** `MOD-01 → MOD-06 → MOD-11 / MOD-09`. Complete by hour 6. The phase model is the spine of both differentiators, so if it slips, both FR-6 and FR-7 degrade to generic implementations and the submission loses its argument.

### ⚠️ The one cross-member dependency — and how it is neutralised

`MOD-09` (Anomaly, **M2**) depends on `MOD-06` (Phase, **M3**). That is the only place one member blocks another on the critical path, so it is removed by construction:

**`MOD-01`'s generator writes the `phase` label onto every rental row it creates.** Phase is *known* for synthetic data because the generator produced it. `MOD-09` and `MOD-11` therefore just **read a column** — they never call `MOD-06` to get started.

Phase *inference* (deriving phase from an unlabelled site's equipment mix and hour trends) is only needed for the 7 real seed rows and for realism. It is a **refinement delivered later by M3**, not a blocker. M2 is never stalled.

### Foundation layer — M1

| Module | Path | Purpose | Key interface |
|---|---|---|---|
| `MOD-01` **Data Foundation** | `backend/ingest/` `data/` | Load the 7 seed rows verbatim; generate seeded synthetic history from those rows' own distributions; rebase dates onto the virtual clock; simulate fuel and geo and tag them `source=sim` | `load_fleet() -> DataFrame`, `generate(seed) -> DataFrame` |
| `MOD-02` **Virtual Clock** | `backend/clock/` | Single source of `now` for the entire system. Nothing anywhere calls `datetime.now()` directly | `GET /api/clock`, `POST /api/clock/scrub` |
| `MOD-03` **Custody Ledger** | `backend/custody/` | Append-only event log. Asset state is a **pure fold** over events — never mutated in place. Owns the `UNACCOUNTED` state, its escalation SLA and the recovery playbook | `POST /api/custody/event`, `GET /api/assets/{id}/timeline`, `fold_state(events) -> AssetState` |
| `MOD-04` **Telemetry Stream** | `backend/telemetry/` | Emits ticks (engine hrs, idle hrs, fuel, lat/lon) over SSE, driven by `MOD-02` | `GET /api/stream/telemetry` |
| `MOD-05` **QR Identity** | `backend/qr/` | One QR per asset resolving to the scan route; a scan posts a custody event to `MOD-03` | `GET /api/assets/{id}/qr` |
| `MOD-08` **Alert Engine** | `backend/alerts/` | Derives approaching-due / due-today / overdue from the clock and the ledger, with escalating severity | `GET /api/alerts/overdue` |

### Intelligence layer — M2

| Module | Path | Purpose | Key interface |
|---|---|---|---|
| `MOD-07` **KPI & Summary Engine** | `backend/kpi/` | Brief-mandated: total rented hours, **usage per site**, downtime. Plus **working hours**, **utilization %** = engine ÷ (engine + idle), **cost per working hour ₹**, **idle spend ₹**, per-site allocation balance | `GET /api/summary` |
| `MOD-09` **Anomaly Engine** ⭐ | `backend/anomaly/` | **Differentiator.** **Tier 1** — deterministic rules (§9), which absorb all validity checking; there is no separate integrity layer. **Tier 2** — IsolationForest, unsupervised because no labelled misuse data exists, over utilization ratio, idle ratio, daily-hours variance, fuel per working hour, operator churn, and **deviation from the phase-and-type peer baseline**. Peer comparison is **phase-relative**, never global. Every anomaly emits `{rule_id or feature_attribution, severity, evidence, remediation}` — never a bare boolean | `GET /api/anomalies` |
| `MOD-10` **Economics Engine** | `backend/economics/` | Applies `rates.yaml` to produce **idle burn ₹/day** (money paid for hours the machine didn't work), **overrun exposure** (projected extension cost at current run-rate), **early-return saving**, and **redeployment saving** net of transport. Prices idle **three ways** — rental paid for no output, diesel burned while stationary, and SMU consumed that pulls maintenance forward. Owns the visible Assumptions page | `GET /api/economics/{id}` |
| `MOD-13` **Recommendation Engine** | `backend/recommend/` | Converts findings from `MOD-08/09/10` into priced, approvable action cards. Renter action verbs: **return early (call off)** · **extend now vs. let it run** · **move to site X** · **assign / reassign operator** · **dispute this billing line**. Approval writes back to `MOD-03` | `GET /api/recommendations`, `POST /api/recommendations/{id}/approve` |

### Predictive layer — M3

| Module | Path | Purpose | Key interface |
|---|---|---|---|
| `MOD-06` **Phase Engine** ⭐ | `backend/phase/` `data/phases.yaml` | **The spine of both differentiators.** Owns the phase definitions — project archetype (highway / commercial build / mining pit) → ordered phase sequence → sampled duration distribution → per-phase equipment requirement profile (type, count, expected utilization). Definitions live in `phases.yaml` so `MOD-01` reads the *same config* to generate history with **no code dependency**. Also provides phase **inference** for unlabelled rows (the 7 seed rows and real data) from equipment mix and hour trends — a later refinement, not a blocker | `get_phase(site_id, date) -> PhaseState`, `phase_completion_pct()`, `successor_phase()` |
| `MOD-11` **Forecast Engine** ⭐ | `backend/forecast/` | **Differentiator.** Weekly demand per (equipment_type × site) via **XGBoost**. Features: inferred phase, phase completion %, engine-hour trend of the *outgoing* equipment class, typical successor phase, demand lags at 1/2/4 weeks, concurrent equipment mix on site, project archetype, equipment type, monsoon and calendar effects. **Quantile objectives produce P10/P50/P90**, so intervals are earned rather than asserted. Feature importances are exposed so the UI can show *why*. **Must return `insufficient_data` where n is too small rather than fabricate.** Includes the backtest harness whose holdout MAPE is surfaced in the UI | `GET /api/forecast?type=&site=` |
| `MOD-12` **Redeployment Optimizer** | `backend/forecast/redeploy.py` | Matches an idle machine at one of the contractor's sites against forecast demand at another, netting out transport cost from `rates.yaml`. **Renter-primary makes this fully viable** — moving between your *own* sites needs no cross-dealer data, so the module is now supported end-to-end by the supplied schema | `GET /api/recommendations` (contributes cards) |
| `MOD-14` **Narration** | `backend/narrate/` | Morning briefing + NL query over a **fixed set of pandas-backed tools** (no free-form SQL). Output pre-cached to disk so the demo never touches the network | `GET /api/narrate/briefing -> {text, source: llm\|cached}` |

### Presentation layer — M4

| Module | Path | Purpose |
|---|---|---|
| `MOD-15` **Contractor Console** | `frontend/app/console/` | The product. Assets held, grouped by site, with **utilization and phase context** on every row · asset detail with custody timeline (including dealer handoff events) and original-vs-rebased dates · alerts · **anomalies with evidence and phase-relative peer comparison** · **forecast charts with P10/P50/P90 bands, backtest MAPE and feature importances** · a **site phase timeline** showing where each project sits and what it will need next · return-or-extend cards · recommendation cards · the **time-travel scrubber** and its **Reset** button |
| ~~`MOD-16`~~ | — | **Dropped.** One excellent console beats two half-built ones. The dealer survives as a counterparty actor in the `MOD-03` ledger, so the handoff story costs no UI |
| `MOD-17` **Scan App** | `frontend/app/scan/` | Mobile-first camera QR scanner posting custody events — a site supervisor taking or handing over custody. Must work on a phone browser over LAN |

Both build against `frontend/mocks/` from hour 1 and switch to live endpoints as they land.

### Module Definition of Done

A module is done when it: works against real generated data rather than a stub; handles the null/missing/impossible cases this dataset is full of; exposes exactly the interface in the frozen contract; is visible in the UI **or** covered by tests; and is merged with `main` still running.

## 9. Anomaly Detection — Tier 1 Rule Specification (FR-7)

These rules live **inside `MOD-09`**. There is no separate integrity, audit or trust-scoring layer — that was cancelled in v3.0. Every rule emits `{rule_id, severity, evidence, remediation}` — never a bare boolean. Rules are named and versioned.

| ID | Rule | Severity | Fires on |
|---|---|---|---|
| `AN-01` | Billing mismatch: `abs((check_out − check_in).days − rental_days_stated) > 0` | High | EQX1003 (states 25, dates give 24) |
| `AN-02` | Day budget exceeded: `engine + idle > 24` | Critical | synthetic only — **no seed row violates this** |
| `AN-03` | Zero-work asset: working hours ≈ 0 across an entire billed rental | Critical | EQX1002 (220 engine-on h), EQX1007 (144 engine-on h) |
| `AN-04` | Orphan custody: `site_id` or `operator_id` null while accruing engine-on hours | Critical | EQX1002, EQX1007 |
| `AN-05` | Frozen sensor: identical value repeated ≥ 14 consecutive days | Medium | EQX1005 (idle exactly 0.0 × 30 d) |
| `AN-06` | Value out of range: any hour value negative or > 24 | High | synthetic only |
| `AN-07` | Stale telemetry beyond SLA | Medium | live stream |
| `AN-08` | **Phase-relative under-utilization** — utilization below the same-type-same-phase peer baseline by a configured margin | High | EQX1001 (13%), EQX1004 (18%), EQX1006 (33%) |

`AN-08` is the rule that requires `MOD-06`, and it is the one no competing team will have. The others are phase-independent and can ship before the phase model lands.

### Tier 2 — IsolationForest

Unsupervised, because no labelled misuse data exists. Features: utilization ratio, idle ratio, variance in daily hours, fuel per working hour, operator churn within a rental, and **deviation from the phase-and-type peer baseline**. Catches what rules cannot express; always reported alongside a feature attribution so the finding stays explainable.

### Validation — the answer key

`MOD-01`'s generator injects known anomalies and writes `defect_labels.csv`. **No detector ever reads that file.** It exists solely so precision and recall can be *measured* rather than claimed. Guard this boundary in review.

## 10. Data Model

```
Asset            equipment_id, type, model, acquired_on, is_ground_truth
Rental           rental_id, equipment_id, site_id, check_in, check_out,
                 rental_days_stated, rental_days_computed, day_rate,
                 phase            -- written by the generator; read by MOD-09/11
Site             site_id, name, lat, lon, region, project_archetype
PhaseDef         archetype, phase_name, order_index, duration_dist,
                 equipment_profile[{type, count, expected_utilization}]
                 -- from data/phases.yaml; read by BOTH MOD-01 and MOD-06
PhaseState       site_id, phase_name, started_on, completion_pct,
                 successor_phase          -- derived, never persisted
CustodyEvent     event_id, equipment_id, ts, type, actor, site_id,
                 operator_id, method(qr|manual|rfid_sim), geo, note
                 -- APPEND ONLY
TelemetryTick    equipment_id, ts, engine_hours, idle_hours, fuel_l,
                 lat, lon, source(sim|seed)
Finding          finding_id, equipment_id, rule_id, severity, evidence,
                 remediation, detected_at
Site             site_id, name, lat, lon, region
```

**Derived, never stored:** asset status, phase state, utilization, all KPIs.
`CustodyEvent` is the system of record. Asset state is a fold over it.

## 11. API Contract — frozen at hour 1

Interface changes after hour 1 require agreement from all four members.

```
GET  /api/clock                          -> {now, mode}
POST /api/clock/scrub                    {to}
GET  /api/assets                         -> [AssetView]
GET  /api/assets/{id}                    -> AssetDetail
GET  /api/assets/{id}/timeline           -> [CustodyEvent]
GET  /api/assets/{id}/qr                 -> image/png
POST /api/custody/event                  {equipment_id, type, site_id,
                                          operator_id, method, geo}
GET  /api/stream/telemetry               -> text/event-stream
GET  /api/phase/{site_id}                -> {phase, completion_pct, successor}
GET  /api/phase/timeline                 -> per-site phase timeline
GET  /api/anomalies                      -> [Anomaly]
GET  /api/alerts/overdue                 -> [Alert]
GET  /api/summary?trust=all|verified     -> KPIs  (trust filter drives FR-8 demo)
GET  /api/economics/{id}                 -> {idle_burn, overrun_exposure}
GET  /api/forecast?type=&site=           -> {points[], lower[], upper[],
                                             verdict, mape}
GET  /api/recommendations                -> [ActionCard]
POST /api/recommendations/{id}/approve
GET  /api/narrate/briefing               -> {text, source: llm|cached}
```

**`AssetView`** — `equipment_id, type, status, site_id, operator_id, custodian, days_remaining, engine_hours, idle_hours, utilization_pct, confidence, band, open_findings, is_ground_truth`

## 12. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | Critical demo path runs with the network disabled |
| NFR-2 | No cold start — the app opens on a pre-seeded, interesting state |
| NFR-3 | Deterministic — same seed produces the same fleet, scores and findings |
| NFR-4 | `main` must always run. A push that breaks the demo is reverted, not debugged |
| NFR-5 | Dashboard first paint under 2 s on a laptop |
| NFR-6 | Responsive — `/scan` must work on a phone browser |

## 13. Out of Scope

Authentication · real payments · native mobile apps · real RFID hardware · production deployment · non-Cat asset onboarding · historical data migration.

## 14. Credibility Commitments

These are scoring decisions, not modesty.

1. **An explicit "What's Real vs. Simulated" slide** in the deck. Volunteering limitations builds more credibility with engineer judges than any additional feature.
2. **The forecast backtest harness is presented as the deliverable, not the accuracy number.** The model is validated on synthetic history and we say so.
3. **`insufficient_data` is a legitimate API response.** Where n is too small, the system refuses rather than fabricates.
4. **Domain vocabulary throughout:** call-off (ending a rental early), SMU (Service Meter Units), utilization %, ghost asset, redeployment, plant manager, site custodian.

## 15. Open Question for Organizers

The `Engine Hours/Day` vs `Idle Hours/Day` semantics (see A7). Worth asking directly. The build handles both readings either way, so this is not a blocker.
