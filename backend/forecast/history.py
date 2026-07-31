"""Synthetic rental history generator (MOD-11, step 1).

The central design decision: **we generate rental events, not weekly numbers.**

    lambda(type, site, week) -> arrival process -> rental events
                                                        |
                                        weekly aggregation (features.py)
                                                        v
                                                  demand series

Generating events rather than a weekly squiggle buys three things:

1. Autocorrelation is real. A 25-day rental occupies four consecutive weeks of
   the fleet, so persistence emerges from the process instead of being an AR
   term bolted onto noise.
2. Durations, rates and engine/idle behaviour are drawn from distributions
   fitted to the 7 supplied rows (see calibration.py).
3. Every synthetic record is a complete ``Rental`` row per PRD section 10, so it
   also serves MOD-03 and MOD-07 rather than only MOD-11.

Three domain signals shape lambda, each a claim we can defend on a slide:

* **Site project phase** — excavators front-load a project, compactors finish
  it. Two sites at different phases want different machines the same week; this
  is the structure MOD-12 redeployment exploits.
* **Monsoon** — Jun-Sep earthmoving collapses on saturated ground, Oct-Dec
  surges as projects catch up.
* **Indian fiscal year** — Q4 budget flush, April collapse.

The forecaster never sees any of these parameters. It sees only the calendar and
the observed history (see features.py). That separation is asserted in the tests.
"""

from __future__ import annotations

import hashlib
import heapq
import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import calibration, clock_adapter, config, paths

RENTAL_COLUMNS = [
    "rental_id",
    "equipment_id",
    "type",
    "site_id",
    # check_in is the START of the rental contract window and check_out its END.
    # Settled by the supplied data: PRD section 3 gives EQX1003 as
    # 2025-02-15 -> 2025-03-11 = 24 days, so check_in is the earlier date (the
    # "hotel" reading, not the library one where you check an item out first).
    #
    # The window is the RENTAL, not the site assignment. EQX1002 and EQX1007
    # carry dates and 20 days of billing with a null Site ID — coherent only if
    # these dates bracket the contract rather than a stay at a site. That row is
    # pain #1 from the brief: on rent, paid for, never allocated to anyone.
    #
    # Consequence for MOD-11: a new rental row is a CALL-OFF to the dealer. An
    # internal transfer between the renter's own sites produces no row at all —
    # it is a custody event inside an existing rental (MOD-03).
    "check_in",
    "check_out",
    # The supplied `Rental Days` verbatim — the STATED contract figure. It is
    # deliberately not always equal to (check_out - check_in): that discrepancy
    # is the EQX1003 defect INT-01 exists to catch. The computed span is NOT
    # stored, because derived values are never persisted; INT-01 recomputes it
    # on read, which is the whole point of the rule.
    "rental_days",
    # The project phase the SITE was in when this machine was rented. Written
    # here because the generator knows it; read as a plain column by the phase
    # models and by the anomaly detector, which needs it to compare a machine
    # against same-type-same-phase peers rather than a global average. 20%
    # utilisation is unremarkable during erection and alarming during
    # excavation, and only the phase tells you which.
    "phase",
    # `Last Operator ID` from the supplied schema. Drawn from a per-site pool,
    # so operator churn on one machine is a signal rather than noise.
    "operator_id",
    "engine_hours_per_day",
    "idle_hours_per_day",
    # Required as outcomes by the brief, absent from the supplied schema
    # (PRD section 3). Simulated; every row here carries source="sim".
    "fuel_l_per_day",
    "lat",
    "lon",
    "is_ground_truth",
    "source",
]


# --------------------------------------------------------------------------
# Project schedules — when each site is in which phase
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class PhaseWindow:
    """One phase of one site, as a half-open span of history week indices."""

    site_id: str
    phase: str
    order: int
    start_week: int
    end_week: int              # exclusive

    @property
    def weeks(self) -> int:
        return self.end_week - self.start_week

    def contains(self, week_index: int) -> bool:
        return self.start_week <= week_index < self.end_week


@dataclass(frozen=True)
class Schedule:
    """A site's full phase plan, oldest first."""

    site_id: str
    windows: tuple[PhaseWindow, ...]

    @property
    def start_week(self) -> int:
        return self.windows[0].start_week

    @property
    def end_week(self) -> int:
        return self.windows[-1].end_week

    @property
    def total_weeks(self) -> int:
        return self.end_week - self.start_week

    def window_at(self, week_index: int) -> PhaseWindow | None:
        return next((w for w in self.windows if w.contains(week_index)), None)

    def progress_at(self, week_index: int) -> float:
        """Fraction of the whole project elapsed. Drives the equipment mix."""
        return (week_index - self.start_week) / self.total_weeks

    def is_active_at(self, week_index: int) -> bool:
        """Before groundbreaking a site is a plot of land; it rents nothing."""
        return self.start_week <= week_index < self.end_week


def build_schedule(site: config.Site, seed: int = config.MASTER_SEED,
                   weeks: int = config.HISTORY_WEEKS) -> Schedule:
    """Draw one site's phase durations and position it against ``now``.

    Two things happen here, and the order matters.

    **Durations slip.** Each phase runs ``base_weeks x site pace x lognormal
    noise``. Without that slip every site's excavation would last exactly 16
    weeks, "when does this phase end?" would be a lookup rather than a
    prediction, and the phase-end model would score perfectly while having
    learned nothing. The slip is the thing the model exists to see through.

    **The site is then positioned by its destination, not its origin.** Because
    the durations are random, a site's start week is not knowable in advance —
    so the config states which phase the site should be in at ``now`` and how
    far through it, and the start week is solved backwards from there. That is
    what keeps two sites in each of the six phases no matter how the draws land.
    """
    rng = np.random.default_rng([seed, 7_777, config.SITES.index(site)])

    durations: list[int] = []
    for phase in config.PHASES:
        slip = float(rng.lognormal(0.0, config.PHASE_SLIP_SIGMA))
        raw = phase.base_weeks * site.pace * slip
        durations.append(max(config.PHASE_MIN_WEEKS, int(round(raw))))

    target = config.PHASE_BY_NAME[site.phase_now].order - 1
    elapsed_at_now = (
        sum(durations[:target]) + site.phase_frac_now * durations[target]
    )
    start_week = int(round((weeks - 1) - elapsed_at_now))

    windows: list[PhaseWindow] = []
    cursor = start_week
    for phase, duration in zip(config.PHASES, durations):
        windows.append(PhaseWindow(
            site_id=site.site_id, phase=phase.name, order=phase.order,
            start_week=cursor, end_week=cursor + duration,
        ))
        cursor += duration

    return Schedule(site_id=site.site_id, windows=tuple(windows))


def build_schedules(seed: int = config.MASTER_SEED,
                    weeks: int = config.HISTORY_WEEKS) -> dict[str, Schedule]:
    """Every site's schedule. Deterministic for a given seed."""
    return {
        site.site_id: build_schedule(site, seed=seed, weeks=weeks)
        for site in config.SITES
    }


# --------------------------------------------------------------------------
# The demand intensity, lambda(site, type, week)
# --------------------------------------------------------------------------

def _phase_factor(progress: float, peak: float, width: float) -> float:
    """Gaussian bump over project progress, with a floor.

    Outside the project's life the site still trickles (mobilisation, snagging),
    hence the floor rather than a hard zero.
    """
    if progress < -0.15 or progress > 1.15:
        return 0.05
    bump = math.exp(-0.5 * ((progress - peak) / width) ** 2)
    return 0.08 + 0.92 * bump


def intensity(site: config.Site, etype: config.EquipmentType,
              week_index: int, week_start: date,
              schedule: Schedule | None = None) -> float:
    """Expected new rentals for one (site, type) in one week.

    Exposed for the deck and the tests — this *is* the data-generating process,
    and we publish it rather than hiding it.
    """
    schedule = schedule or build_schedule(site)
    progress = schedule.progress_at(week_index)
    phase = _phase_factor(progress, etype.peak_progress, etype.phase_width)

    month = week_start.month
    monsoon_raw = config.MONSOON_MULT[month]
    monsoon = 1.0 + etype.monsoon_sensitivity * (monsoon_raw - 1.0)
    fiscal = config.FISCAL_MULT[month]

    trend = math.exp(site.growth * (week_index / 52.0))
    sparse = config.SPARSE_CELLS.get((site.site_id, etype.name), 1.0)

    lam = (
        config.BASE_LAMBDA
        * site.scale
        * etype.share
        * phase
        * monsoon
        * fiscal
        * trend
        * sparse
    )
    return max(lam, 0.0)


def _cell_rng(seed: int, site_idx: int, type_idx: int) -> np.random.Generator:
    """Independent stream per cell.

    Seeding per cell rather than once globally means adding a site or reordering
    the type list does not perturb every other cell's draws — backtest numbers
    stay stable across the build.
    """
    return np.random.default_rng([seed, site_idx, type_idx])


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------

@dataclass
class _Arrival:
    check_in: date
    site_id: str
    type_name: str
    week_index: int
    progress: float            # the site's project progress at check_in
    phase: str                 # the phase the site was in
    weeks_left_in_phase: int   # from check_in to the end of that phase


def _draw_arrivals(seed: int, week_starts: list[date],
                   schedules: dict[str, Schedule]) -> list[_Arrival]:
    """Draw rental start events across every (site, type, week) cell."""
    arrivals: list[_Arrival] = []

    for s_idx, site in enumerate(config.SITES):
        schedule = schedules[site.site_id]

        for t_idx, etype in enumerate(config.EQUIPMENT_TYPES):
            rng = _cell_rng(seed, s_idx, t_idx)

            for w_idx, w_start in enumerate(week_starts):
                # Before groundbreaking and after handover a site rents nothing.
                if not schedule.is_active_at(w_idx):
                    continue

                lam = intensity(site, etype, w_idx, w_start, schedule)
                if lam <= 0:
                    continue

                # Gamma-Poisson mixture => negative binomial counts.
                # Demand is over-dispersed; pure Poisson is too well behaved.
                r = config.DISPERSION_R
                mixed = rng.gamma(shape=r, scale=lam / r)
                n = int(rng.poisson(mixed))
                if n == 0:
                    continue

                window = schedule.window_at(w_idx)
                progress = schedule.progress_at(w_idx)

                for _ in range(n):
                    offset = int(rng.integers(0, 7))
                    arrivals.append(
                        _Arrival(
                            check_in=w_start + timedelta(days=offset),
                            site_id=site.site_id,
                            type_name=etype.name,
                            week_index=w_idx,
                            progress=progress,
                            phase=window.phase,
                            weeks_left_in_phase=window.end_week - w_idx,
                        )
                    )

    arrivals.sort(key=lambda a: (a.check_in, a.site_id, a.type_name))
    return arrivals


def _draw_contract_days(rng: np.random.Generator, arrivals: list[_Arrival],
                        calib: calibration.Calibration) -> list[int]:
    """How long each machine is rented for — the *contract* clock.

    This is the hinge of the whole module. `check_in` -> `check_out` is when the
    rent runs; the phase is when the machine is actually needed. Two different
    people set those, so they do not line up, and each way of missing costs
    something different:

        rent expires BEFORE the phase ends  -> extend, or lose the machine
        phase ends BEFORE the rent expires  -> paid-for capacity sitting idle

    Drawing durations independently of phase — as this generator originally
    did — makes that gap pure noise, and an allocator built on noise finds
    nothing. So the contract is built in two steps:

    1. **Need.** A work package runs for a typical rental length (the lognormal
       fitted to the seed rows), but never past the end of the phase that
       justified it: ``need = min(typical, days_left_in_phase)``. That is what
       ties the two clocks together, and it is why rentals starting near a phase
       boundary come with short contracts.
    2. **Planning error.** The contract is that need scaled by
       ``N(CONTRACT_COVERAGE_MEAN, CONTRACT_COVERAGE_SD)``, so roughly half the
       contracts overshoot the need and half fall short.

    Keeping step 1 anchored on the calibrated lognormal means the overall
    duration distribution still matches the supplied rows; the phase only ever
    truncates it.
    """
    typical = rng.lognormal(
        calib.duration_log_mu, calib.duration_log_sigma, len(arrivals)
    )
    left = np.array([a.weeks_left_in_phase * 7.0 for a in arrivals])
    need = np.minimum(typical, np.maximum(left, config.CONTRACT_MIN_DAYS))

    coverage = rng.normal(
        config.CONTRACT_COVERAGE_MEAN, config.CONTRACT_COVERAGE_SD, len(arrivals)
    ).clip(0.35, 2.0)

    days = np.round(need * coverage)
    days = np.clip(days, config.CONTRACT_MIN_DAYS, config.CONTRACT_MAX_DAYS)
    return days.astype(int).tolist()


def _assign_equipment(arrivals: list[_Arrival], durations: list[int]) -> list[str]:
    """Allocate a physical machine to each rental, never double-booking one.

    The fleet is not capped: when nothing is free, a machine is added. Fleet size
    is therefore an *output* of demand rather than an input, which keeps the
    history internally consistent without having to model stockouts. (Censored
    demand — requests refused for want of stock — is deliberately out of scope;
    see README.)
    """
    pools: dict[str, list[tuple[date, str]]] = {}
    counter = config.SYNTHETIC_ID_BASE
    assigned: list[str] = []

    for arrival, days in zip(arrivals, durations):
        pool = pools.setdefault(arrival.type_name, [])
        if pool and pool[0][0] <= arrival.check_in:
            _, equipment_id = heapq.heappop(pool)
        else:
            counter += 1
            equipment_id = f"EQX{counter}"

        free_from = arrival.check_in + timedelta(
            days=days + config.TURNAROUND_DAYS
        )
        heapq.heappush(pool, (free_from, equipment_id))
        assigned.append(equipment_id)

    return assigned


def _draw_usage(rng: np.random.Generator, calib: calibration.Calibration,
                n: int) -> tuple[np.ndarray, np.ndarray]:
    """Engine and idle hours per day, with declared injections.

    Engine hours are working hours; idle hours are engine-on but not working.
    They are **disjoint**, so ``engine + idle`` is total engine-on time (the SMU
    the machine accrues) and the validity condition is simply
    ``engine + idle <= 24`` with each part non-negative.

    Two things are injected on top of the clean draw, and they are different in
    kind:

    * **Severe under-utilisation** (``idle > engine``). Not an error and not
      impossible — a machine that idles more than it works is a real and
      expensive situation, and surfacing it is the anomaly detector's job.
    * **A blown day budget** (``engine + idle > 24``). This one genuinely is a
      bad record. It is capped at ``MAX_DAY_HOURS_DEFECT`` so it stays
      implausible-but-arguable; a row claiming 40 idle hours in a 24-hour day
      is not a finding, it is a bug in the generator.
    """
    engine = rng.normal(calib.engine_hours_mean, calib.engine_hours_sd, n)
    engine = np.clip(engine, 0.5, 16.0)

    frac = rng.normal(calib.idle_fraction_mean, calib.idle_fraction_sd, n)
    frac = np.clip(frac, 0.02, 0.85)
    idle = engine * frac

    # Severe under-utilisation: the machine idles more than it works.
    flip = rng.random(n) < config.RATE_IDLE_EXCEEDS_ENGINE
    idle[flip] = engine[flip] * rng.uniform(1.4, 4.0, int(flip.sum()))

    # A bad record: the day budget is blown.
    blow = rng.random(n) < config.DEFECT_RATE_DAY_BUDGET
    engine[blow] = rng.uniform(13.0, 18.0, int(blow.sum()))
    idle[blow] = rng.uniform(7.0, 11.0, int(blow.sum()))

    # Nothing may claim more hours than the ceiling, injected or not. Scaling
    # both parts preserves the utilisation ratio the row was drawn with, so a
    # capped row still reads as the situation it was meant to represent.
    total = engine + idle
    over = total > config.MAX_DAY_HOURS_DEFECT
    if over.any():
        scale = config.MAX_DAY_HOURS_DEFECT / total[over]
        engine[over] *= scale
        idle[over] *= scale

    return np.round(engine, 2), np.round(idle, 2)


def _draw_operators(rng: np.random.Generator,
                    site_ids: list[str]) -> list[str]:
    """`Last Operator ID`, drawn from the operator pool of the machine's site.

    Operators belong to a site, not to a machine — which is what makes "this
    machine passed through four operators this month" a detectable signal
    instead of an artefact of random assignment.
    """
    pools = {
        site.site_id: [
            f"OP-{site.site_id}-{i:02d}"
            for i in range(1, config.OPERATORS_PER_SITE + 1)
        ]
        for site in config.SITES
    }
    return [
        pools[site_id][int(rng.integers(0, config.OPERATORS_PER_SITE))]
        for site_id in site_ids
    ]


def _draw_fuel(rng: np.random.Generator, engine: np.ndarray, idle: np.ndarray,
               type_names: list[str]) -> np.ndarray:
    """Litres per day, derived from the hours the machine actually ran.

    Not an independent random column. Fuel is a *function* of engine-on time and
    machine class, so it is computed from them:

        fuel = engine_h x burn_rate  +  idle_h x burn_rate x IDLE_FUEL_FRACTION

    Engine and idle hours are disjoint (the semantics are settled), so
    ``engine + idle`` is total engine-on time and each part burns at its own
    rate. An idling machine still consumes roughly a quarter of its working
    draw, which is precisely why idle hours cost money.

    Generating fuel independently would be the lazy version and would break the
    first correlation anyone plots. A +/-8% spread covers operator technique,
    load factor and terrain.
    """
    burn = np.array([
        {t.name: t.fuel_burn_l_per_h for t in config.EQUIPMENT_TYPES}[name]
        for name in type_names
    ])
    litres = burn * (engine + idle * config.IDLE_FUEL_FRACTION)
    return np.round(litres * rng.normal(1.0, 0.08, len(litres)).clip(0.75, 1.25), 1)


def _draw_geo(rng: np.random.Generator,
              site_ids: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Machine position, jittered around its site centroid.

    A machine sits somewhere on a site, not on its exact centre point. Jitter is
    uniform over roughly a 1 km box, which is a realistic site footprint and
    keeps the map legible when several machines share a site.
    """
    lat = np.empty(len(site_ids))
    lon = np.empty(len(site_ids))
    for i, site_id in enumerate(site_ids):
        site = config.SITE_BY_ID[site_id]
        lat[i] = site.lat + rng.uniform(-config.GEO_JITTER_DEG,
                                        config.GEO_JITTER_DEG)
        lon[i] = site.lon + rng.uniform(-config.GEO_JITTER_DEG,
                                        config.GEO_JITTER_DEG)
    return np.round(lat, 5), np.round(lon, 5)


def generate_history(
    seed: int = config.MASTER_SEED,
    now: date | None = None,
    weeks: int = config.HISTORY_WEEKS,
    calib: calibration.Calibration | None = None,
) -> pd.DataFrame:
    """Generate the full synthetic rental history.

    Returns one row per rental, sorted by ``check_in``. ``check_in`` is the
    rental start and ``check_out`` the return, matching the column order and the
    worked example in PRD section 3.

    Deterministic: identical ``seed``/``now``/``weeks`` yield an identical frame.
    """
    now = now or clock_adapter.now_date()
    calib = calib or calibration.load_calibration()

    current_week = clock_adapter.week_start(now)
    # History ends with the week *before* now: the current week is incomplete and
    # would otherwise read as a demand collapse in the final observation.
    last_full_week = current_week - timedelta(days=7)
    first_week = last_full_week - timedelta(days=7 * (weeks - 1))
    week_starts = [first_week + timedelta(days=7 * i) for i in range(weeks)]

    schedules = build_schedules(seed=seed, weeks=weeks)
    arrivals = _draw_arrivals(seed, week_starts, schedules)
    n = len(arrivals)
    if n == 0:
        return pd.DataFrame(columns=RENTAL_COLUMNS)

    # One stream for per-rental attributes, independent of the arrival streams.
    rng = np.random.default_rng([seed, 9_001])

    durations = _draw_contract_days(rng, arrivals, calib)

    equipment_ids = _assign_equipment(arrivals, durations)
    engine, idle = _draw_usage(rng, calib, n)

    type_names = [a.type_name for a in arrivals]
    site_ids = [a.site_id for a in arrivals]
    fuel = _draw_fuel(rng, engine, idle, type_names)
    lat, lon = _draw_geo(rng, site_ids)
    operators = _draw_operators(rng, site_ids)

    # INT-01 fodder: stated rental days disagrees with the date span, exactly the
    # defect present on EQX1003.
    stated = np.array(durations, dtype=int)
    mismatch = rng.random(n) < config.DEFECT_RATE_STATED_DAYS_MISMATCH
    stated[mismatch] += rng.choice([-1, 1], int(mismatch.sum()))

    frame = pd.DataFrame(
        {
            "rental_id": [f"RNT{i:06d}" for i in range(1, n + 1)],
            "equipment_id": equipment_ids,
            "type": type_names,
            "site_id": site_ids,
            "check_in": [a.check_in for a in arrivals],
            "check_out": [
                a.check_in + timedelta(days=int(d))
                for a, d in zip(arrivals, durations)
            ],
            "rental_days": stated,
            "phase": [a.phase for a in arrivals],
            "operator_id": operators,
            "engine_hours_per_day": engine,
            "idle_hours_per_day": idle,
            "fuel_l_per_day": fuel,
            "lat": lat,
            "lon": lon,
            "is_ground_truth": False,
            "source": "sim",
        }
    )[RENTAL_COLUMNS]

    _inject_paperwork_gaps(rng, frame)

    frame["check_in"] = pd.to_datetime(frame["check_in"])
    frame["check_out"] = pd.to_datetime(frame["check_out"])
    return frame.sort_values("check_in").reset_index(drop=True)


def _inject_paperwork_gaps(rng: np.random.Generator, frame: pd.DataFrame) -> None:
    """Blank out site and operator on a small share of rows, in place.

    Two ordinary bookkeeping failures, not sensor faults: a machine went out
    without a site recorded against it, or without a named operator. Both are
    conditions a fleet manager wants surfaced — an unassigned machine is one
    nobody is accountable for — and neither is inferable from the telemetry, so
    they have to be injected here rather than derived downstream.

    A row with no site has no phase either: the phase label comes from the
    site's schedule, so a record that never got a site cannot coherently claim
    to know which phase of which project it belonged to. Both columns go
    together. The operator gap is independent — those rows keep their site and
    phase and stay in the modelling panel.

    Drawn last so it cannot perturb any earlier draw's stream.
    """
    n = len(frame)

    unassigned = rng.random(n) < config.RATE_UNASSIGNED_SITE
    frame.loc[unassigned, "site_id"] = None
    frame.loc[unassigned, "phase"] = None

    no_operator = rng.random(n) < config.RATE_NO_OPERATOR
    frame.loc[no_operator, "operator_id"] = None


# --------------------------------------------------------------------------
# Phase windows — the ground truth the phase models train on
# --------------------------------------------------------------------------

SITE_PHASE_COLUMNS = [
    "site_id",
    "site_name",
    "phase",
    "phase_order",
    "start_date",
    "end_date",
    # False for the phase a site is *currently* in: its end has not happened
    # yet, so it has no observed end date. These are the rows the model has to
    # predict; the completed ones are what it learns from.
    "is_complete",
    # True when the phase was already under way at the start of the history, so
    # its measured duration is a lower bound rather than an observation. The
    # duration model must exclude these; the classifier may still use them.
    "start_censored",
    "duration_weeks",
]


def site_phase_windows(now: date | None = None,
                       weeks: int = config.HISTORY_WEEKS,
                       seed: int = config.MASTER_SEED) -> pd.DataFrame:
    """When each site entered and left each phase.

    Separating this from the rental table matters. A rental row carries the
    phase it *started* in, which is enough for peer comparison but too coarse to
    train against — phase boundaries would have to be guessed back out of rental
    clusters. These windows are the labels, and they are what makes the
    phase-end prediction falsifiable rather than merely plausible.

    Windows are clipped to the observed history: a phase that began before our
    records start is reported from the first week we can see, flagged by a start
    date equal to the window start. ``is_complete`` is False for the phase each
    site is in at ``now`` — that end has not happened yet, and pretending
    otherwise would leak the answer into the training set.
    """
    now = now or clock_adapter.now_date()
    current_week = clock_adapter.week_start(now)
    last_full_week = current_week - timedelta(days=7)
    first_week = last_full_week - timedelta(days=7 * (weeks - 1))

    now_index = weeks - 1
    schedules = build_schedules(seed=seed, weeks=weeks)

    rows: list[dict] = []
    for site in config.SITES:
        for window in schedules[site.site_id].windows:
            # Phases entirely outside the observed history are invisible to us
            # and must not appear in a file that claims to be observations.
            if window.end_week <= 0 or window.start_week > now_index:
                continue

            is_current = window.contains(now_index)
            # Truncated by an edge of the history rather than observed ending:
            # a phase already running when records began has an unknown true
            # start, so its measured duration is a lower bound. Flagged rather
            # than dropped — still valid for the classifier, which reads a
            # snapshot, and invalid only for the duration model.
            start_censored = window.start_week < 0
            visible_start = max(window.start_week, 0)

            rows.append({
                "site_id": site.site_id,
                "site_name": site.name,
                "phase": window.phase,
                "phase_order": window.order,
                "start_date": first_week + timedelta(days=7 * visible_start),
                "end_date": (None if is_current else
                             first_week + timedelta(days=7 * (window.end_week - 1))),
                "is_complete": not is_current,
                "start_censored": start_censored,
                "duration_weeks": (None if is_current or start_censored
                                   else window.weeks),
            })

    frame = pd.DataFrame(rows, columns=SITE_PHASE_COLUMNS)
    frame["start_date"] = pd.to_datetime(frame["start_date"])
    frame["end_date"] = pd.to_datetime(frame["end_date"])
    return frame


def write_site_phases(now: date | None = None,
                      weeks: int = config.HISTORY_WEEKS,
                      seed: int = config.MASTER_SEED) -> pd.DataFrame:
    """Persist the phase windows to ``data/site_phases.csv``.

    Written outside ``forecast_cache/`` on purpose: this file is a **handoff
    artefact**, consumed by the anomaly detector as well as by this module, and
    burying it in a cache directory keyed on a fingerprint hash would make it
    look disposable.
    """
    frame = site_phase_windows(now=now, weeks=weeks, seed=seed)
    frame.to_csv(paths.site_phases_csv(), index=False)
    return frame


# --------------------------------------------------------------------------
# Caching — NFR-1, the demo runs with the network off and must open instantly
# --------------------------------------------------------------------------

def dgp_fingerprint() -> str:
    """Short hash of every parameter that shapes the generated history.

    Part of the cache key. Without it, tuning a multiplier in ``config.py`` would
    silently reload stale data and you would spend an hour wondering why the
    numbers never move — an expensive way to lose time during a 24-hour build.
    """
    payload = repr((
        config.BASE_LAMBDA,
        config.DISPERSION_R,
        config.TURNAROUND_DAYS,
        config.EQUIPMENT_TYPES,
        config.SITES,
        config.PHASES,
        config.PHASE_SLIP_SIGMA,
        config.PHASE_MIN_WEEKS,
        config.HISTORY_WEEKS,
        config.OPERATORS_PER_SITE,
        config.CONTRACT_COVERAGE_MEAN,
        config.CONTRACT_COVERAGE_SD,
        config.CONTRACT_MIN_DAYS,
        config.CONTRACT_MAX_DAYS,
        sorted(config.SPARSE_CELLS.items()),
        sorted(config.MONSOON_MULT.items()),
        sorted(config.FISCAL_MULT.items()),
        config.RATE_IDLE_EXCEEDS_ENGINE,
        config.DEFECT_RATE_DAY_BUDGET,
        config.MAX_DAY_HOURS_DEFECT,
        config.DEFECT_RATE_STATED_DAYS_MISMATCH,
        config.RATE_UNASSIGNED_SITE,
        config.RATE_NO_OPERATOR,
    ))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]


def cached_history(
    seed: int = config.MASTER_SEED,
    now: date | None = None,
    weeks: int = config.HISTORY_WEEKS,
    refresh: bool = False,
) -> pd.DataFrame:
    """Generate once, then reload from ``data/forecast_cache/``."""
    now = now or clock_adapter.now_date()
    path = paths.cache_dir() / (
        f"rental_history_{seed}_{now.isoformat()}_{weeks}_"
        f"{dgp_fingerprint()}.csv"
    )

    if path.exists() and not refresh:
        frame = pd.read_csv(path, parse_dates=["check_in", "check_out"])
    else:
        frame = generate_history(seed=seed, now=now, weeks=weeks)
        frame.to_csv(path, index=False)

    # Cheap and derived purely from config, so it is rewritten either way —
    # otherwise a cache hit would leave a stale handoff file on disk.
    write_site_phases(now=now, weeks=weeks, seed=seed)
    return frame
