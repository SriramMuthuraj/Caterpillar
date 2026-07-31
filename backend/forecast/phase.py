"""Phase engine — what phase is this site in, and when does it end?

Two models, both XGBoost, answering the only two genuinely uncertain questions
in the module:

1. **Which phase is this site in?** ``PhaseClassifier`` — multi-class over the
   six phases, reading nothing but the equipment on the ground.
2. **When does that phase end?** ``PhaseEndModel`` — quantile regression on
   weeks remaining, so the answer is a range rather than a false point.

Everything else the allocator needs (what the *next* phase requires) is a lookup
table measured from history, not a model. Training a learner to memorise six
rows would invite exactly the question we do not want asked.

---

**Why a classifier at all, when the generator writes the phase down?**

Because "we know what phase your site is in" has to be a capability, not a
column read. The generated `phase` column exists so the pipeline runs end to end
from minute one and so the anomaly detector is never blocked. But if the only
answer to *"how would this work on real data?"* is "our own simulator told us",
the claim collapses. So the classifier is trained to recover the label from the
equipment mix alone — the same signal a real deployment would have — and its
held-out accuracy is published alongside every prediction.

**Why the phase-end model is the hard one.** Phase durations slip per site
(``config.PHASE_SLIP_SIGMA``): a nominally 16-week excavation runs anywhere from
9 to 24 weeks. That spread is the thing being predicted. Without it the answer
would be a lookup of ``base_weeks`` and a perfect score would mean nothing.

---

**The leakage rule.** Neither model may see anything only the generator knows —
not ``config.Site.pace``, not the drawn durations, not the true phase boundary.
Features come from the rental records and the calendar, which is what a real
deployment would have. ``tests/test_phase.py`` asserts it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRegressor

from . import clock_adapter, config

# --------------------------------------------------------------------------
# Features
# --------------------------------------------------------------------------

def _slug(name: str) -> str:
    return name.lower().replace(" ", "_")


# The equipment mix — the share of machines *standing on site* of each type.
# Excavators dominate early and all but vanish by demobilisation; compactors do
# the reverse.
MIX_COLUMNS = [f"share_{_slug(t.name)}" for t in config.EQUIPMENT_TYPES]

# The mix of machines *newly arriving*, over a longer window.
#
# This is the sharper of the two signals and the reason both exist. Machines on
# site is a stock: a 25-day excavator rental taken out in week 2 of excavation is
# still standing there in week 5 of foundation, so the standing mix lags the
# phase by roughly a rental length and smears every boundary. Arrivals are a
# flow — what the site is calling off *now* — and they turn a phase change from
# a slow drift into a step.
ARRIVAL_MIX_COLUMNS = [f"arrivals_{_slug(t.name)}"
                       for t in config.EQUIPMENT_TYPES]

# Everything a site foreman could tell you by looking around.
CONTEXT_COLUMNS = [
    "machines_on_site",
    "starts_this_week",
    "mean_engine_hours",
    "mean_idle_hours",
    "utilisation",
    "distinct_operators",
    # How long this site has been running. Legitimately observable — a real
    # deployment knows when it broke ground — and strongly informative, since
    # phases run in a fixed order. It is not leakage: it says nothing about how
    # long *this* phase was drawn to last, which is what slips.
    "site_age_weeks",
]

CLASSIFIER_FEATURES = MIX_COLUMNS + ARRIVAL_MIX_COLUMNS + CONTEXT_COLUMNS

# The duration model additionally knows how long the phase has already run, how
# the mix is drifting, and — the feature that actually earns its keep — how far
# behind or ahead of plan this particular site has run so far.
DURATION_EXTRA_COLUMNS = [
    "weeks_elapsed_in_phase",
    "phase_order",
    "mix_drift_4w",
    "machines_trend_4w",
    "site_weeks_observed",
    # The planned length of this phase. Not an outcome — it is the schedule the
    # contractor drew up, which any real deployment has in hand.
    "phase_planned_weeks",
    "weeks_elapsed_vs_planned",
    # THE feature. Ratio of actual to planned duration across the phases this
    # site has ALREADY finished. A site running 20% long on clearing, excavation
    # and foundation will run long on erection too — that is what "this project
    # is slipping" means, and it is the only observable that carries the slip.
    # Without it the model has nothing the flat baseline lacks, and duly loses
    # to it.
    "site_pace_observed",
    "site_phases_completed",
    # planned x observed pace — the estimate a planner would make on the back of
    # an envelope. Handed over explicitly because trees approximate products
    # with a staircase of splits, and on ~400 rows that costs more than it is
    # worth. The model still has to decide how far to trust it against the mix
    # and trend features.
    "planned_x_pace",
]

DURATION_FEATURES = CLASSIFIER_FEATURES + DURATION_EXTRA_COLUMNS

# Rolling window over which the standing equipment mix is measured.
MIX_WINDOW_WEEKS = 4

# Rolling window for the arrival mix. Longer, because arrivals are counts and a
# single week at one site yields only a handful — too few to form a stable share.
# Eight weeks is a compromise: enough machines to make the proportions mean
# something, short enough to stay inside one phase.
ARRIVAL_WINDOW_WEEKS = 8

# A phase needs at least this many completed observations before the duration
# model will speak about it. Below that it returns `insufficient_data` — the
# refusal is a feature, not a gap.
MIN_COMPLETED_PHASES = 4

# Quantiles the duration model is fitted at. The outer pair is the reported
# range; the middle one is the headline.
QUANTILES = (0.10, 0.50, 0.90)
INTERVAL_LEVEL = 0.80


def _conformal_pad(truth: np.ndarray, low: np.ndarray, high: np.ndarray,
                   level: float) -> float:
    """How much to widen the quantile band so it covers what it claims.

    Quantile regression fits its quantiles on the *training* data, and on a few
    hundred rows the fitted P10/P90 sit far too close to the median — measured
    out of fold, a nominal 80% band was covering about 37%. Shipping that as an
    "80% interval" would be a straightforward falsehood, and a band that narrow
    is worse than none, because the allocator downstream sizes its slack on it.

    This is conformalized quantile regression (Romano, Patterson & Candès 2019):
    take the out-of-fold conformity scores — how far outside its own band each
    truth fell, negative when comfortably inside — and widen every band by their
    (1 - alpha) quantile. Coverage then holds by construction rather than by
    assumption, at the cost of a single symmetric constant.

    The finite-sample correction ``ceil((n + 1) * level) / n`` is what makes the
    guarantee valid on a sample this small rather than merely asymptotic.
    """
    if len(truth) == 0:
        return 0.0

    scores = np.maximum(low - truth, truth - high)
    n = len(scores)
    rank = min(int(np.ceil((n + 1) * level)), n)
    pad = float(np.sort(scores)[rank - 1])
    return max(pad, 0.0)


def _machines_on_site(rentals: pd.DataFrame, site_id: str,
                      week_start: date) -> pd.DataFrame:
    """Rentals live at a site during a given week.

    "Live" means the contract brackets the week: rented on or before it, not yet
    expired. That is the fleet a foreman would see standing on the ground.
    """
    week_end = week_start + timedelta(days=6)
    mask = (
        (rentals["site_id"] == site_id)
        & (rentals["check_in"] <= pd.Timestamp(week_end))
        & (rentals["check_out"] >= pd.Timestamp(week_start))
    )
    return rentals.loc[mask]


def _arrivals_between(rentals: pd.DataFrame, site_id: str,
                      first_week: date, last_week: date) -> pd.DataFrame:
    """Rentals *commencing* at a site within a span of weeks."""
    mask = (
        (rentals["site_id"] == site_id)
        & (rentals["check_in"] >= pd.Timestamp(first_week))
        & (rentals["check_in"] <= pd.Timestamp(last_week + timedelta(days=6)))
    )
    return rentals.loc[mask]


def site_week_features(rentals: pd.DataFrame, site_id: str,
                       week_start: date,
                       site_first_week: date | None = None) -> dict[str, float]:
    """One observation: what the site looked like in one week.

    Deliberately shared by training and prediction. A mismatch between the
    features a model was fitted on and the ones it scores is the classic silent
    failure, and the only reliable defence is to build both from one function.
    """
    window_start = week_start - timedelta(days=7 * (MIX_WINDOW_WEEKS - 1))
    weeks = [window_start + timedelta(days=7 * i)
             for i in range(MIX_WINDOW_WEEKS)]

    frames = [_machines_on_site(rentals, site_id, w) for w in weeks]
    window = pd.concat(frames) if frames else rentals.iloc[:0]
    current = frames[-1]

    row: dict[str, float] = {}

    # Equipment mix over the window, as shares that sum to 1.
    total = float(len(window))
    for etype, column in zip(config.EQUIPMENT_TYPES, MIX_COLUMNS):
        count = float((window["type"] == etype.name).sum())
        row[column] = count / total if total else 0.0

    # Arrival mix: what the site is calling off now, not what is standing there.
    arrival_start = week_start - timedelta(days=7 * (ARRIVAL_WINDOW_WEEKS - 1))
    arrivals = _arrivals_between(rentals, site_id, arrival_start, week_start)
    n_arrivals = float(len(arrivals))
    for etype, column in zip(config.EQUIPMENT_TYPES, ARRIVAL_MIX_COLUMNS):
        count = float((arrivals["type"] == etype.name).sum())
        row[column] = count / n_arrivals if n_arrivals else 0.0

    row["machines_on_site"] = float(len(current))
    row["starts_this_week"] = float(
        (current["check_in"] >= pd.Timestamp(week_start)).sum()
    )
    row["site_age_weeks"] = (
        float((week_start - site_first_week).days // 7)
        if site_first_week is not None else 0.0
    )

    if len(current):
        engine = float(current["engine_hours_per_day"].mean())
        idle = float(current["idle_hours_per_day"].mean())
        row["mean_engine_hours"] = engine
        row["mean_idle_hours"] = idle
        # Engine and idle hours are disjoint, so engine-on time is their sum and
        # utilisation is the working share of it.
        row["utilisation"] = engine / (engine + idle) if engine + idle else 0.0
        row["distinct_operators"] = float(current["operator_id"].nunique())
    else:
        row["mean_engine_hours"] = 0.0
        row["mean_idle_hours"] = 0.0
        row["utilisation"] = 0.0
        row["distinct_operators"] = 0.0

    return row


def _mix_vector(row: dict[str, float]) -> np.ndarray:
    return np.array([row[c] for c in MIX_COLUMNS], dtype=float)


def build_panel(rentals: pd.DataFrame, site_phases: pd.DataFrame,
                now: date | None = None) -> pd.DataFrame:
    """One row per (site, week) that the site was live, with its true phase.

    **This is the answer to the data-size problem.** There are only ~30 completed
    phase windows in the history, and 30 rows will not train anything. But a
    phase is not one observation — it is one observation *per week it ran*:
    "given four weeks elapsed and this equipment on the ground, how many weeks
    remain?" That turns ~30 windows into ~500 rows without inventing data.

    The cost is that rows within a window are near-duplicates, which is why
    every split downstream is **by phase window, never by row**. A random split
    would put week 3 of a phase in train and week 4 in test, score beautifully,
    and mean nothing.
    """
    now = now or clock_adapter.now_date()
    rentals = rentals.copy()

    # A small share of rows carry no site (config.RATE_UNASSIGNED_SITE) — a
    # paperwork gap the anomaly detector is meant to catch. They cannot belong
    # to a site-week, so they are dropped here rather than forming a phantom
    # group keyed on NaN.
    rentals = rentals.dropna(subset=["site_id"])

    rentals["check_in"] = pd.to_datetime(rentals["check_in"])
    rentals["check_out"] = pd.to_datetime(rentals["check_out"])

    windows = site_phases.copy()
    windows["start_date"] = pd.to_datetime(windows["start_date"])
    windows["end_date"] = pd.to_datetime(windows["end_date"])

    # When each site first appears in the records. Observable to anyone holding
    # the rental history — no schedule required.
    site_first_week = {
        str(site_id): clock_adapter.week_start(first.date())
        for site_id, first in rentals.groupby("site_id")["check_in"].min().items()
    }

    rows: list[dict] = []
    for window in windows.itertuples(index=False):
        start = window.start_date.date()
        # An in-progress phase has no observed end; its rows are still useful to
        # the classifier (the phase label is known) but carry no duration target.
        end = (window.end_date.date() if window.is_complete
               else clock_adapter.week_start(now))

        week = clock_adapter.week_start(start)
        elapsed = 0
        while week <= end:
            feats = site_week_features(
                rentals, window.site_id, week,
                site_first_week.get(window.site_id),
            )
            feats.update({
                "site_id": window.site_id,
                "week_start": pd.Timestamp(week),
                "phase": window.phase,
                "phase_order": float(window.phase_order),
                "window_id": f"{window.site_id}|{window.phase}",
                "weeks_elapsed_in_phase": float(elapsed),
                "is_complete": bool(window.is_complete),
                "start_censored": bool(window.start_censored),
                # THE TARGET: the phase's total length.
                #
                # Not "weeks remaining", which is what the caller ultimately
                # wants. Remaining = total - elapsed, and elapsed is a known
                # input, so a model asked for remaining has to learn a straight
                # subtraction — which gradient-boosted trees are bad at, because
                # they approximate a smooth linear relationship with a staircase
                # of splits. Predicting the total (roughly constant across a
                # window) and subtracting the elapsed weeks ourselves puts the
                # arithmetic where arithmetic belongs and leaves the model the
                # part that actually needs learning.
                "phase_total_weeks": (
                    float(window.duration_weeks)
                    if window.is_complete and not window.start_censored
                    and pd.notna(window.duration_weeks) else math.nan
                ),
                "weeks_remaining": (
                    float((end - week).days // 7) if window.is_complete
                    else math.nan
                ),
            })
            rows.append(feats)
            week += timedelta(days=7)
            elapsed += 1

    panel = pd.DataFrame(rows)
    if panel.empty:
        return panel

    panel = panel.sort_values(["site_id", "week_start"]).reset_index(drop=True)
    panel = _add_trend_features(panel)
    return _add_pace_features(panel, windows)


def _add_pace_features(panel: pd.DataFrame,
                       windows: pd.DataFrame) -> pd.DataFrame:
    """How far behind plan each site has run, using only its finished phases.

    The leakage risk here is sharp and worth stating. "This site runs 20% long"
    is only a legitimate feature if it is computed from phases that had already
    **finished** when the row being described was observed. Include the current
    phase's own outcome and the model is reading the answer off the label; the
    score would look excellent and the thing would be worthless in front of a
    site that has not finished yet.

    So the ratio is built strictly from windows whose ``end_date`` precedes the
    current window's ``start_date``. A site's first phase therefore has no track
    record and falls back to 1.0 — on plan until proven otherwise.
    """
    planned = {p.name: float(p.base_weeks) for p in config.PHASES}

    finished = windows[
        windows["is_complete"] & ~windows["start_censored"]
    ].copy()
    finished["ratio"] = finished.apply(
        lambda w: (w["duration_weeks"] / planned[w["phase"]]
                   if planned.get(w["phase"]) else np.nan),
        axis=1,
    )

    history_by_site: dict[str, list[tuple[pd.Timestamp, float]]] = {}
    for row in finished.itertuples(index=False):
        if not np.isnan(row.ratio):
            history_by_site.setdefault(row.site_id, []).append(
                (row.end_date, float(row.ratio))
            )

    paces: list[float] = []
    counts: list[float] = []
    for row in panel.itertuples(index=False):
        prior = [
            ratio for ended, ratio in history_by_site.get(row.site_id, [])
            if pd.notna(ended) and ended < row.week_start
        ]
        paces.append(float(np.mean(prior)) if prior else 1.0)
        counts.append(float(len(prior)))

    panel = panel.copy()
    panel["site_pace_observed"] = paces
    panel["site_phases_completed"] = counts
    panel["phase_planned_weeks"] = panel["phase"].map(planned).astype(float)
    panel["weeks_elapsed_vs_planned"] = (
        panel["weeks_elapsed_in_phase"] / panel["phase_planned_weeks"]
    )
    panel["planned_x_pace"] = (
        panel["phase_planned_weeks"] * panel["site_pace_observed"]
    )
    return panel


def _add_trend_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Rate-of-change features, computed within a site's own timeline.

    A phase is identifiable from a snapshot, but its *ending* shows up as
    movement: the mix drifting toward the next phase's profile, the machine
    count rolling off. Both are computed against the site's own past, never
    across sites, and never forward in time.
    """
    out: list[pd.DataFrame] = []
    for _, group in panel.groupby("site_id", sort=False):
        group = group.sort_values("week_start").copy()

        mix = group[MIX_COLUMNS].to_numpy(dtype=float)
        drift = np.zeros(len(group))
        if len(group) > MIX_WINDOW_WEEKS:
            lagged = np.roll(mix, MIX_WINDOW_WEEKS, axis=0)
            lagged[:MIX_WINDOW_WEEKS] = mix[:MIX_WINDOW_WEEKS]
            drift = np.abs(mix - lagged).sum(axis=1)
        group["mix_drift_4w"] = drift

        machines = group["machines_on_site"].astype(float)
        group["machines_trend_4w"] = (
            machines - machines.shift(MIX_WINDOW_WEEKS)
        ).fillna(0.0)

        group["site_weeks_observed"] = np.arange(len(group), dtype=float)
        out.append(group)

    return pd.concat(out).sort_values(
        ["site_id", "week_start"]
    ).reset_index(drop=True)


# --------------------------------------------------------------------------
# Model 1 — which phase is this site in?
# --------------------------------------------------------------------------

@dataclass
class ClassifierReport:
    """How well the classifier recovers a phase it was not shown."""

    accuracy: float
    n_train: int
    n_test: int
    n_test_windows: int
    within_one_phase: float           # off-by-one counts as near, not wrong
    per_phase_accuracy: dict[str, float] = field(default_factory=dict)
    confusion: dict[str, dict[str, int]] = field(default_factory=dict)
    feature_importance: dict[str, float] = field(default_factory=dict)

    def summary(self) -> dict:
        return {
            "accuracy": round(self.accuracy, 3),
            "within_one_phase": round(self.within_one_phase, 3),
            "n_train_rows": self.n_train,
            "n_test_rows": self.n_test,
            "n_test_windows": self.n_test_windows,
            "per_phase_accuracy": {
                k: round(v, 3) for k, v in self.per_phase_accuracy.items()
            },
            "confusion": self.confusion,
            "feature_importance": {
                k: round(v, 4) for k, v in self.feature_importance.items()
            },
            "method": (
                "held out whole phase windows, never individual weeks — a "
                "random row split would put adjacent weeks of the same phase "
                "on both sides and score meaninglessly high"
            ),
        }


class PhaseClassifier:
    """Recovers the project phase from the equipment standing on the ground."""

    def __init__(self) -> None:
        self.model: XGBClassifier | None = None
        self.report: ClassifierReport | None = None
        self._labels = list(config.PHASE_NAMES)

    # -- artifact interface (see artifacts.py) -----------------------------

    @property
    def feature_columns(self) -> list[str]:
        return list(CLASSIFIER_FEATURES)

    @property
    def labels(self) -> list[str]:
        return list(self._labels)

    @classmethod
    def restore(cls, bundle: dict) -> "PhaseClassifier":
        """Rebuild from a saved bundle. The bundle is already validated."""
        obj = cls()
        obj.model = bundle["model"]
        obj._labels = list(bundle["classes_"])
        scores = bundle.get("scores")
        obj.report = ClassifierReport(**scores) if scores else None
        return obj

    def _new_model(self) -> XGBClassifier:
        # Shallow and small on purpose: ~1,000 rows and 11 features. Deeper
        # trees memorise individual site-weeks and the held-out score collapses.
        return XGBClassifier(
            n_estimators=220,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            min_child_weight=4,
            objective="multi:softprob",
            num_class=len(self._labels),
            tree_method="hist",
            n_jobs=1,             # single-threaded: determinism over speed
            random_state=config.MASTER_SEED,
            verbosity=0,
        )

    def fit(self, panel: pd.DataFrame) -> "PhaseClassifier":
        usable = panel.dropna(subset=CLASSIFIER_FEATURES)
        if usable.empty:
            raise ValueError("no usable rows to fit the phase classifier")

        self.report = self._evaluate(usable)

        # Refit on everything for the model that actually answers queries — the
        # out-of-fold score above is the honest estimate of how it will do.
        self.model = self._new_model()
        self.model.fit(
            usable[CLASSIFIER_FEATURES].to_numpy(dtype=float),
            self._encode(usable["phase"]),
        )
        if self.report is not None:
            self.report.feature_importance = self._importance(self.model)
        return self

    def _encode(self, phases: pd.Series) -> np.ndarray:
        index = {name: i for i, name in enumerate(self._labels)}
        return phases.map(index).to_numpy(dtype=int)

    def _importance(self, model: XGBClassifier) -> dict[str, float]:
        scores = model.feature_importances_
        pairs = sorted(
            zip(CLASSIFIER_FEATURES, (float(s) for s in scores)),
            key=lambda kv: kv[1], reverse=True,
        )
        return dict(pairs)

    def _evaluate(self, usable: pd.DataFrame) -> ClassifierReport | None:
        folds = window_folds(usable)
        if not folds:
            return None

        predicted: list[str] = []
        truth: list[str] = []
        n_train = 0
        for train, test in folds:
            if train.empty or test.empty:
                continue
            model = self._new_model()
            model.fit(
                train[CLASSIFIER_FEATURES].to_numpy(dtype=float),
                self._encode(train["phase"]),
            )
            predicted.extend(
                self._labels[i] for i in
                model.predict(test[CLASSIFIER_FEATURES].to_numpy(dtype=float))
            )
            truth.extend(test["phase"])
            n_train = len(train)

        if not truth:
            return None

        correct = sum(p == t for p, t in zip(predicted, truth))
        order = {name: config.PHASE_BY_NAME[name].order for name in self._labels}
        near = sum(abs(order[p] - order[t]) <= 1 for p, t in zip(predicted, truth))

        per_phase: dict[str, float] = {}
        confusion: dict[str, dict[str, int]] = {}
        for name in self._labels:
            rows = [(p, t) for p, t in zip(predicted, truth) if t == name]
            if rows:
                per_phase[name] = sum(p == t for p, t in rows) / len(rows)
            counts: dict[str, int] = {}
            for p, t in rows:
                counts[p] = counts.get(p, 0) + 1
            if counts:
                confusion[name] = counts

        n = len(truth) or 1
        return ClassifierReport(
            accuracy=correct / n,
            n_train=n_train,
            n_test=len(truth),
            n_test_windows=int(usable["window_id"].nunique()),
            within_one_phase=near / n,
            per_phase_accuracy=per_phase,
            confusion=confusion,
        )

    def predict(self, features: dict[str, float]) -> tuple[str, float]:
        """Most likely phase and the probability assigned to it."""
        if self.model is None:
            raise RuntimeError("PhaseClassifier.predict called before fit")
        row = np.array([[features[c] for c in CLASSIFIER_FEATURES]], dtype=float)
        probabilities = self.model.predict_proba(row)[0]
        best = int(np.argmax(probabilities))
        return self._labels[best], float(probabilities[best])


# --------------------------------------------------------------------------
# Model 2 — when does this phase end?
# --------------------------------------------------------------------------

@dataclass
class DurationReport:
    """Held-out error of the weeks-remaining model, in weeks."""

    mae_weeks: float
    baseline_mae_weeks: float
    n_train: int
    n_test: int
    n_test_windows: int
    coverage: float                   # after conformal widening
    raw_coverage: float = 0.0         # what the fitted quantiles alone achieved
    interval_pad_weeks: float = 0.0
    mae_by_phase: dict[str, float] = field(default_factory=dict)
    feature_importance: dict[str, float] = field(default_factory=dict)

    @property
    def skill(self) -> float:
        """Fractional improvement over the baseline. Negative means worse."""
        if not self.baseline_mae_weeks:
            return 0.0
        return 1.0 - (self.mae_weeks / self.baseline_mae_weeks)

    def summary(self) -> dict:
        return {
            "mae_weeks": round(self.mae_weeks, 2),
            "baseline_mae_weeks": round(self.baseline_mae_weeks, 2),
            "skill_vs_baseline": round(self.skill, 3),
            "interval_coverage": round(self.coverage, 3),
            "interval_level": INTERVAL_LEVEL,
            "interval_coverage_before_calibration": round(self.raw_coverage, 3),
            "interval_pad_weeks": round(self.interval_pad_weeks, 2),
            "interval_method": (
                "conformalized quantile regression — the fitted P10/P90 covered "
                f"only {self.raw_coverage:.0%} out of fold, so every band is "
                f"widened by {self.interval_pad_weeks:.1f} weeks, calibrated on "
                "out-of-fold conformity scores"
            ),
            "n_train_rows": self.n_train,
            "n_test_rows": self.n_test,
            "n_test_windows": self.n_test_windows,
            "mae_by_phase": {
                k: round(v, 2) for k, v in self.mae_by_phase.items()
            },
            "feature_importance": {
                k: round(v, 4) for k, v in self.feature_importance.items()
            },
            "baseline": (
                "mean observed duration of this phase, minus weeks elapsed — "
                "what you would predict from a schedule alone"
            ),
        }


class PhaseEndModel:
    """Weeks remaining in the current phase, as a range.

    Three quantile regressors (P10 / P50 / P90) rather than one point model.
    Reporting "excavation ends in 4 weeks" as a bare number claims a precision
    nobody has; "4 weeks, likely 3 to 7" is the same information told honestly,
    and the allocator downstream needs the width to decide how much slack to
    leave.
    """

    def __init__(self) -> None:
        self.models: dict[float, XGBRegressor] = {}
        self.report: DurationReport | None = None
        self.mean_duration: dict[str, float] = {}
        self.trainable_phases: set[str] = set()
        # Conformal padding, in weeks — see `_conformal_pad`.
        self.interval_pad: float = 0.0

    # -- artifact interface (see artifacts.py) -----------------------------

    @property
    def feature_columns(self) -> list[str]:
        return list(DURATION_FEATURES)

    @classmethod
    def restore(cls, bundle: dict) -> "PhaseEndModel":
        """Rebuild from a saved bundle. The bundle is already validated."""
        obj = cls()
        obj.models = dict(bundle["models"])
        obj.interval_pad = float(bundle["interval_pad"])
        obj.mean_duration = dict(bundle.get("mean_duration") or {})
        obj.trainable_phases = set(bundle["trainable_phases"])
        scores = bundle.get("scores")
        obj.report = DurationReport(**scores) if scores else None
        return obj

    def _new_model(self, quantile: float) -> XGBRegressor:
        return XGBRegressor(
            objective="reg:quantileerror",
            quantile_alpha=quantile,
            n_estimators=260,
            max_depth=3,
            learning_rate=0.07,
            subsample=0.9,
            colsample_bytree=0.9,
            min_child_weight=5,
            tree_method="hist",
            n_jobs=1,
            random_state=config.MASTER_SEED,
            verbosity=0,
        )

    def fit(self, panel: pd.DataFrame,
            site_phases: pd.DataFrame) -> "PhaseEndModel":
        # Only windows whose end we actually watched happen. In-progress phases
        # have no target, and start-censored ones have a duration that is a
        # lower bound rather than an observation — training on either teaches
        # the model that phases are shorter than they are.
        usable = panel[
            panel["is_complete"]
            & ~panel["start_censored"]
            & panel["phase_total_weeks"].notna()
        ].dropna(subset=DURATION_FEATURES)

        self._fit_baseline(site_phases)

        if usable.empty:
            return self

        self.report = self._evaluate(usable)

        for quantile in QUANTILES:
            model = self._new_model(quantile)
            model.fit(
                usable[DURATION_FEATURES].to_numpy(dtype=float),
                usable["phase_total_weeks"].to_numpy(dtype=float),
            )
            self.models[quantile] = model

        if self.report is not None and 0.50 in self.models:
            scores = self.models[0.50].feature_importances_
            self.report.feature_importance = dict(sorted(
                zip(DURATION_FEATURES, (float(s) for s in scores)),
                key=lambda kv: kv[1], reverse=True,
            ))
        return self

    def _fit_baseline(self, site_phases: pd.DataFrame) -> None:
        """Mean observed duration per phase — the bar the model must clear.

        Also decides which phases the model is allowed to speak about at all.
        A phase with two completed observations has no basis for a prediction,
        and saying so is better than producing a number.
        """
        completed = site_phases[
            site_phases["is_complete"] & ~site_phases["start_censored"]
        ]
        for name, group in completed.groupby("phase"):
            durations = group["duration_weeks"].dropna()
            if len(durations):
                self.mean_duration[str(name)] = float(durations.mean())
            if len(durations) >= MIN_COMPLETED_PHASES:
                self.trainable_phases.add(str(name))

    def _baseline_predict(self, frame: pd.DataFrame) -> np.ndarray:
        """What a schedule alone would tell you: typical length minus elapsed."""
        typical = frame["phase"].map(self.mean_duration).astype(float)
        overall = (np.mean(list(self.mean_duration.values()))
                   if self.mean_duration else 0.0)
        typical = typical.fillna(overall)
        return np.clip(typical - frame["weeks_elapsed_in_phase"], 0.0, None)

    def _evaluate(self, usable: pd.DataFrame) -> DurationReport | None:
        """Out-of-fold error, folded over whole phase windows."""
        folds = window_folds(usable)
        if not folds:
            return None

        pieces: list[pd.DataFrame] = []
        n_train = 0
        for train, test in folds:
            if train.empty or test.empty:
                continue
            fitted = {}
            for quantile in QUANTILES:
                model = self._new_model(quantile)
                model.fit(
                    train[DURATION_FEATURES].to_numpy(dtype=float),
                    train["phase_total_weeks"].to_numpy(dtype=float),
                )
                fitted[quantile] = model

            design = test[DURATION_FEATURES].to_numpy(dtype=float)
            elapsed = test["weeks_elapsed_in_phase"].to_numpy(dtype=float)
            out = test[["phase", "window_id", "weeks_remaining"]].copy()
            # Predict the total, then subtract what has already elapsed. Scored
            # on weeks remaining so the number in the report is the number the
            # user sees.
            for name, quantile in (("median", 0.50), ("low", 0.10), ("high", 0.90)):
                out[name] = np.clip(fitted[quantile].predict(design) - elapsed,
                                    0.0, None)
            out["baseline"] = self._baseline_predict(test)
            pieces.append(out)
            n_train = len(train)

        if not pieces:
            return None

        scored = pd.concat(pieces, ignore_index=True)
        truth = scored["weeks_remaining"].to_numpy(dtype=float)
        errors = np.abs(scored["median"].to_numpy() - truth)
        baseline_errors = np.abs(scored["baseline"].to_numpy() - truth)

        # Independently fitted quantiles can cross on thin data; order them
        # before measuring coverage, exactly as `predict` does.
        low = np.minimum(scored["low"].to_numpy(), scored["high"].to_numpy())
        high = np.maximum(scored["low"].to_numpy(), scored["high"].to_numpy())

        by_phase = {
            str(name): float(np.abs(
                group["median"].to_numpy() - group["weeks_remaining"].to_numpy()
            ).mean())
            for name, group in scored.groupby("phase")
        }

        # Calibrate the band width on these same out-of-fold predictions, then
        # report the coverage the calibrated band actually achieves.
        raw_coverage = float(((truth >= low) & (truth <= high)).mean())
        self.interval_pad = _conformal_pad(truth, low, high, INTERVAL_LEVEL)
        padded_low = np.clip(low - self.interval_pad, 0.0, None)
        padded_high = high + self.interval_pad

        return DurationReport(
            mae_weeks=float(errors.mean()),
            baseline_mae_weeks=float(baseline_errors.mean()),
            n_train=n_train,
            n_test=len(scored),
            n_test_windows=int(usable["window_id"].nunique()),
            coverage=float(
                ((truth >= padded_low) & (truth <= padded_high)).mean()
            ),
            raw_coverage=raw_coverage,
            interval_pad_weeks=self.interval_pad,
            mae_by_phase=by_phase,
        )

    def predict(self, features: dict[str, float], phase: str) -> dict:
        """Weeks remaining in ``phase``, or an explicit refusal.

        Refusing is a supported answer, not an error path. A phase observed to
        completion three times gives no basis for a duration prediction, and a
        fabricated number there is worse than none — the allocator would act on
        it.
        """
        if phase not in self.trainable_phases or not self.models:
            observed = self.mean_duration.get(phase)
            return {
                "verdict": "insufficient_data",
                "reason": (
                    f"only {'no' if observed is None else 'a few'} completed "
                    f"{phase} phases observed (need {MIN_COMPLETED_PHASES}); "
                    "refusing to predict an end date"
                ),
                "weeks_remaining": None,
                "weeks_remaining_low": None,
                "weeks_remaining_high": None,
            }

        row = np.array([[features[c] for c in DURATION_FEATURES]], dtype=float)
        elapsed = float(features["weeks_elapsed_in_phase"])

        # The models predict the phase's total length; remaining is arithmetic.
        totals = {
            q: float(self.models[q].predict(row)[0]) for q in QUANTILES
        }
        low, median, high = (
            totals[0.10] - elapsed,
            totals[0.50] - elapsed,
            totals[0.90] - elapsed,
        )

        # Quantile models are fitted independently and can cross on thin data.
        # Sorting is honest — the alternative is an upper bound below the point
        # estimate, which is simply wrong on screen.
        low, median, high = sorted((low, median, high))

        # Widen to the width that was actually measured to cover 80% out of
        # fold. Without this the band is roughly half as wide as it claims.
        low = max(low - self.interval_pad, 0.0)
        high = high + self.interval_pad
        median = max(median, 0.0)

        return {
            "verdict": "ok",
            "reason": None,
            "weeks_remaining": round(median, 1),
            "weeks_remaining_low": round(low, 1),
            "weeks_remaining_high": round(high, 1),
            "phase_total_weeks": round(totals[0.50], 1),
            "weeks_elapsed": round(elapsed, 1),
        }


# --------------------------------------------------------------------------
# Splitting
# --------------------------------------------------------------------------

# Folds for the grouped cross-validation below. Five gives every window a
# held-out prediction while leaving 80% of the (already small) data to fit on.
N_FOLDS = 5


def window_folds(panel: pd.DataFrame,
                 n_folds: int = N_FOLDS) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    """Grouped K-fold over whole phase windows, never individual weeks.

    **This is the single most important line of defence in the module.** Weeks
    inside one phase window are near-duplicates of each other: same site, same
    machines, a mix that moved slightly. Split them at random and week 3 lands
    in train while week 4 lands in test, the model recognises the site rather
    than the pattern, and the held-out score is a fiction.

    K-fold rather than one holdout because there are only ~40 windows: a single
    25% split leaves ten windows covering perhaps three of the six phases, so
    half the phases go unscored and the number that survives is an accident of
    which windows got drawn. Folding gives every window exactly one out-of-fold
    prediction, so the reported score covers the whole dataset.

    The assignment is seeded, so the folds do not move between runs and do not
    depend on row order.
    """
    windows = sorted(panel["window_id"].unique())
    if len(windows) < n_folds:
        return []

    rng = np.random.default_rng(config.MASTER_SEED)
    shuffled = list(windows)
    rng.shuffle(shuffled)

    assignment = {w: i % n_folds for i, w in enumerate(shuffled)}
    fold_of = panel["window_id"].map(assignment)

    return [
        (panel.loc[fold_of != k].copy(), panel.loc[fold_of == k].copy())
        for k in range(n_folds)
    ]


# --------------------------------------------------------------------------
# The lookup — what does the next phase need?
# --------------------------------------------------------------------------

def equipment_mix_by_phase(rentals: pd.DataFrame) -> pd.DataFrame:
    """Share of rentals of each type, by phase. Measured, not asserted.

    This is the "what will the next phase need" table, and it is deliberately
    **not** a model. It has six rows; a learner fitted to it would be memorising
    a lookup and inviting the question of why a model was used at all. Measuring
    it from history is both more defensible and more honest.
    """
    table = pd.crosstab(rentals["phase"], rentals["type"], normalize="index")
    return table.reindex(config.PHASE_NAMES).fillna(0.0)


def typical_machines_per_phase(rentals: pd.DataFrame,
                               site_phases: pd.DataFrame) -> pd.DataFrame:
    """Machines of each type a site typically runs during a phase.

    The mix table gives proportions; the allocator needs counts.

    **Median weekly count, not the peak.** The peak is tempting — a requirement
    is what you need at your busiest — but it is wrong here, and wrong by a
    factor of three. Rentals are strongly seasonal: activity collapses through
    the Jun-Sep monsoon and surges Oct-Dec as projects claw the quarter back. A
    phase running twenty weeks almost always covers one of those surges, so its
    peak week reflects the season rather than the phase. Sizing an August
    requirement off a November peak tells a site it is twenty machines short
    when it is not short at all.

    The median week is what the phase actually needs sustained, and the seasonal
    swing around it belongs to the demand model, not the requirement.
    """
    windows = site_phases.copy()
    windows["start_date"] = pd.to_datetime(windows["start_date"])
    windows["end_date"] = pd.to_datetime(windows["end_date"])

    type_names = [t.name for t in config.EQUIPMENT_TYPES]

    records: list[dict] = []
    for window in windows[windows["is_complete"]].itertuples(index=False):
        week = clock_adapter.week_start(window.start_date.date())
        end = window.end_date.date()
        while week <= end:
            on_site = _machines_on_site(rentals, window.site_id, week)
            counts = on_site["type"].value_counts()
            for type_name in type_names:
                records.append({
                    "phase": window.phase,
                    "type": type_name,
                    "site_id": window.site_id,
                    # Zeros must be recorded, not skipped: a type absent from a
                    # week is a real observation that the phase does not need
                    # it, and dropping those weeks pulls every median upward.
                    "machines": int(counts.get(type_name, 0)),
                })
            week += timedelta(days=7)

    if not records:
        return pd.DataFrame(columns=["phase", "type", "typical_machines"])

    frame = pd.DataFrame(records)
    typical = (
        frame.groupby(["phase", "type"])["machines"]
        .median().round(1).reset_index()
        .rename(columns={"machines": "typical_machines"})
    )
    return typical


def typical_site_size(rentals: pd.DataFrame, site_phases: pd.DataFrame) -> float:
    """Median machines on a site in a week, across the whole fleet.

    The denominator for site scaling: a site running twice this many machines
    needs roughly twice the typical complement of its next phase.
    """
    windows = site_phases.copy()
    windows["start_date"] = pd.to_datetime(windows["start_date"])
    windows["end_date"] = pd.to_datetime(windows["end_date"])

    counts: list[int] = []
    for window in windows[windows["is_complete"]].itertuples(index=False):
        week = clock_adapter.week_start(window.start_date.date())
        end = window.end_date.date()
        while week <= end:
            counts.append(len(_machines_on_site(rentals, window.site_id, week)))
            week += timedelta(days=7)

    return float(np.median(counts)) if counts else 1.0


__all__ = [
    "CLASSIFIER_FEATURES", "DURATION_FEATURES", "MIX_COLUMNS",
    "PhaseClassifier", "PhaseEndModel", "ClassifierReport", "DurationReport",
    "build_panel", "site_week_features",
    "equipment_mix_by_phase", "typical_machines_per_phase",
]
