# FleetTrust — Work Split & Execution Tracker

**4 members · 24 hours · reference:** [PRD.md](PRD.md)

The split is designed so **no member ever waits on another**. Three mechanisms make that true:

1. **The API contract is frozen at hour 1.** Everyone codes against it, not against each other's code.
2. **Exclusive file ownership.** No two members edit the same file. This eliminates merge conflicts by construction.
3. **The frontend runs on a mock API from hour 1**, so UI work never blocks on backend readiness.

---

## Roles

| | Member | Role | Owns |
|---|---|---|---|
| **M1** | | **Data & Platform** | Repo, data generation, virtual clock, custody ledger, telemetry stream, QR generation, overdue engine |
| **M2** | | **Intelligence** | Integrity rules, confidence score, anomaly detection, KPI computation, economics, recommendations |
| **M3** | | **ML & Insight** | Demand forecasting, backtest harness, narration layer, redeployment matching, deck data slides |
| **M4** | | **Frontend & Demo** | Contractor console, mobile scan page, trust toggle, time scrubber, demo script |

Write your names in the blank column before hour 0.

## Requirement Ownership

| FR | Requirement | Pri | Owner | Support |
|---|---|---|---|---|
| FR-1 | Asset Dashboard | P0 | **M4** | — |
| FR-2 | Check-in/out + QR scan | P0 | **M1** (codes, API) | M4 (scan UI) |
| FR-3 | Usage Logging + SSE stream | P0 | **M1** | — |
| FR-4 | Summaries with trust bands | P0 | **M2** (compute) | M4 (render) |
| FR-5 | Overdue Alerts | P0 | **M1** (clock-driven) | M4 (render) |
| FR-6 | Demand Forecasting | P0 | **M3** | — |
| FR-7 | Anomaly Detection | P0 | **M2** | — |
| FR-8 | Confidence Score / Trust Layer | P0 | **M2** | M4 (badges, toggle) |
| FR-9 | Custody Ledger | P0 | **M1** | — |
| FR-10 | Virtual Clock | P0 | **M1** (service) | M4 (scrubber) |
| FR-11 | Economics | P1 | **M2** | — |
| FR-12 | Recommendation Cards | P1 | **M2** (logic) | M4 (cards) |
| FR-13 | Return-or-Extend Decision | P1 | **M2** (logic) | M4 (cards) |
| FR-14 | Narration + NL query | P2 | **M3** | — |
| FR-15 | Redeployment Matching | P2 | **M3** | — |

## Module Ownership — see [PRD §8.1](PRD.md) for each module's interface

Every requirement is allocated to exactly one owning module. **Nobody edits a file outside their column** — this eliminates merge conflicts by construction.

| | M1 — Foundation | M2 — Intelligence | M3 — Predictive | M4 — Presentation |
|---|---|---|---|---|
| **Modules** | `MOD-01` Data Foundation<br>`MOD-02` Virtual Clock<br>`MOD-03` Custody Ledger<br>`MOD-04` Telemetry Stream<br>`MOD-05` QR Identity<br>`MOD-08` Alert Engine | `MOD-06` Trust Engine ⭐<br>`MOD-07` KPI & Summary<br>`MOD-09` Anomaly Engine<br>`MOD-10` Economics<br>`MOD-13` Recommendations | `MOD-11` Forecast Engine<br>`MOD-12` Redeployment<br>`MOD-14` Narration | `MOD-15` Contractor Console<br>`MOD-17` Scan App<br><br>~~`MOD-16`~~ dropped |
| **Paths** | `data/`<br>`backend/ingest/`<br>`backend/clock/`<br>`backend/custody/`<br>`backend/telemetry/`<br>`backend/alerts/`<br>`backend/qr/`<br>`backend/main.py`, Docker, CI | `backend/integrity/`<br>`backend/kpi/`<br>`backend/anomaly/`<br>`backend/economics/`<br>`backend/recommend/`<br>`data/rates.yaml` | `backend/forecast/`<br>`backend/narrate/`<br>`notebooks/`<br>`data/forecast_cache/` | `frontend/` (all)<br>`frontend/mocks/` |

⭐ `MOD-06` is the product differentiator. If M2 falls behind, the team reallocates to M2 — not the reverse.

**Critical path: `MOD-01 → MOD-04 → MOD-06 → MOD-07` must be complete by hour 6.** The trust engine is the differentiator and the KPI engine feeds every screen. Everything else may slip; this chain may not.

**Shared and therefore locked:** `backend/schemas.py` (the contract) and `openapi.yaml`. Changes require all four members to agree in the standup. Nobody edits these alone.

---

## Hour-by-Hour Schedule

Rest is staggered in pairs during the calm stretch after Milestone 1. **Take it — a tired team ships a broken demo.**

| Hours | M1 | M2 | M3 | M4 |
|---|---|---|---|---|
| **0–1** | 🔴 **ALL FOUR TOGETHER:** scope freeze · write `openapi.yaml` and `schemas.py` · repo skeleton · commit the 7 seed rows verbatim · `rates.yaml` | | | |
| 1–3 | **`MOD-01`** generator + date rebasing<br>**`MOD-02`** virtual clock | **`MOD-06`** `INT-01`…`INT-05` rules + unit tests | **`MOD-11`** feature table from history | **`MOD-15`** Next.js shell + routing + mock API layer |
| 3–6 | **`MOD-03`** custody ledger (append-only + fold)<br>**`MOD-04`** SSE telemetry | **`MOD-06`** confidence score + bands + `IDLE_SEMANTICS` dual-compute<br>**`MOD-07`** KPI engine + `trust=` filter | **`MOD-11`** forecast v1 per (type × site) | **`MOD-15`** console on live `/api/assets` |
| **6–8** | 🔴 **ALL FOUR:** integration. **MILESTONE 1 — all 7 outcomes working end-to-end. `git tag m1`** | | | |
| 8–11 | 😴 **REST** | **`MOD-09`** anomaly Tier 1 rules + Tier 2 IsolationForest | 😴 **REST** | **`MOD-17`** scan app + camera QR<br>**`MOD-15`** alerts UI |
| 11–14 | **`MOD-05`** QR generation<br>**`MOD-08`** alert engine | 😴 **REST** | **`MOD-11`** backtest harness + prediction intervals + `insufficient_data` | 😴 **REST** |
| **14–16** | 🔴 **ALL FOUR:** integration. **MILESTONE 2 — FEATURE FREEZE. Nothing new after this line.** | | | |
| 16–18 | **`MOD-01`** seed demo state (active / due-soon / overdue / unaccounted) | **`MOD-10`** economics<br>**`MOD-13`** recommendation logic + return-or-extend (FR-13) | **`MOD-14`** narration + **pre-cache LLM output to disk** | **`MOD-15`** trust toggle + time scrubber + Reset button |
| 18–20 | README + architecture diagram | **`MOD-06`** `INT-06`…`INT-08`<br>**`MOD-10`** assumptions page | **`MOD-12`** redeployment (only if green) | **`MOD-15`** recommendation cards + visual polish |
| 20–22 | Deck: problem, architecture, gaps | Deck: trust layer, **"Real vs. Simulated"** slide | Deck: forecast credibility, backtest MAPE | Deck screenshots + **own the demo script** |
| **22–23** | 🔴 **ALL FOUR:** three full dry runs. **One with the wifi physically off.** Fix breakages only. | | | |
| **23–24** | 🔴 **ALL FOUR:** buffer. Submit repo. **Do not write code.** | | | |

**Approximate hands-on hours: M1 ≈ 15 · M2 ≈ 15 · M3 ≈ 15 · M4 ≈ 15.** Balanced.

---

## Milestones — the two lines that decide the outcome

### 🚩 Milestone 1 (hour 8) — the rubric is satisfied
Every one of the seven mandated outcomes works end-to-end, even if plain. **Tag it: `git tag m1`.** If everything after this collapses, you still have a complete, demonstrable submission. This is the insurance policy and it is the most important decision in the plan.

### 🚩 Milestone 2 (hour 16) — feature freeze
No new features after hour 16. **M4 enforces this** and has the authority to say no. Every hour past 16 goes to polish, deck, demo rehearsal and rest. Teams lose this hackathon between hours 16 and 22 by adding one more thing.

---

## Working Rules

1. **`main` must always run.** A push that breaks the demo is **reverted, not debugged**.
2. **Branch per member:** `feat/m1-foundation`, `feat/m2-intelligence`, `feat/m3-ml`, `feat/m4-frontend`. Merge to `main` whenever green; mandatory merge at hours 6–8 and 14–16.
3. **Blocked for more than 20 minutes → say so out loud immediately.** Do not grind silently. This is the single most common way 4-person hackathon teams lose hours.
4. **Contract changes are a group decision.** Never edit `schemas.py` alone.
5. **Commit at least once an hour.** Small commits survive; heroic 4-hour commits do not.
6. **No new dependencies after hour 14.**

## Definition of Done

A task is done only when all five hold:

- [ ] Endpoint or component works against **real generated data**, not a stub
- [ ] Visible in the UI, or covered by a test if it has no UI surface
- [ ] Handles the null / missing / impossible cases (this dataset is full of them)
- [ ] Merged to `main` and `main` still runs
- [ ] `STATUS.md` updated

## 2-Hourly Standup — 5 minutes, standing up

At hours 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22. Each member says exactly three things:

> **Done** · **Next** · **Blocked on**

Then one shared question: *"Are all seven outcomes still on track?"* If the answer is no, cut a P1 or P2 immediately. Do not negotiate.

## STATUS.md — create at hour 0, update every checkpoint

```markdown
# STATUS — updated H__

## M1 Foundation
- [x] MOD-01 Data Foundation    DONE  H3
- [x] MOD-02 Virtual Clock      DONE  H3
- [x] MOD-03 Custody Ledger     DONE  H5   (FR-9)
- [ ] MOD-04 Telemetry Stream   WIP   H6   (FR-3)
- [ ] MOD-05 QR Identity        TODO
- [ ] MOD-08 Alert Engine       TODO       (FR-5)
- Blocked: none

## M2 Intelligence
- [ ] MOD-06 Trust Engine ⭐    WIP   H4   (FR-8)  <- critical path
- [ ] MOD-07 KPI & Summary      TODO       (FR-4)
- [ ] MOD-09 Anomaly Engine     TODO       (FR-7)
- [ ] MOD-10 Economics          TODO       (FR-11)
- [ ] MOD-13 Recommendations    TODO       (FR-12)
- Blocked: none

## M3 Predictive
- [ ] MOD-11 Forecast Engine    WIP   H4   (FR-6)
- [ ] MOD-12 Redeployment       TODO       (FR-15, P2)
- [ ] MOD-14 Narration          TODO       (FR-14, P2)
- Blocked: none

## M4 Presentation
- [ ] MOD-15 Contractor Console WIP   H5   (FR-1)
- [ ] MOD-17 Scan App           TODO       (FR-2 UI)
- Blocked: none

## Critical path (MOD-01 -> 04 -> 06 -> 07) must be green by H6
Status: ⚠️ MOD-04 in progress

## Outcome coverage (recheck at H8, H16, H22)
1 Dashboard ✅  2 Check-in/out ✅  3 Usage log ✅  4 Summaries ✅
5 Overdue ✅    6 Forecast ⚠️      7 Anomaly ✅
```

---

## Demo Script (M4 owns this from hour 18) — 3 minutes

Renter-side, so **lead with money, not utilization**. The contractor's opening number is spend.

| # | Beat | ~Time |
|---|---|---|
| 1 | **Contractor console.** 45 machines across 8 sites. Rental spend this month **₹X**. Utilization **61%**. Looks healthy. | 20s |
| 2 | **Flip the Trust toggle.** The numbers move. *"Six of these machines report hours that are physically impossible. That 61% was computed on data nobody verified."* | 25s |
| 3 | **Disputed billing tile: ₹Y invoiced against untrusted data.** Drill into **EQX1002** — billed 20 days, engine never turned on, no site recorded, no operator assigned. *"You are paying for this. Here's the rule that caught it, and the evidence."* | 40s |
| 4 | **EQX1007 — UNACCOUNTED, 19 days.** Nobody is accountable. Open the recovery playbook → assign a custodian → **hand a judge a phone; they scan the printed QR** → ledger updates live on the big screen. | 45s |
| 5 | **Scrub forward 3 days.** EQX1001 flips to OVERDUE live, overrun exposure appears in ₹, and the return-or-extend card recommends calling it off. Hit **Reset**. *(cut this beat first if over time)* | 20s |
| 6 | **Forecast tab.** S002 needs 3 excavators in week 34 — prediction interval shown, backtest MAPE 12%. Two sit idle at S006 → move between your own sites, save **₹Z** net of transport. | 30s |
| 7 | **Close.** *"We don't just track rented equipment. We track how much you can trust what you're being billed for, and who is accountable."* | 10s |

Beat 3 is the emotional centre of the pitch — it is concrete, financial, and drawn entirely from Caterpillar's own sample data. Do not rush it.

**Print three QR codes on paper before hour 22.** The physical scan is the moment judges remember.

## Risks

| Risk | Owner | Mitigation |
|---|---|---|
| Synthetic data looks fake | M1 | Seed the generator from the 7 rows' own distributions; keep those rows verbatim and flagged as ground truth |
| Forecast overfits synthetic history | M3 | Say it out loud; present the **backtest harness** as the deliverable, not the accuracy figure |
| Scope creep kills the demo | M4 | Hour-16 freeze, enforced with authority to refuse |
| Venue wifi dies | M3 | LLM output pre-cached to disk; full dry run with network off at hour 22 |
| Members block each other | All | Frozen contract at hour 1 + exclusive file ownership + mock API from hour 1 |
| Someone burns out | All | Staggered 3-hour rest blocks are scheduled, not optional |
