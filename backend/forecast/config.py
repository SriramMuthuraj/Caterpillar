"""MOD-11 Forecast Engine — configuration.

Every constant that shapes the synthetic rental history or the forecaster lives
here, so the whole module is auditable from one file. Nothing in this package
reads a value that is not declared below.

Forecast target (locked): **new rentals commencing** in ISO week W for a given
(equipment_type x site). Not "assets currently on rent" — that series is
dominated by persistence and a good score on it proves nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------

# Every rng in this package is spawned from MASTER_SEED with an explicit
# per-(site, type) sub-seed, so adding a site does not shift another site's
# draws. NFR-3: same seed -> same fleet, same scores, same findings.
MASTER_SEED = 20250818

# --------------------------------------------------------------------------
# Time
# --------------------------------------------------------------------------

# Fallback "now" used only when MOD-02 (Virtual Clock) is not importable.
# 2025-08-18 is a Monday and the first day of ISO week 34 of 2025 — the week
# the demo script forecasts against. NEVER call datetime.now() in this package.
DEMO_NOW = date(2025, 8, 18)

# Three monsoon cycles. Two (104) is enough to *fit* seasonality, but the phase
# models train on completed phase windows, and a site only completes a phase
# every ~20 weeks — at 104 weeks there are too few finished windows to learn
# from. The extra year roughly doubles them.
HISTORY_WEEKS = 156
FORECAST_HORIZON_WEEKS = 8
INTERVAL_LEVEL = 0.80        # 80% prediction interval

# --------------------------------------------------------------------------
# The refusal (FR-6): where n is too small we decline rather than fabricate
# --------------------------------------------------------------------------

MIN_NONZERO_WEEKS = 12       # weeks with at least one rental start
MIN_TOTAL_RENTALS = 20       # total rentals observed in the cell

# --------------------------------------------------------------------------
# Demand generating process
# --------------------------------------------------------------------------

# Expected new rentals per site per week, before every multiplier below.
#
# Set so a healthy (site x type) cell runs at roughly 2-3 new rentals a week.
# Below about 1, Poisson noise swamps the seasonal signal, every forecast reads
# "0.4 machines" and the model cannot meaningfully beat a flat mean — the
# forecast tab then looks like a rounding error on screen. The implied fleet is
# a few hundred machines, which is the right order for a Cat dealer branch.
BASE_LAMBDA = 11.0

# Gamma-Poisson dispersion. var = lam + lam^2 / DISPERSION_R.
# Lower r = burstier arrivals. Demand is over-dispersed; pure Poisson is too tame.
DISPERSION_R = 6.0

# Turnaround: a returned machine is not re-rentable the same day.
TURNAROUND_DAYS = 2

# --------------------------------------------------------------------------
# Operators
# --------------------------------------------------------------------------
# `Last Operator ID` is in the supplied schema. Operators are drawn from a
# per-site pool, so an operator is associated with a site rather than a machine
# — which is what makes "this machine changed hands four times this month" a
# detectable signal rather than noise.
OPERATORS_PER_SITE = 8

# --------------------------------------------------------------------------
# Contract length vs phase length
# --------------------------------------------------------------------------
# THE central quantity of this module. check_in/check_out is the *contract*
# clock (when the rent starts and expires); the phase is the *work* clock (when
# the machine is actually needed). They are set by different people and do not
# line up, and every mismatch is money:
#
#   rent expires BEFORE phase ends  -> machine lost mid-work, extend or replace
#   phase ends BEFORE rent expires  -> paying for idle capacity, redeploy it
#
# A contract is therefore drawn to *roughly* cover the machine's remaining need
# in the current phase, then slipped. If durations were drawn independently of
# phase (as they were originally) the gap would be pure noise and there would be
# nothing for the allocator to detect.
CONTRACT_COVERAGE_MEAN = 1.00   # 1.0 = contract exactly covers remaining phase
CONTRACT_COVERAGE_SD = 0.28     # planning error, both directions
CONTRACT_MIN_DAYS = 5
CONTRACT_MAX_DAYS = 120


@dataclass(frozen=True)
class EquipmentType:
    """A rental class.

    peak_progress / phase_width describe *when in a construction project's life*
    this class is wanted, as a Gaussian bump over project progress in [0, 1].
    Excavators front-load; compactors are a finishing-phase machine. This is the
    structure that makes redeployment (MOD-12) meaningful — two sites at
    different phases want different machines in the same week.

    monsoon_sensitivity in [0, 1] scales the monsoon multiplier. Earthmoving
    stops on saturated ground; indoor-adjacent lifting barely notices.
    """

    name: str
    share: float               # share of a site's demand, sums to ~1.0
    peak_progress: float
    phase_width: float
    monsoon_sensitivity: float
    fuel_burn_l_per_h: float   # litres/hour while working, by machine class


# Progress at which a project is treated as wound down. The last phase's band is
# open-ended so it can absorb snagging work, but a project does not run forever:
# past this point the site stops renting and stops appearing in phase windows.
PROJECT_TAIL_PROGRESS = 1.15


# No day_rate here on purpose. Rental pricing lives in `data/rates.yaml`, which
# is M2's file per the ownership table — generating rates into M3's data would
# create a second source of truth for money.
EQUIPMENT_TYPES: tuple[EquipmentType, ...] = (
    EquipmentType("Excavator",      0.30, 0.20, 0.28, 1.00, 17.0),
    EquipmentType("Wheel Loader",   0.20, 0.32, 0.30, 0.85, 14.0),
    EquipmentType("Backhoe Loader", 0.22, 0.50, 0.40, 0.70,  7.5),
    EquipmentType("Telehandler",    0.15, 0.65, 0.30, 0.45,  6.0),
    EquipmentType("Compactor",      0.13, 0.82, 0.25, 0.60,  9.0),
)

# Fuel burn while the engine runs but the machine is not working, as a fraction
# of the working rate. An idling diesel still consumes — roughly a quarter of
# its working draw — which is what makes idle hours cost money rather than
# merely waste time. This is the coefficient that turns FR-11's idle burn from
# an assertion into a calculation.
IDLE_FUEL_FRACTION = 0.25

# Machine position is jittered around the site centroid. ~0.01 deg is ~1.1 km,
# about the footprint of a real construction site — a machine is somewhere on
# the site, not stacked on its centroid.
GEO_JITTER_DEG = 0.010


@dataclass(frozen=True)
class Site:
    """A customer project site.

    A site is positioned by **which phase it is in at `now`**, not by a start
    week. Phase durations slip per site (PHASE_SLIP_SIGMA), so a site's start
    week is not knowable until its schedule has been drawn — and the one thing
    this fleet must guarantee is that the twelve sites are spread across all six
    phases at `now`. Stating the destination and deriving the start keeps that
    guarantee true no matter how the durations land.

    ``pace`` scales every phase of this project: a fast-tracked job runs each
    phase shorter than nominal, a troubled one longer. It is the site-level
    part of the slip the phase-end model has to see through, and it is never
    exposed to that model.
    """

    site_id: str
    name: str
    region: str
    scale: float               # relative project size
    pace: float                # site-wide multiplier on every phase duration
    phase_now: str             # the phase this site is in at `now`
    phase_frac_now: float      # how far through that phase, in [0, 1)
    growth: float              # annual trend, exp(growth * years)
    lat: float                 # site centroid
    lon: float


# Real Tamil Nadu locations. Plausible geography costs nothing and means the map
# survives someone in the room knowing the region.
#
# start_week is staggered so that at `now` (the last history week, index
# HISTORY_WEEKS - 1) the twelve sites sit at *different* points in their life:
# two apiece in each of the six phases. Without that spread the product has
# nothing to say — the whole pitch is "this site is finishing phase X, here is
# what phase Y needs", and a fleet of finished projects has no next phase.
#
# Twelve sites rather than six because the phase-end model trains on completed
# phase windows, and six sites do not produce enough of them (see phase.py).
# Synthetic sites are free; training data is not.
# Two sites in each of the six phases at `now`, and within each pair one is
# early in the phase and one is late — so the demo board shows both "this
# transition is imminent" and "this one is weeks out" for every phase.
#
#                                                scale  pace  phase_now        frac
SITES: tuple[Site, ...] = (
    Site("S001", "Chennai Metro Ph2",     "TN-North",   1.15, 1.18, "clearing",       0.30,  0.06,
         13.0827, 80.2707),
    Site("S002", "Hosur Industrial Park", "TN-West",    1.30, 0.78, "clearing",       0.75,  0.10,
         12.7409, 77.8253),
    Site("S003", "Coimbatore Ring Road",  "TN-West",    0.95, 1.02, "excavation",     0.25,  0.02,
         11.0168, 76.9558),
    Site("S004", "Krishnagiri Quarry",    "TN-West",    0.85, 1.32, "excavation",     0.80,  0.01,
         12.5186, 78.2137),
    Site("S005", "Sriperumbudur Plant",   "TN-North",   0.70, 0.85, "foundation",     0.35,  0.05,
         12.9675, 79.9430),
    Site("S006", "Madurai Bypass",        "TN-South",   1.00, 1.22, "foundation",     0.85, -0.03,
          9.9252, 78.1198),
    Site("S007", "Trichy Ring Main",      "TN-Central", 0.90, 0.92, "erection",       0.30,  0.03,
         10.7905, 78.7047),
    Site("S008", "Salem Steel Expansion", "TN-West",    1.10, 1.12, "erection",       0.80,  0.04,
         11.6643, 78.1460),
    Site("S009", "Tuticorin Port Yard",   "TN-South",   0.80, 0.72, "grading",        0.25,  0.02,
          8.7642, 78.1348),
    Site("S010", "Erode Bypass",          "TN-West",    0.75, 1.28, "grading",        0.80, -0.01,
         11.3410, 77.7172),
    Site("S011", "Vellore Township",      "TN-North",   0.95, 0.88, "demobilisation", 0.30,  0.03,
         12.9165, 79.1325),
    Site("S012", "Thanjavur Canal Works", "TN-Central", 0.70, 1.05, "demobilisation", 0.75,  0.01,
         10.7870, 79.1378),
    # A second cohort, same six-phase spread. Twelve sites yield only ~30
    # completed phase windows, and 30 groups is not enough to fit a duration
    # model that beats "the average phase takes N weeks" — with that little
    # data the average IS the best available answer. Twenty-four roughly doubles
    # the training windows and, incidentally, doubles the pool of machines
    # redeployment can draw on.
    Site("S013", "Karur Textile Park",    "TN-Central", 0.85, 0.75, "clearing",       0.55,  0.05,
         10.9601, 78.0766),
    Site("S014", "Namakkal Logistics Hub","TN-West",    1.05, 1.30, "clearing",       0.20,  0.07,
         11.2189, 78.1677),
    Site("S015", "Dindigul Ring Road",    "TN-South",   0.90, 0.82, "excavation",     0.60,  0.02,
         10.3673, 77.9803),
    Site("S016", "Tirunelveli Water Grid","TN-South",   1.00, 1.15, "excavation",     0.40, -0.02,
          8.7139, 77.7567),
    Site("S017", "Cuddalore Petro Yard",  "TN-North",   1.20, 0.90, "foundation",     0.65,  0.06,
         11.7480, 79.7714),
    Site("S018", "Villupuram Junction",   "TN-North",   0.80, 1.25, "foundation",     0.15,  0.01,
         11.9401, 79.4861),
    Site("S019", "Kanchipuram IT Park",   "TN-North",   1.10, 0.80, "erection",       0.55,  0.08,
         12.8342, 79.7036),
    Site("S020", "Tiruppur Knitwear Zone","TN-West",    0.95, 1.20, "erection",       0.15,  0.04,
         11.1085, 77.3411),
    Site("S021", "Nagercoil Coastal Road","TN-South",   0.75, 0.95, "grading",        0.55, -0.01,
          8.1833, 77.4119),
    Site("S022", "Pudukkottai Reservoir", "TN-Central", 0.85, 1.10, "grading",        0.10,  0.02,
         10.3833, 78.8001),
    Site("S023", "Ariyalur Cement Line",  "TN-Central", 1.00, 0.86, "demobilisation", 0.55,  0.00,
         11.1401, 79.0782),
    Site("S024", "Perambalur Bypass",     "TN-Central", 0.70, 1.24, "demobilisation", 0.15, -0.02,
         11.2342, 78.8808),
)

SITE_BY_ID: dict[str, Site] = {s.site_id: s for s in SITES}


# --------------------------------------------------------------------------
# Project phases
# --------------------------------------------------------------------------
# A construction project is a *sequence*, not a season: clear -> excavate ->
# found -> erect -> grade -> demobilise. The end of one phase is the leading
# indicator of demand for the next, which is a causal signal rather than a
# correlational one.
#
# These bands are a *labelling* of structure the generator already produces.
# EQUIPMENT_TYPES.peak_progress / phase_width place each machine class at a
# point in project life, so banding progress yields a mix that shifts
# monotonically across the sequence (excavators 48% -> 8%, compactors 3% -> 19%)
# without touching the demand process itself.

@dataclass(frozen=True)
class Phase:
    """One phase of a project and how long it nominally runs."""

    name: str
    order: int
    base_weeks: int            # nominal duration before slip


PHASES: tuple[Phase, ...] = (
    Phase("clearing",       1, 10),
    Phase("excavation",     2, 16),
    Phase("foundation",     3, 18),
    Phase("erection",       4, 22),
    Phase("grading",        5, 14),
    Phase("demobilisation", 6, 10),
)

PHASE_BY_NAME: dict[str, Phase] = {p.name: p for p in PHASES}
PHASE_NAMES: tuple[str, ...] = tuple(p.name for p in PHASES)
NOMINAL_PROJECT_WEEKS = sum(p.base_weeks for p in PHASES)

# Schedule slip has two parts, and the split between them is what decides
# whether the phase-end model has anything to learn.
#
#   duration = base_weeks x site.pace x lognormal(0, PHASE_SLIP_SIGMA)
#              \_______________________/   \_______________________/
#               persistent, learnable        irreducible, per-phase
#
# **Persistent slip dominates, and that is a domain claim, not a convenience.**
# Schedule performance is autocorrelated within a project: the crew, the ground
# conditions, the client's decision latency and the subcontractor bench are the
# same in month nine as in month two, so a job that ran 25% long through
# clearing and excavation runs long through erection too. Treating each phase as
# an independent draw — which an earlier version of this generator did — makes
# slip pure noise, and then no model can beat "the average phase takes N weeks",
# because there is genuinely nothing to know.
#
# So `pace` spreads widely across sites (0.70-1.35) and the per-phase noise is
# small. That is what makes a site's own track record predictive of its next
# phase, which is exactly the inference a planner makes by hand.
PHASE_SLIP_SIGMA = 0.09
PHASE_MIN_WEEKS = 5


def next_phase(name: str) -> Phase | None:
    """The phase that follows ``name``, or None if the project is ending."""
    order = PHASE_BY_NAME[name].order
    return next((p for p in PHASES if p.order == order + 1), None)

# Deliberately starved cells. These exist so `insufficient_data` fires against
# real generated data instead of being a branch nobody ever exercises — and each
# one is domain-plausible (a quarry does not rent telehandlers).
SPARSE_CELLS: dict[tuple[str, str], float] = {
    ("S004", "Telehandler"): 0.03,
    ("S004", "Compactor"): 0.06,
    ("S005", "Excavator"): 0.05,
    ("S003", "Compactor"): 0.04,
    ("S001", "Compactor"): 0.08,
}

# Month multipliers, applied at the week's start month.
#
# MONSOON: south-west monsoon Jun-Sep collapses earthmoving; Oct-Dec is the
# catch-up surge as projects claw back the lost quarter.
MONSOON_MULT = {
    1: 1.05, 2: 1.05, 3: 1.05, 4: 1.00, 5: 0.95, 6: 0.55,
    7: 0.40, 8: 0.45, 9: 0.70, 10: 1.30, 11: 1.35, 12: 1.15,
}

# FISCAL: Indian FY ends 31 March. Q4 budget flush, April collapse.
FISCAL_MULT = {
    1: 1.15, 2: 1.20, 3: 1.30, 4: 0.75, 5: 0.85, 6: 0.95,
    7: 1.00, 8: 1.00, 9: 1.00, 10: 1.05, 11: 1.05, 12: 1.05,
}

MONSOON_MONTHS = (6, 7, 8, 9)
FISCAL_Q4_MONTHS = (1, 2, 3)

# --------------------------------------------------------------------------
# Economics — what the allocator decides with
# --------------------------------------------------------------------------
# The allocator's job is to choose between moving a machine you have already
# paid for and calling off a new one from the dealer. That choice must be made
# with money, not with a tuned threshold: "wait if the delay is under 10 days"
# is unarguable-with and the first thing anyone will poke at. Two costs, both
# reported alongside every recommendation, and the cheaper one wins.
#
# Figures are INR and are order-of-magnitude plausible for the Indian rental
# market rather than quoted from a rate card. They are declared here so a single
# edit re-prices every recommendation in the product.

# Dealer day rate by machine class.
DAY_RATE_INR: dict[str, float] = {
    "Excavator": 12_000.0,
    "Wheel Loader": 9_500.0,
    "Backhoe Loader": 6_500.0,
    "Telehandler": 7_000.0,
    "Compactor": 5_500.0,
}

# One-off charge to bring a machine onto a site from the dealer: float,
# unload, commissioning. Independent of distance.
MOBILISATION_INR = 18_000.0

# Moving a machine between two of your own sites. Low-bed haulage, priced by
# road distance, plus a fixed handling charge at each end.
TRANSPORT_INR_PER_KM = 95.0
TRANSPORT_HANDLING_INR = 12_000.0

# Road distance is longer than the straight line between two points. 1.35 is the
# usual planning factor for Indian state highways.
ROAD_CIRCUITY_FACTOR = 1.35

# What a day of waiting costs when a phase cannot start for want of a machine:
# idle crew, standing plant, extended preliminaries. This is the number that
# makes waiting expensive rather than free, and it is the single most
# consequential figure here — set it to zero and the allocator will always tell
# you to wait.
BLOCKED_DAY_INR = 22_000.0

# --------------------------------------------------------------------------
# Defect injection
# --------------------------------------------------------------------------
# Real rental records are dirty. If the synthetic history were spotless the
# anomaly detector would find nothing in 99% of the fleet and would look like a
# toy. These rates are small and declared here, not hidden in the generator.

# A machine that idles more than it works. This is NOT impossible and NOT a data
# error — it is severe under-utilisation, which is exactly what the anomaly
# detector should surface. Named as the condition, not as a defect.
RATE_IDLE_EXCEEDS_ENGINE = 0.025

# The day budget is blown: engine + idle claims more hours than a day has.
# Unlike the above this genuinely IS a bad record, and the detector should say
# so. Capped by MAX_DAY_HOURS_DEFECT so it stays implausible-but-arguable rather
# than absurd — a row claiming 40 idle hours in a 24-hour day is not a finding,
# it is a bug in the generator.
DEFECT_RATE_DAY_BUDGET = 0.015
MAX_DAY_HOURS_DEFECT = 26.5   # engine + idle ceiling on an injected bad row

# Stated contract days disagree with the check_in -> check_out span.
DEFECT_RATE_STATED_DAYS_MISMATCH = 0.020

# Paperwork gaps. A machine is on site but the rental record never got a site
# assigned, or never got an operator named against it. Both are ordinary
# real-world bookkeeping failures rather than sensor problems, and both are
# things a fleet manager genuinely wants flagged: an unassigned machine is one
# nobody is accountable for.
#
# They are written as blank cells, which is what the source data uses for a
# missing value. Downstream consumers must therefore tolerate a null site_id —
# phase.build_panel() and features.weekly_panel() drop these rows before
# grouping, because a site-less rental cannot belong to a site-week.
RATE_UNASSIGNED_SITE = 0.004
RATE_NO_OPERATOR = 0.004

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

SEED_CSV = "data/seed_assets.csv"
CACHE_DIR = "data/forecast_cache"

# Phase windows per site: the ground truth the phase models train on and are
# scored against. Written by the generator, consumed by phase.py and by the
# anomaly detector on the other side of the handoff.
SITE_PHASES_CSV = "data/site_phases.csv"

# Trained model artifacts. Two files, one per model — see artifacts.py.
MODELS_DIR = "models"
CLASSIFIER_ARTIFACT = "phase_classifier.pkl"
PHASE_END_ARTIFACT = "phase_end.pkl"

# Synthetic equipment ids start here so they can never collide with the
# supplied EQX1001..EQX1007 ground-truth rows.
SYNTHETIC_ID_BASE = 2000
