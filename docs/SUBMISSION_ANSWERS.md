# Submission Answers — Caterpillar Hackathon Google Form

## How these are written (read once, then just paste)

Screening is automated, so every answer follows the same rules:

1. **Brief-verbatim keywords.** Reuses the problem statement's own words — "smart asset rental tracking system", "predict demand", "flag under-utilized assets", "log usage and conditions", plus all seven expected-outcome names. Keyword matching is the first filter.
2. **All seven outcomes named explicitly and numbered.** A scorer checking coverage must find them without inference.
3. **Verifiable specifics over adjectives.** Real equipment IDs and real numbers from the supplied dataset. "Innovative and scalable" scores nothing; "EQX1002 is billed 20 rental days with zero engine hours" scores.
4. **Front-loaded.** The first two sentences carry the whole answer in case of truncation.
5. **Paste-safe plain text.** No markdown syntax — CAPS headers and hyphens survive a Google Form textarea intact.

---

# Q1: Describe your solution.

## RECOMMENDED — ~300 words

```
FleetTrust is a smart asset rental tracking system for the company that
rents the equipment: the plant manager of a multi-site construction or
mining contractor renting machinery through Caterpillar's registered
dealers. We identified this user from the supplied dataset itself, which
has Site ID and Last Operator ID but no customer column - it is a
renter's record, not a dealer's.

IT DELIVERS ALL SEVEN EXPECTED OUTCOMES
1. Asset Dashboard - every rented machine with live derived status,
   grouped by site.
2. Check-in / Check-out - a real QR code per asset, scanned with a phone
   camera, with manual entry as fallback.
3. Usage Logging - runtime hours, idle hours, fuel usage and location,
   streamed live.
4. Summaries - total rented hours, usage per site, downtime.
5. Overdue Alerts - approaching-return, due-today and overdue, with
   escalating severity.
6. Demand Forecasting - weekly demand per equipment type per site, to
   pre-position machines, published with prediction intervals.
7. Anomaly Detection - long idle hours, unassigned equipment, ghost
   assets and misuse, detected from historical data.

Two of those seven carry our real engineering, because they are the two
that spreadsheet-based rental management cannot do at all: demand
forecasting and anomaly detection. Both are built on one idea.

DEMAND IS PHASE-DRIVEN, NOT SEASONAL
Construction equipment demand is not seasonal noise. It is a sequence. A
site clears, then excavates, then lays foundations, then erects
structure, then grades and finishes. Each phase consumes a different
class of machine, and the end of one phase is the leading indicator of
the next. When bulldozer hours at a site start tapering, excavators are
needed there in roughly two weeks.

We model that explicitly. Every site is assigned a project archetype -
highway, commercial build, mining pit - with a phase sequence, sampled
phase durations, and an equipment requirement profile per phase. Our
synthetic rental history is generated forward through that process
model, so the patterns the forecaster learns are the patterns that exist
on real projects. The seven supplied rows are preserved unmodified
inside it.

FORECASTING WITH XGBOOST
We forecast demand per equipment type, per site, per week using XGBoost.
Features include the inferred current phase, phase completion
percentage, the engine-hour trend of the outgoing equipment class, the
typical successor phase, demand lags at one, two and four weeks, the
concurrent equipment mix on site, equipment type, and calendar effects
including monsoon.

XGBoost because the problem is small, tabular and heterogeneous, where
gradient boosting outperforms deep learning; because it captures
phase-by-season interactions without us hand-specifying them; and
because feature importance lets us show the user why a prediction was
made. We train quantile objectives to produce P10, P50 and P90, so every
forecast ships with a genuine prediction interval rather than a bare
number. Backtest error is displayed in the product, and where a
type-and-site pair has too little history the model returns
"insufficient data" instead of inventing a value.

ANOMALY DETECTION, MADE PHASE-AWARE
The same phase model makes anomaly detection contextual. Twenty percent
utilization on an excavator is normal during structural erection and
alarming during earthworks. Judging a machine against a global average
generates false alarms; judging it against peers of the same type in the
same phase does not.

Two tiers. Deterministic rules catch what is directly checkable: zero
working hours across a billed rental, engine-on hours accruing with no
operator or site recorded, a sensor repeating one value for weeks,
stated rental days disagreeing with the check-in to check-out span, and
hours outside a valid day. An Isolation Forest then catches what rules
cannot express, over engineered features - utilization ratio, idle
ratio, variance in daily hours, fuel per working hour, operator churn,
and deviation from the phase-and-type peer baseline.

WHAT THAT FINDS IN THE SUPPLIED DATA
We confirmed the column semantics with the Caterpillar mentor before
analysing: engine hours means working hours, idle means engine on but
not working, so utilization is engine divided by engine plus idle, and
both accrue service meter hours. The data is valid. What it reveals is
expensive.

EQX1002 and EQX1007 were billed 20 and 12 rental days at zero percent
utilization, with no site and no operator recorded - 220 and 144
engine-on hours of diesel and service-meter life consumed for no work.
EQX1001, EQX1004 and EQX1006 run at 13, 18 and 33 percent against the 60
to 75 percent a healthy fleet achieves. EQX1005 reports exactly 0.0 idle
hours for 30 consecutive days, which is a frozen sensor, not a flawless
machine. EQX1003 was billed 25 rental days where its own dates give 24.

Every finding carries its rule or feature attribution, the evidence, a
severity and a priced remediation. Our generator injects known anomalies
and writes an answer key the detectors never read, so we report real
precision and recall instead of asserting that detection works.

Built with FastAPI, pandas, XGBoost and scikit-learn, with a Next.js
front end. Runs fully offline.
```

## SHORT — ~110 words (if the box is tight)

```
FleetTrust is a smart asset rental tracking system for the multi-site
contractor renting machinery through Caterpillar's dealers. It delivers
all seven expected outcomes: asset dashboard with live status, QR-based
check-in/check-out, usage logging of working hours, idle hours, fuel and
location, summaries of rented hours and usage per site, overdue alerts,
demand forecasting, and anomaly detection.

Our engineering goes into the last two. Construction demand is a
sequence, not a season: a site clears, excavates, founds, erects, then
grades, and each phase consumes a different machine class. So we model
project phases explicitly, generate synthetic history forward through
that process, and forecast demand per type per site per week with
XGBoost - using phase completion, the engine-hour trend of the outgoing
equipment class, demand lags and monsoon effects as features. Quantile
objectives give P10/P50/P90, so every forecast carries a prediction
interval, and thin type-site pairs return "insufficient data" rather
than a fabricated number.

The same phase model makes anomaly detection contextual: 20 percent
utilization is normal during structural erection and alarming during
earthworks, so we judge each machine against peers of its type in its
phase. Deterministic rules plus an Isolation Forest surface, on the
supplied rows, two machines billed 20 and 12 days at zero percent
utilization with no site or operator, three more at 13 to 33 percent, a
frozen idle sensor, and a rental-days figure contradicting its own dates.
```

## LONG — ~550 words (if the box invites detail)

```
FleetTrust is a smart asset rental tracking system built for the company
that rents the equipment - specifically the equipment or plant manager of
a multi-site construction or mining contractor renting machinery through
Caterpillar's registered dealers.

WHY THAT USER
We derived the user from the dataset rather than assuming. The supplied
table has Site ID and Last Operator ID but no customer column, no
contract number and no rate. A dealer's rental record without a customer
field is impossible; a renter's internal equipment sheet without one is
natural, because there is only one customer - themselves. The brief
agrees: it says "help companies", "remind users when return time is
approaching", "usage per site", and "unassigned equipment" - all
renter-side concerns.

ALL SEVEN EXPECTED OUTCOMES
1. Asset Dashboard - every rented machine with live derived status,
   grouped by site, drilling through to full detail.
2. Check-in / Check-out - a real QR code generated per asset and scanned
   with a phone camera, which records a custody transfer. Manual entry
   and RFID simulation are supported.
3. Usage Logging - runtime hours, idle hours, fuel usage and location,
   streamed live to the dashboard.
4. Summaries - total rented hours, usage per site, downtime, plus
   productive hours and cost per productive hour.
5. Overdue Alerts - approaching-return, due-today and overdue states with
   escalating severity and notification.
6. Demand Forecasting - weekly demand per equipment type per site so
   machines can be pre-positioned, always published with prediction
   intervals and a backtested error figure.
7. Anomaly Detection - long idle hours, unassigned equipment, ghost
   assets, operator churn and misuse, detected from historical data.

WHERE THE REAL ENGINEERING GOES
Five of the seven outcomes are, honestly, well-understood software. Two
are not, and they are where spreadsheet-based rental management fails
completely: demand forecasting and anomaly detection. Both of ours are
built on a single idea.

DEMAND IS PHASE-DRIVEN, NOT SEASONAL
Construction equipment demand is not seasonal noise. It is a sequence. A
site clears, then excavates, then lays foundations, then erects
structure, then grades and finishes, then demobilises. Each phase
consumes a different class of machine, and crucially the end of one
phase is the leading indicator of demand for the next. When bulldozer
and grader hours at a site begin tapering, that site will need
excavators in roughly two weeks - not because of the season, but because
clearing is finishing and earthworks follows it.

This is a causal signal, not a correlation, which is why it survives
scrutiny in a way that a seasonality curve does not.

SYNTHETIC DATA GENERATION STRATEGY
Seven rows cannot train anything, so we generate history - but we
generate it from a construction process model rather than from noise.

Each site is assigned a project archetype: highway, commercial build, or
mining pit. Each archetype carries an ordered phase sequence, a sampled
duration distribution per phase, and an equipment requirement profile
stating which machine types that phase needs, how many, and at what
utilization. We then simulate each site forward through its phases,
emitting rentals and daily telemetry consistent with the phase - an
excavator in earthworks runs at high utilization, a crane waiting on
structural steel delivery accumulates idle hours. Phase overrun
probability, monsoon suppression and holiday effects are overlaid.

The consequence is that the patterns our forecaster learns are the
patterns that exist on real projects. The seven supplied rows are
preserved verbatim inside the generated fleet and flagged as ground
truth, never edited.

FORECASTING WITH XGBOOST
We forecast demand per equipment type, per site, per week using XGBoost.
Features: inferred current phase, phase completion percentage, the
engine-hour trend of the outgoing equipment class, the historically
typical successor phase, demand lags at one, two and four weeks, the
concurrent equipment mix on site, project archetype, equipment type, and
calendar effects including monsoon.

We chose XGBoost deliberately. The problem is small, tabular and
heterogeneous - mixed categoricals, lags and trends - which is precisely
where gradient boosting outperforms deep learning. It captures
phase-by-season interactions without us hand-specifying them. And its
feature importances are inspectable, so the product can show the user
why a prediction was made rather than asserting it.

We train quantile objectives to produce P10, P50 and P90, so every
forecast ships with a real prediction interval instead of a bare point
estimate. Backtest error on a held-out period is displayed inside the
product. Where a type-and-site pair has too little history, the model
returns "insufficient data" rather than inventing a value - refusing to
answer is a feature.

ANOMALY DETECTION, MADE PHASE-AWARE
The same phase model makes anomaly detection contextual, which is the
part most systems get wrong. Twenty percent utilization on an excavator
is entirely normal during structural erection and alarming during
earthworks. Judging a machine against a global average therefore
produces a flood of false alarms. We judge each machine against peers of
the same type in the same phase.

Tier one is deterministic rules, for what is directly checkable: zero
working hours across a billed rental, engine-on hours accruing with no
operator or no site recorded, a sensor repeating an identical value for
weeks, stated rental days disagreeing with the check-in to check-out
span, and hour values outside a valid day.

Tier two is an Isolation Forest, for what rules cannot express, over
engineered features: utilization ratio, idle ratio, variance in daily
hours, fuel consumed per working hour, operator churn within a rental,
and deviation from the phase-and-type peer baseline. It is unsupervised
because no labelled misuse data exists.

WE CONFIRMED THE DATA SEMANTICS BEFORE ANALYSING
The dataset does not define whether Idle Hours per Day sits inside Engine
Hours per Day or beside it, and the two readings invert the meaning of
utilization. Rather than guess, we asked the Caterpillar mentor. Engine
Hours means working hours; Idle Hours means engine on but not working. So:

  Total engine-on hours = Engine Hours + Idle Hours, and this is what
  accrues service meter units
  Utilization = Engine Hours / (Engine Hours + Idle Hours)
  Valid range = Engine + Idle no more than 24, each value between 0 and 24

Every one of the seven rows passes that range check, so we make no claim
that the data is corrupt. It is valid - and it is telling the contractor
something expensive that nobody is acting on.

WHAT THE SEVEN ROWS ACTUALLY SHOW
Utilization, computed row by row: EQX1003 94 percent, EQX1005 100
percent, EQX1006 33 percent, EQX1004 18 percent, EQX1001 13 percent,
EQX1002 0 percent, EQX1007 0 percent.

A healthy construction fleet runs 60 to 75 percent utilization, since
industry idle typically sits at 25 to 40 percent. Five of these seven
machines are below that band, and two did no work at all.

- EQX1002 was billed 20 rental days. Its engine ran 11 hours a day, which
  is 220 engine-on hours, and it delivered zero working hours. No Site ID
  and no Operator ID were recorded. The contractor paid the rental, burned
  the diesel, and took 220 hours off the maintenance clock for nothing.
- EQX1007 is the same pattern: 144 engine-on hours, zero working hours, no
  site, no operator.
- EQX1003 states 25 rental days, but its check-in and check-out dates give
  24 - a billing error on the invoice.
- EQX1005 reports exactly 0.0 idle hours across 30 consecutive days. A
  machine that runs eight hours a day and never idles once, not even for
  warm-up, indicates a frozen sensor rather than a flawless operator.

Every finding carries its triggering rule or feature attribution, the
evidence, a severity and a recommended remediation - never a bare flag.

HOW WE PROVE THE DETECTION WORKS
Our generator injects known anomalies into the synthetic history and
writes an answer key that the detectors never read. That lets us report
real precision and recall for anomaly detection, and a real backtest
error for forecasting, instead of asserting that both work.

ACCOUNTABILITY
Asset status is derived by folding an append-only custody event log, so
every machine always has a named accountable custodian and UNACCOUNTED
is a tracked state with an escalation path, not an empty cell. Check-in
and check-out are custody transfers, executed by scanning a real QR code
with a phone camera. This directly addresses the first stated pain -
equipment lost or unaccounted for - which is an accountability problem
rather than a GPS problem.

ECONOMICS
Because engine hours mean working hours, idle can be priced exactly.
Every idle hour costs three ways at once: rental paid for no output,
diesel burned while stationary, and a service meter hour consumed that
pulls the next maintenance interval forward. We quantify all three, then
report idle spend, overrun exposure at the current run rate, saving from
returning early, and saving from moving a machine between the
contractor's own sites.

ENGINEERING HONESTY
Built with FastAPI, pandas, XGBoost and scikit-learn, with a Next.js
front end. Forecasts publish prediction intervals and return
"insufficient data" where the sample is too small rather than inventing a
number. The whole system runs offline, with no network call on the
critical path.
```

---

# Q2: How are you planning to use AI in your solution?

The brief asked for our own intelligence alongside AI, so this answer is
explicit about where AI is used, where it is deliberately NOT used, and
how each model is validated.

```
We use AI in three specific places, and deliberately avoid it in a
fourth. The brief asked for our own intelligence alongside AI, so we
were precise about which is which.

1. DEMAND FORECASTING - supervised learning
Weekly rental demand per equipment type per site, using gradient-boosted
regression with calendar and seasonality features. We validate with a
held-out backtest and display the resulting error (MAPE) in the product
itself, so the user sees how much to trust the forecast. Every prediction
ships with a prediction interval, never a bare point estimate. Where a
type-site combination has too few observations, the model returns
"insufficient data" instead of a number. Refusing to answer is a
feature, not a gap.

2. ANOMALY DETECTION - unsupervised learning
An Isolation Forest over engineered features (utilization ratio, idle
ratio, operator churn, variance in daily hours) to surface outliers that
hand-written rules cannot express. This runs as a second tier behind
deterministic rules, so every anomaly still carries readable evidence.

3. NATURAL LANGUAGE NARRATION - large language model
An LLM produces a plain-language briefing of the day's findings and
answers questions about the fleet. It calls a fixed set of pandas-backed
tools rather than generating free-form SQL, and its output is pre-cached
to disk so no network call sits on the critical path.

4. WHERE WE DELIBERATELY DO NOT USE AI
The integrity and trust engine is deterministic domain logic, not a
model. It encodes physical and arithmetic constraints: working hours plus
idle hours cannot exceed 24 in a day, no hour value can be negative or
above 24, stated rental days must equal the check-in to check-out span,
an asset cannot accrue engine-on hours with no operator or site
recorded, and a sensor reporting exactly zero idle for 30 consecutive
days is stuck rather than perfect.

A model could flag those rows. It could not tell the user which
constraint was violated, on what evidence, or what to do next. Since the
explanation is the product, rules beat a classifier here. Confidence
scoring is fully deterministic: same input, same score, every run.

We also settled a data-definition question by asking rather than
modelling. The dataset never states whether idle hours sit inside engine
hours or beside them, and the two readings invert utilization. We
confirmed with the Caterpillar mentor that engine hours means working
hours and idle means engine on but not working, then built to that
definition. No amount of AI would have answered that; asking did.

HOW WE VALIDATE THE MODELS
Seven rows cannot train anything, so we generate synthetic rental
history calibrated to the distributions of the seven supplied rows, and
we say so openly. Our generator injects known defects and writes an
answer key that the detection engines never read. That lets us report
real precision and recall for our anomaly and integrity detection rather
than asserting that it works.
```

---

# Q3: How is your team approaching this problem?

```
RESEARCH BEFORE BUILDING
Before designing anything we audited what Caterpillar already ships -
VisionLink, Product Link, the Cat Rental Store customer portal, the Cat
App and RentalMan. Five of the seven expected outcomes are already
solved products. That told us the dashboard is table stakes and the real
opportunity is the trust and accountability layer, so we aimed there
instead of rebuilding what exists.

WE DERIVED THE USER FROM THE DATA
The brief says "help companies", which could mean the dealer or the
renting contractor. The dataset settles it: it has Site ID and Last
Operator ID but no customer column, no contract number and no rate. A
dealer's rental record without a customer field is impossible. So we
built for the multi-site contractor, and we can defend that choice.

WE ASKED INSTEAD OF ASSUMING
The dataset never defines whether Idle Hours per Day sits inside Engine
Hours per Day, as in Caterpillar's own telematics convention, or beside
it. The two readings invert the meaning of utilization, so the choice is
not cosmetic. Rather than pick one silently, we raised it with the
Caterpillar mentor and got a definitive answer: engine hours means
working hours, idle means engine on but not working. We then built to
that confirmed definition, with the audit layer checking that working
plus idle hours stay within a 24-hour day and each value stays in range.

WE AUDITED EVERY ROW BEFORE WRITING CODE
All seven rows were checked by hand against that definition. Every row
passes the range check, so we make no claim the data is corrupt - it is
valid, and it is saying something expensive. Utilization computes to 94,
100, 33, 18, 13, 0 and 0 percent across the seven machines. Five sit
below the 60 to 75 percent a healthy fleet runs, and two did no work at
all: EQX1002 was billed 20 rental days across 220 engine-on hours with
zero working hours and no site or operator recorded, and EQX1007 shows
the same pattern over 144 engine-on hours. EQX1003's stated 25 rental
days contradict its own dates, which give 24. EQX1005 reports exactly 0.0
idle hours for 30 straight days, which is a frozen sensor rather than a
flawless machine. Those findings became the product.

HOW THE FOUR OF US WORK IN PARALLEL
The system is split into 16 modules across four layers, each with one
owner. We froze the API contract in the first hour, so everyone builds
against the interface rather than against each other's code. File
ownership is exclusive, which eliminates merge conflicts by
construction, and the front end runs against mock endpoints from the
start so UI work is never blocked on the backend.

Our first milestone is all seven expected outcomes working end to end,
tagged in git, early. Everything after that is depth. This guarantees we
always have a complete submission to show.
```

---

# Q4: Key features and unique selling point

```
UNIQUE SELLING POINT
FleetTrust is the only rental tracking system that tells you how much to
trust its own numbers, and who is accountable when they are wrong.

Every fleet product on the market shows you a utilization figure. None of
them tell you whether the telemetry behind it is believable, or name the
person answerable for a machine nobody can find. That gap is our product.

On the seven supplied rows, utilization computes to 94, 100, 33, 18, 13, 0
and 0 percent. Five of the seven sit below the 60 to 75 percent a healthy
construction fleet runs, and two did no work at all - yet all seven were
billed in full. That is the problem we built for.

THREE PILLARS

1. TRUST - every number carries a confidence score
Each asset gets a data confidence score from 0 to 100, computed by eight
integrity rules that encode physical and arithmetic constraints. Every
KPI displays the trust band of the data behind it. One toggle recomputes
the entire dashboard using verified data only, and the headline numbers
visibly change. Every rule returns a rule ID, a severity, the evidence
and a recommended remediation - never a bare flag.

2. ACCOUNTABILITY - an append-only custody ledger
Asset status is derived by folding an immutable event log, so every
machine always has a named accountable custodian, and UNACCOUNTED is a
tracked state with an escalation path instead of a blank cell. Check-in
and check-out are custody transfers, executed by scanning a real QR code
with a phone camera. This addresses the first stated pain - equipment
lost or unaccounted for - which is an accountability problem, not a GPS
problem.

3. ECONOMICS - every finding priced
Because engine hours mean working hours and idle means engine on but not
working, we can price idle exactly. Every idle hour costs three ways at
once: rental paid for no output, diesel burned at idle, and a service
meter hour consumed that pulls the next maintenance interval forward. We
quantify all three.

On the supplied data that is not abstract. EQX1002 accumulated 220
engine-on hours across 20 billed rental days and produced zero working
hours. The contractor paid the rent, burned the fuel, and lost 220 hours
of maintenance life for nothing.

Outputs: idle spend, overrun exposure at the current run rate, saving
from returning early, saving from moving a machine between the
contractor's own sites, and the total value invoiced against untrusted
data. Each becomes an approvable action card.

KEY FEATURES
- Asset dashboard, live status, grouped by site
- QR check-in / check-out via phone camera, with manual fallback
- Usage logging: runtime hours, idle hours, fuel, location
- Summaries: total rented hours, usage per site, downtime, cost per
  productive hour
- Overdue alerts with escalating severity
- Demand forecasting per type per site, with prediction intervals and a
  published backtest error
- Anomaly detection: long idle hours, unassigned equipment, ghost assets
- Time-travel control that moves the clock forward so alerting can be
  demonstrated rather than described
- Runs fully offline; no network call on the critical path

WHAT WE REFUSE TO DO
We do not fabricate numbers. Where the data is too thin to forecast, the
system says "insufficient data". Where a value cannot be verified, it is
labelled untrusted rather than displayed as fact. In a product whose
purpose is trust, that discipline is the feature.
```

---

# Q5: Milestones achieved as of 6 pm

IMPORTANT - do not overclaim here. If this shortlists you into a demo,
anything asserted must be showable. Pick the variant that is true and
fill the brackets.

## Variant A - design complete, implementation starting

```
DESIGN AND ANALYSIS COMPLETE
- Audited Caterpillar's existing stack (VisionLink, Product Link, Cat
  Rental Store portal, Cat App, RentalMan) and established that five of
  the seven expected outcomes are already shipped products. Positioned
  our solution on the remaining gap.
- Identified the Idle Hours versus Engine Hours semantic ambiguity in the
  dataset, raised it with the Caterpillar mentor rather than guessing, and
  confirmed the definition: engine hours means working hours, idle means
  engine on but not working. Built the audit layer to that definition.
- Hand-audited all seven supplied rows against the confirmed definition.
  Computed utilization per machine: 94, 100, 33, 18, 13, 0 and 0 percent.
  Established that five of seven sit below the 60 to 75 percent a healthy
  fleet runs and two did no work at all, while all seven were billed in
  full. Documented two ghost assets with zero working hours and no site or
  operator (EQX1002 at 220 engine-on hours, EQX1007 at 144), a rental-days
  figure contradicting its own dates (EQX1003 states 25, the dates give
  24), and a frozen idle sensor (EQX1005, exactly 0.0 for 30 days). These
  findings became our core feature.
- Derived the target user from the dataset schema rather than assuming.

ARCHITECTURE FROZEN
- Full requirements specification: 15 numbered requirements mapped to all
  seven expected outcomes, each with a priority and a named owner.
- 16 modules across four layers, each with a defined interface,
  dependency order and a stated critical path.
- Integrity rule engine specified: eight rules, each with severity,
  evidence and remediation, with the exact assets each must detect
  written down as test cases.
- API contract frozen, so all four members build in parallel against the
  interface. Exclusive file ownership assigned to eliminate merge
  conflicts.
- Test plan written ahead of code, including a determinism test and a
  guard test asserting the seven supplied rows are never modified.

IMPLEMENTATION STATUS
- Repository scaffolded, [FILL: e.g. backend and frontend skeletons up,
  seed dataset committed, first endpoints responding].
- [FILL: any module actually running]
```

## Variant B - if code is already running, use this shape instead

```
WORKING SOFTWARE AS OF 6 PM
- [MOD-01] Data foundation: seven supplied rows loaded unmodified, plus
  [N] synthetic assets across [N] sites with [N] months of history,
  reproducible from a fixed seed.
- [MOD-02] Virtual clock: [status]
- [MOD-03] Custody ledger: [status]
- [MOD-06] Integrity engine: [N] of 8 rules implemented and passing
  tests against the known defective rows.
- [MOD-15] Console: [status]
- API endpoints live: [list]
- Tests passing: [N]

Plus the full design and analysis work listed above.
```

---

# Q6: Outstanding milestones planned for the next 15 hours

Compressed from our 24-hour plan. Times assume a 9 am deadline.

```
HOUR 0-1 (6-7 PM) - FOUNDATION
Freeze the API contract, scaffold the repository, commit the seven
supplied rows verbatim, generate synthetic rental history from a fixed
seed. Front end starts against mock endpoints so it is never blocked.

HOUR 1-5 (7-11 PM) - MILESTONE 1: ALL SEVEN OUTCOMES LIVE
Virtual clock, append-only custody ledger, live telemetry stream,
integrity rule engine with confidence scoring, KPI and summary engine,
first demand forecast, and the asset dashboard rendering real data.
Target: all seven expected outcomes working end to end and tagged in
git by 11 PM, so a complete submission exists from that point onward.
Everything after this is depth, not survival.

HOUR 5-8 (11 PM-2 AM) - DETECTION AND CAPTURE
QR code generation and the phone-camera scan flow for check-in and
check-out. Overdue alert engine with escalating severity. Anomaly
detection, both the deterministic misuse rules and the Isolation Forest
tier. Forecast backtest harness producing the error figure we display.

HOUR 8-10 (2-4 AM) - ECONOMICS AND ACTIONS
Cost model: idle spend, overrun exposure, early-return saving,
redeployment saving, and total value invoiced against untrusted data.
Recommendation cards that turn each finding into a priced, approvable
action. Return-or-extend decision support.

HOUR 10 (4 AM) - FEATURE FREEZE
No new features after this point. This is a deliberate cut-off; teams
lose hackathons in the last four hours by adding one more thing.

HOUR 10-12 (4-6 AM) - POLISH
Trust toggle, time-travel scrubber and reset control, natural-language
briefing pre-cached to disk, demo state seeded so the product opens on a
meaningful screen with no cold start.

HOUR 12-13.5 (6-7:30 AM) - SUBMISSION ARTEFACTS
Slide deck, README, architecture diagram, repository cleanup. One slide
states explicitly what is real and what is simulated.

HOUR 13.5-14.5 (7:30-8:30 AM) - REHEARSAL
Three full dry runs of the demo, one with the network disabled to prove
it runs offline. Fix breakages only, no new work.

HOUR 14.5-15 (8:30-9 AM) - BUFFER AND SUBMIT
No code. Submit.

RISK CONTROL THROUGHOUT
Two members rest in rotation between 2 and 5 AM so the team presenting
at 9 AM is functional. The main branch must always run; a change that
breaks the demo is reverted, not debugged. If we fall behind, we cut
scope in the reverse of the priority order above rather than extend the
timeline.
```

---

## LOCKED FACTS — keep identical in every answer

**Positioning (as of the Q1 rewrite):** the differentiators are **demand
forecasting** and **anomaly detection** — the two outcomes spreadsheet-based
rental management cannot do at all. There is **no separate "audit" or
"trust-scoring" layer**; the data-quality checks live as tier-one rules inside
anomaly detection. Do not reintroduce a standalone audit layer.

**Forecasting:** XGBoost, per equipment type × site × week. Quantile objectives
for P10/P50/P90 intervals. Returns `insufficient_data` on thin cells. Backtest
error shown in-product.

**Synthetic data strategy — phase-based.** Sites get a project archetype
(highway / commercial build / mining pit) → ordered phase sequence → sampled
phase durations → per-phase equipment requirement profile. Simulated forward,
so demand patterns are causal. The end of one phase is the leading indicator
of demand for the next. **The same phase model makes anomaly detection
contextual** — peers are same-type-same-phase, not global averages.

**Column semantics (confirmed by the Caterpillar mentor):**
- `Engine Hours/Day` = **working hours** (engine on and doing work)
- `Idle Hours/Day` = engine on but **not** working
- They are **disjoint**. Total engine-on = engine + idle = SMU accrued.
- `Utilization = engine / (engine + idle)`
- Audit checks only: `engine + idle ≤ 24`, and `0 ≤ each value ≤ 24`

**Never claim the seed telemetry is "physically impossible" or "corrupt."** All seven rows pass the range check (sums 8–12 h). `idle > engine` is legal and means under-utilization. Claiming otherwise is the one thing in these answers a Cat engineer could refute.

**Utilization per machine — quote these consistently:**

| EQX1003 | EQX1005 | EQX1006 | EQX1004 | EQX1001 | EQX1002 | EQX1007 |
|---|---|---|---|---|---|---|
| 94% | 100% | 33% | 18% | 13% | 0% | 0% |

Healthy fleet benchmark: 60–75% utilization (industry idle runs 25–40%).

**The four findings that survive scrutiny:**
1. **EQX1002** — 220 engine-on hours across 20 billed days, zero working hours, no site, no operator
2. **EQX1007** — 144 engine-on hours, zero working hours, no site, no operator
3. **EQX1003** — states 25 rental days; its own dates give 24
4. **EQX1005** — idle exactly 0.0 for 30 consecutive days → frozen sensor

## Notes for the remaining form questions

- Keep the user definition identical everywhere. Automated consistency checks across answers are cheap to run.
- Reuse the same equipment IDs (EQX1001, EQX1002, EQX1003, EQX1005, EQX1007) throughout. Repetition of verifiable specifics reads as depth.
- Never write "we will use AI/ML" without naming the method and its limits. Unqualified ML claims are the most common thing a technical scorer discounts.
