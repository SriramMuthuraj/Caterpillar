"""One dataset, three views.

The generated rental history is the single source of truth. Everything the
product shows is a projection of it, so no two screens can contradict each
other::

    rental_history_*.csv   7,209 rows · 677 machines · 3 years
       |
       +-- history()         all rows          -> forecast models, anomaly rules
       +-- live_snapshot()   active at `now`   -> Cat_SRTS operational store
       +-- anomaly_view()    renamed columns   -> the anomaly detector

**history vs current state.** These are different kinds of data, not different
sizes of the same data. The history is three years of completed rentals and is
what the models learn from. The live snapshot is what is on hire *today* — at
``DEMO_NOW`` that is 296 machines across 24 sites — and it is what an operations
dashboard is for. The snapshot is *derived*, never authored: a machine appears
in it because it has a rental spanning ``now``. Sample the fleet instead and the
dashboard says "20 machines" while the forecast page says "296 active", which is
a contradiction a five-second glance would catch.

**The naming inversion.** Cat_SRTS and the forecast module use ``check_out`` to
mean opposite ends of a rental:

===============================  ==========================================
``rentals.check_in``             rental starts  ->  ``assignment.checkOutTime``
``rentals.check_out``            rent expires   ->  ``equipment.expectedReturnDate``
``assignment.checkInTime``       machine returned (null while on hire)
===============================  ==========================================

His "check out" is the machine leaving the yard; mine is the contract running
out. Getting this backwards is silent and plausible, so it has its own test.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta

import pandas as pd

from ..forecast import clock_adapter, config, history as history_mod

# One usage log per active rental per day over this window. Seven days keeps the
# collection around 2,000 rows — enough for the dashboard's charts and the
# detector's per-machine baselines without turning the seed file into a
# database dump.
USAGE_LOG_DAYS = 7

# A machine whose contract ended within this many days of `now` is still worth
# showing: it came off hire recently, it is not on hire today, and "what did we
# just send back?" is a question an equipment manager asks. Beyond this window
# the machine has left the story and is history, not operations.
RECENTLY_RETURNED_DAYS = 30

# Cosmetic fields Cat_SRTS's UI shows but the rental schema never carried.
# Declared here rather than invented inline, so they are auditable.
HORSEPOWER = {
    "Excavator": 172,
    "Wheel Loader": 148,
    "Backhoe Loader": 96,
    "Telehandler": 74,
    "Compactor": 110,
}

MODEL_NAMES = {
    "Excavator": "CAT 320",
    "Wheel Loader": "CAT 950 GC",
    "Backhoe Loader": "CAT 424",
    "Telehandler": "CAT TL943",
    "Compactor": "CAT CS11 GC",
}

_FIRST_NAMES = (
    "Arun", "Bala", "Chandran", "Dinesh", "Elango", "Ganesh", "Hari",
    "Ilango", "Jagan", "Karthik", "Lokesh", "Manoj", "Naveen", "Prakash",
    "Rajesh", "Suresh", "Thiru", "Udhaya", "Vignesh", "Yuvan",
)
_LAST_NAMES = (
    "Kumar", "Raman", "Selvam", "Murugan", "Pandian", "Anand", "Krishnan",
    "Subramani", "Natarajan", "Venkatesh",
)


# --------------------------------------------------------------------------
# Deterministic identifiers
# --------------------------------------------------------------------------

def _oid(*parts: str) -> str:
    """A stable 24-hex ObjectId derived from the key, not from the clock.

    Real ObjectIds embed a timestamp and a random counter, so reseeding would
    produce different _ids every run and diffs of the seed files would be
    meaningless. These are reproducible: same input, same id, forever.
    """
    digest = hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:24]


def _operator_name(operator_id: str) -> str:
    """Stable human name for an operator id, derived from the id itself."""
    digest = hashlib.md5(operator_id.encode("utf-8")).digest()
    return (f"{_FIRST_NAMES[digest[0] % len(_FIRST_NAMES)]} "
            f"{_LAST_NAMES[digest[1] % len(_LAST_NAMES)]}")


def _phone(operator_id: str) -> str:
    digest = hashlib.md5(("phone" + operator_id).encode("utf-8")).digest()
    return "+91-9" + "".join(str(b % 10) for b in digest[:9])


def _site_name(site_id) -> str:
    site = config.SITE_BY_ID.get(site_id)
    return site.name if site else "Unassigned"


def _dt(value) -> datetime | None:
    """Normalise to a naive datetime, or None for a missing value."""
    if value is None or pd.isna(value):
        return None
    stamp = pd.Timestamp(value)
    return stamp.to_pydatetime().replace(tzinfo=None)


# --------------------------------------------------------------------------
# The three views
# --------------------------------------------------------------------------

def history() -> pd.DataFrame:
    """Every rental ever recorded — the training and detection surface.

    Reads the cached CSV directly rather than going through ``service``, whose
    accessor builds the entire forecast bundle (models, backtest) on first call.
    The anomaly detector and the operational snapshot need the *data*, not the
    models, and neither should wait forty seconds for something it will not use.
    """
    return history_mod.cached_history(
        seed=config.MASTER_SEED,
        now=clock_adapter.now_date(),
        weeks=config.HISTORY_WEEKS,
    )


def active_rentals(now: date | None = None) -> pd.DataFrame:
    """Rentals whose contract window spans ``now``.

    Rows with no site (config.RATE_UNASSIGNED_SITE) are kept: an unassigned
    machine is still on hire and still costing money, and it is precisely what
    the detector's ``unassigned_equipment`` rule exists to surface. Only the
    modelling panels drop them.
    """
    now = now or clock_adapter.now_date()
    stamp = pd.Timestamp(now)

    frame = history().copy()
    frame["check_in"] = pd.to_datetime(frame["check_in"])
    frame["check_out"] = pd.to_datetime(frame["check_out"])

    live = frame[(frame["check_in"] <= stamp) & (frame["check_out"] >= stamp)]

    # One machine, one active rental. The generator guarantees no double
    # booking, but this makes the collection's uniqueness explicit rather than
    # relying on a property maintained elsewhere.
    return live.sort_values("check_in").drop_duplicates(
        subset="equipment_id", keep="last"
    ).reset_index(drop=True)


def recently_returned(now: date | None = None) -> pd.DataFrame:
    """Machines whose last contract ended in the RECENTLY_RETURNED_DAYS window.

    Excludes anything currently on hire — a machine that went straight back out
    is active, not returned. These rows exist so the fleet view is not
    exclusively "on hire today": a dashboard where Available and Returned are
    permanently zero looks broken even when it is accurate.
    """
    now = now or clock_adapter.now_date()
    stamp = pd.Timestamp(now)
    cutoff = stamp - pd.Timedelta(days=RECENTLY_RETURNED_DAYS)

    frame = history().copy()
    frame["check_in"] = pd.to_datetime(frame["check_in"])
    frame["check_out"] = pd.to_datetime(frame["check_out"])

    on_hire = set(active_rentals(now)["equipment_id"])
    last = frame.sort_values("check_out").groupby("equipment_id").tail(1)

    returned = last[
        (last["check_out"] < stamp)
        & (last["check_out"] >= cutoff)
        & (~last["equipment_id"].isin(on_hire))
    ]
    return returned.sort_values("check_out", ascending=False).reset_index(drop=True)


def live_snapshot(now: date | None = None) -> dict[str, list[dict]]:
    """Today's operational state, in Cat_SRTS's exact camelCase schema.

    Returned in the shape his services and his React types already expect, so
    nothing on his side has to change to display a fleet 15x larger than the
    one he seeded with.
    """
    now = now or clock_adapter.now_date()
    live = active_rentals(now)
    stamped = _dt(now)

    equipment, operators, assignments, usage_logs = [], [], [], []
    seen_operators: dict[str, str] = {}

    for position, row in enumerate(live.itertuples(index=False), start=1):
        equipment_id = row.equipment_id
        site_name = _site_name(row.site_id)
        check_in = _dt(row.check_in)        # machine went out
        check_out = _dt(row.check_out)      # rent expires

        # A machine working more than it idles is Working; otherwise Idle.
        # Both are "on hire" — the distinction his dashboard draws is about
        # utilisation, not custody.
        working = float(row.engine_hours_per_day) >= float(row.idle_hours_per_day)

        equipment.append({
            "_id": {"$oid": _oid("equipment", equipment_id)},
            "equipmentId": equipment_id,
            "equipmentName": f"{MODEL_NAMES.get(row.type, 'CAT')} {row.type}",
            "category": row.type,
            "manufacturer": "Caterpillar",
            "horsePower": HORSEPOWER.get(row.type, 100),
            "ownershipStatus": "Rented",
            "currentStatus": "Working" if working else "Idle",
            "lastUsedDate": {"$date": check_in.isoformat()},
            # The contract expiry. This is what makes his RETURN_DUE alert rule
            # fire — it had nothing to work with before.
            "expectedReturnDate": {"$date": check_out.isoformat()},
            "createdAt": {"$date": check_in.isoformat()},
            "updatedAt": {"$date": stamped.isoformat()},
        })

        operator_id = None if pd.isna(row.operator_id) else row.operator_id
        if operator_id and operator_id not in seen_operators:
            seen_operators[operator_id] = equipment_id
            operators.append({
                "_id": {"$oid": _oid("operator", operator_id)},
                "operatorId": operator_id,
                "operatorName": _operator_name(operator_id),
                "licenseNumber": f"HEQ-LIC-{operator_id.replace('-', '')}",
                "phoneNumber": _phone(operator_id),
                "assignedEquipmentId": equipment_id,
                "createdAt": {"$date": check_in.isoformat()},
                "updatedAt": {"$date": stamped.isoformat()},
            })

        assignments.append({
            "_id": {"$oid": _oid("assignment", row.rental_id)},
            "assignmentId": f"ASG-{position:04d}",
            "equipmentId": equipment_id,
            "operatorId": operator_id,
            "siteName": site_name,
            # checkOutTime is the machine leaving the yard = our check_in.
            "checkOutTime": {"$date": check_in.isoformat()},
            # Still on hire, so it has not been checked back in.
            "checkInTime": None,
            "status": "Working" if working else "Idle",
            "createdAt": {"$date": check_in.isoformat()},
            "updatedAt": {"$date": stamped.isoformat()},
        })

    # Off-hire machines from the last month. They get an equipment record only:
    # no operator is assigned to a machine that has gone back, and an assignment
    # that has ended is history rather than current state.
    for row in recently_returned(now).itertuples(index=False):
        returned_on = _dt(row.check_out)
        equipment.append({
            "_id": {"$oid": _oid("equipment", row.equipment_id)},
            "equipmentId": row.equipment_id,
            "equipmentName": f"{MODEL_NAMES.get(row.type, 'CAT')} {row.type}",
            "category": row.type,
            "manufacturer": "Caterpillar",
            "horsePower": HORSEPOWER.get(row.type, 100),
            "ownershipStatus": "Rented",
            "currentStatus": "Returned",
            "lastUsedDate": {"$date": returned_on.isoformat()},
            # Nothing is expected back — it is already back. Leaving the old
            # contract date here would make the RETURN_DUE rule, which only
            # tests `expectedReturnDate <= today`, flag every returned machine.
            "expectedReturnDate": None,
            "createdAt": {"$date": _dt(row.check_in).isoformat()},
            "updatedAt": {"$date": stamped.isoformat()},
        })

    usage_logs = _usage_logs(live, now)

    return {
        "equipment": equipment,
        "operators": operators,
        "assignments": assignments,
        "usage_logs": usage_logs,
    }


def _usage_logs(live: pd.DataFrame, now: date) -> list[dict]:
    """Daily telemetry for the last USAGE_LOG_DAYS, per active machine.

    The rental row carries per-day averages, so a day's log is that average
    rather than a fresh draw. Inventing daily variation here would put noise in
    front of the anomaly detector that exists in no other view of the data.
    """
    logs = []
    counter = 0

    for row in live.itertuples(index=False):
        site_name = _site_name(row.site_id)
        operator_id = None if pd.isna(row.operator_id) else row.operator_id
        started = _dt(row.check_in)

        for back in range(USAGE_LOG_DAYS):
            day = _dt(now) - timedelta(days=back)
            if day < started:
                continue        # the machine was not on site yet
            counter += 1
            logs.append({
                "_id": {"$oid": _oid("usage", row.rental_id, str(back))},
                "usageId": f"USE-{counter:06d}",
                "equipmentId": row.equipment_id,
                "operatorId": operator_id,
                "runtimeHours": round(float(row.engine_hours_per_day), 2),
                "idleHours": round(float(row.idle_hours_per_day), 2),
                "fuelUsage": round(float(row.fuel_l_per_day), 1),
                "location": site_name,
                "usageDate": {"$date": day.isoformat()},
                "createdAt": {"$date": day.isoformat()},
            })

    return logs


# --------------------------------------------------------------------------
# The anomaly detector's view
# --------------------------------------------------------------------------

# The detector was written against the original supplied schema and every one of
# these is dereferenced unconditionally. Renaming here rather than editing his
# rules keeps his golden test — which pins exact scores against his own 76-row
# sample — passing untouched.
ANOMALY_COLUMNS = [
    "Equipment_ID", "Type", "Site_ID", "Check_In_Date", "Check_Out_Date",
    "Engine_Hours_Day", "Idle_Hours_Day", "Rental_Days", "Last_Operator_ID",
]

_RENAME = {
    "equipment_id": "Equipment_ID",
    "type": "Type",
    "site_id": "Site_ID",
    "check_in": "Check_In_Date",
    "check_out": "Check_Out_Date",
    "engine_hours_per_day": "Engine_Hours_Day",
    "idle_hours_per_day": "Idle_Hours_Day",
    "rental_days": "Rental_Days",
    "operator_id": "Last_Operator_ID",
}


def anomaly_view(now: date | None = None,
                 keep_rental_id: bool = False) -> pd.DataFrame:
    """The history in the 9 columns the anomaly detector requires.

    A pure rename plus formatting — no rows are added, dropped or altered. The
    detector's own rules decide what is wrong with the data; this function must
    not pre-judge that by cleaning anything on the way through.

    Two conventions the detector depends on and pandas does not produce by
    default: dates are ``%Y-%m-%d`` strings (``main.py`` parses them with an
    unguarded ``strptime``, so any other format aborts the run), and missing
    values are the literal string ``"NULL"`` rather than NaN.

    ``keep_rental_id`` adds a tenth column so findings can be joined back to
    their source row — extra columns are ignored by every rule, which only ever
    select by name.
    """
    frame = history().copy()

    frame["check_in"] = pd.to_datetime(frame["check_in"]).dt.strftime("%Y-%m-%d")
    frame["check_out"] = pd.to_datetime(frame["check_out"]).dt.strftime("%Y-%m-%d")

    out = frame.rename(columns=_RENAME)
    columns = list(ANOMALY_COLUMNS)
    if keep_rental_id:
        out = out.rename(columns={"rental_id": "Rental_ID"})
        columns.append("Rental_ID")

    out = out[columns]

    # "NULL" is the sentinel the detector's parsers recognise; NaN would be read
    # by parse_float as 0.0 and silently trip the zero_activity integrity rule.
    return out.fillna("NULL")


def write_anomaly_csv(path, now: date | None = None,
                      keep_rental_id: bool = False):
    """Write the anomaly view where ``run_pipeline`` can read it."""
    frame = anomaly_view(now=now, keep_rental_id=keep_rental_id)
    frame.to_csv(path, index=False)
    return path
