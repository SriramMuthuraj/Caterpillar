"""Allocation engine — who needs what, who has it spare, and what to do.

This is where the two clocks meet.

    contract clock   check_in -> check_out    when the rent runs.  KNOWN
    work clock       phase start -> phase end when it is needed.   PREDICTED

They are set by different people and they do not line up. Every mismatch is
money, and which way it misses decides what to do about it:

    rent expires BEFORE the phase ends   the machine walks off mid-work
                                         -> extend, or line up a replacement

    phase ends BEFORE the rent expires   you are paying for a machine nobody
                                         needs -> move it to a site that does

The second case is the valuable one and the reason this module exists. A machine
whose phase has finished but whose contract still has three weeks to run is
capacity you have **already bought**. Moving it costs haulage; leaving it costs
the full day rate for nothing.

---

**When does a machine come free?**

    freed_at = min(end of the phase it is working, contract expiry)

Both bounds matter and they mean different things. Past the contract expiry the
machine goes back to the dealer whether or not the site still wants it. Past the
phase end the site no longer needs it whether or not the contract has run out.
Whichever comes first is when it can move, and the answer carries which bound
bit — because "free in 9 days when foundation finishes" and "free in 9 days
when the rent expires" call for different conversations.

**Decide with money, never with a threshold.** "Wait if the delay is under ten
days" is a number nobody can defend. Two costs are computed instead, the cheaper
wins, and both are returned so the recommendation can show its working.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from . import clock_adapter, config, phase as phase_mod

# How far ahead the board looks. Beyond a quarter the phase-end predictions are
# wide enough that acting on them is planning theatre.
HORIZON_WEEKS = 13

# A donor that frees up after the need date is useless, but one that frees a
# little after may still beat renting once the wait is priced. This caps how far
# past the need date a candidate is considered at all.
MAX_WAIT_DAYS = 60


# --------------------------------------------------------------------------
# Geography
# --------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def road_km(from_site: config.Site, to_site: config.Site) -> float:
    """Road distance, straight line inflated by the usual circuity factor."""
    straight = haversine_km(from_site.lat, from_site.lon,
                            to_site.lat, to_site.lon)
    return straight * config.ROAD_CIRCUITY_FACTOR


# --------------------------------------------------------------------------
# The ledger — every machine currently on rent, and when it comes free
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Machine:
    """One machine on rent, with the date it becomes available."""

    equipment_id: str
    type: str
    site_id: str
    check_in: date
    check_out: date              # contract expiry
    phase: str                   # phase its site was in when it was rented
    freed_at: date
    freed_because: str           # "phase_ends" | "contract_expires"
    contract_days_left: int
    # Days the contract runs past the point the site stops needing it. Positive
    # means paid-for capacity going spare; negative means the rent runs out
    # before the work does.
    surplus_days: int

    @property
    def is_surplus(self) -> bool:
        return self.surplus_days > 0

    def to_dict(self) -> dict:
        return {
            "equipment_id": self.equipment_id,
            "type": self.type,
            "site_id": self.site_id,
            "phase": self.phase,
            "check_out": self.check_out.isoformat(),
            "freed_at": self.freed_at.isoformat(),
            "freed_because": self.freed_because,
            "contract_days_left": self.contract_days_left,
            "surplus_days": self.surplus_days,
        }


def build_ledger(rentals: pd.DataFrame, phase_end: dict[str, date],
                 now: date) -> list[Machine]:
    """Every machine on rent right now, with the date it becomes available.

    ``phase_end`` maps site_id to the predicted end of that site's current
    phase. Sites with no usable prediction are simply absent from it, and their
    machines fall back to the contract expiry alone — a known date beats a
    fabricated one, and the ledger says which it used.
    """
    live = rentals[
        (rentals["check_in"] <= pd.Timestamp(now))
        & (rentals["check_out"] >= pd.Timestamp(now))
    ]

    machines: list[Machine] = []
    for row in live.itertuples(index=False):
        check_out = row.check_out.date()
        site_phase_end = phase_end.get(row.site_id)

        if site_phase_end is not None and site_phase_end < check_out:
            freed_at, because = site_phase_end, "phase_ends"
        else:
            freed_at, because = check_out, "contract_expires"

        surplus = ((check_out - site_phase_end).days
                   if site_phase_end is not None else 0)

        machines.append(Machine(
            equipment_id=row.equipment_id,
            type=row.type,
            site_id=row.site_id,
            check_in=row.check_in.date(),
            check_out=check_out,
            phase=row.phase,
            freed_at=freed_at,
            freed_because=because,
            contract_days_left=(check_out - now).days,
            surplus_days=surplus,
        ))

    return machines


# --------------------------------------------------------------------------
# Requirements — what the next phase needs
# --------------------------------------------------------------------------

def requirements_for(phase_name: str, typical: pd.DataFrame,
                     site_scale: float = 1.0) -> dict[str, int]:
    """Machines of each type a site needs during ``phase_name``.

    Read off the measured typical-machines table, not predicted — the "what
    does the next phase need" question is a lookup with six rows, and a model
    fitted to it would be memorising a table.

    ``site_scale`` carries how big this site is relative to a typical one,
    measured from the machines it is running now. Without it every site gets the
    fleet-average complement, which over-provisions the small ones and starves
    the large.
    """
    rows = typical[typical["phase"] == phase_name]
    out: dict[str, int] = {}
    for row in rows.itertuples(index=False):
        count = int(round(row.typical_machines * site_scale))
        if count > 0:
            out[row.type] = count
    return out


# --------------------------------------------------------------------------
# The decision
# --------------------------------------------------------------------------

@dataclass
class Option:
    """One way to satisfy a shortfall, priced."""

    kind: str                    # "redeploy" | "rent"
    total_inr: float
    available_on: date
    wait_days: int
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "total_inr": round(self.total_inr),
            "available_on": self.available_on.isoformat(),
            "wait_days": self.wait_days,
            **self.detail,
        }


def _price_rental(type_name: str, days_needed: int, needed_by: date) -> Option:
    """Call off a new machine from the dealer.

    Assumed available on the day it is wanted — the dealer holds stock, which is
    the whole point of renting. So this option never carries a wait cost, and
    that is precisely what redeployment has to beat.
    """
    day_rate = config.DAY_RATE_INR.get(type_name, 8_000.0)
    hire = day_rate * days_needed
    total = hire + config.MOBILISATION_INR
    return Option(
        kind="rent",
        total_inr=total,
        available_on=needed_by,
        wait_days=0,
        detail={
            "day_rate_inr": round(day_rate),
            "days": days_needed,
            "hire_inr": round(hire),
            "mobilisation_inr": round(config.MOBILISATION_INR),
        },
    )


def _price_redeployment(machine: Machine, to_site: config.Site,
                        needed_by: date, days_needed: int) -> Option | None:
    """Move a machine you are already paying for.

    The hire cost is **not** counted: the contract is already running and the
    money is spent whether the machine works or sits. What redeployment costs is
    haulage, plus whatever the receiving site loses while it waits for the
    machine to come free.
    """
    wait_days = max((machine.freed_at - needed_by).days, 0)
    if wait_days > MAX_WAIT_DAYS:
        return None

    from_site = config.SITE_BY_ID[machine.site_id]
    distance = road_km(from_site, to_site)
    haulage = (distance * config.TRANSPORT_INR_PER_KM
               + config.TRANSPORT_HANDLING_INR)
    waiting = wait_days * config.BLOCKED_DAY_INR

    # The contract has to still be running when the work happens, or you are
    # redeploying a machine that goes back to the dealer mid-job.
    covered_days = (machine.check_out - machine.freed_at).days
    shortfall_days = max(days_needed - covered_days, 0)
    extension = shortfall_days * config.DAY_RATE_INR.get(machine.type, 8_000.0)

    return Option(
        kind="redeploy",
        total_inr=haulage + waiting + extension,
        available_on=max(machine.freed_at, needed_by),
        wait_days=wait_days,
        detail={
            "equipment_id": machine.equipment_id,
            "from_site": machine.site_id,
            "from_site_name": from_site.name,
            "distance_km": round(distance, 1),
            "haulage_inr": round(haulage),
            "waiting_inr": round(waiting),
            "extension_days": shortfall_days,
            "extension_inr": round(extension),
            "freed_because": machine.freed_because,
            "hire_already_committed": True,
        },
    )


@dataclass
class Recommendation:
    """One site's shortfall of one machine type, and how to fill it.

    A shortfall is usually more than one machine, and the fill is usually
    mixed — move the two that are going spare nearby, rent the third. So the
    recommendation carries **per-machine assignments**, and every figure on it
    is the total across the whole shortfall. Pricing a single machine and
    labelling the row "x 5" would overstate the saving fivefold.
    """

    site_id: str
    site_name: str
    type: str
    quantity: int
    needed_by: date
    for_phase: str
    decision: str                # "redeploy" | "rent" | "mixed"
    saving_inr: float
    redeployments: list[Option]
    rentals: list[Option]
    rent_unit_inr: float

    @property
    def total_inr(self) -> float:
        return (sum(o.total_inr for o in self.redeployments)
                + sum(o.total_inr for o in self.rentals))

    @property
    def all_rented_inr(self) -> float:
        """What it would cost to just call off the whole shortfall."""
        return self.rent_unit_inr * self.quantity

    def to_dict(self) -> dict:
        return {
            "site_id": self.site_id,
            "site_name": self.site_name,
            "type": self.type,
            "quantity": self.quantity,
            "needed_by": self.needed_by.isoformat(),
            "for_phase": self.for_phase,
            "decision": self.decision,
            "redeploy_count": len(self.redeployments),
            "rent_count": len(self.rentals),
            "total_inr": round(self.total_inr),
            "all_rented_inr": round(self.all_rented_inr),
            "saving_inr": round(self.saving_inr),
            "redeployments": [o.to_dict() for o in self.redeployments],
            "rentals": [o.to_dict() for o in self.rentals],
            "rationale": self._rationale(),
        }

    def _rationale(self) -> str:
        """One sentence a site manager can act on without reading the numbers."""
        need = f"{self.quantity} x {self.type}"
        if not self.redeployments:
            return (
                f"{need} needed for {self.for_phase} and nothing comes free in "
                f"time — call off from the dealer."
            )

        first = self.redeployments[0].detail
        waits = [o.wait_days for o in self.redeployments]
        when = (f"the longest wait is {max(waits)} days" if max(waits)
                else "all are free already")
        moved = len(self.redeployments)
        tail = (f"; the remaining {len(self.rentals)} must be rented"
                if self.rentals else "")

        return (
            f"{need} needed for {self.for_phase}. Move {moved} you are already "
            f"paying for — nearest is {first['equipment_id']} at "
            f"{first['from_site_name']}, {first['distance_km']} km away — and "
            f"{when}{tail}. Saves ₹{self.saving_inr:,.0f} against renting all "
            f"{self.quantity}."
        )


def recommend(rentals: pd.DataFrame, site_status: dict[str, dict],
              typical: pd.DataFrame, typical_site_size: float = 1.0,
              now: date | None = None) -> list[Recommendation]:
    """Match every site's next-phase shortfall against the fleet.

    ``site_status`` is keyed by site_id and carries the current phase, the
    predicted end date and the next phase — everything the phase engine knows
    and this module does not recompute.

    Donors are consumed as they are assigned, so one machine is never promised
    to two sites. Sites are served in order of urgency (soonest need first),
    which is a greedy rule rather than a global optimum: with a few dozen
    machines the difference is small, and a recommendation a manager can follow
    beats one they have to trust.
    """
    now = now or clock_adapter.now_date()

    phase_end = {
        site_id: status["phase_end_date"]
        for site_id, status in site_status.items()
        if status.get("phase_end_date") is not None
    }
    ledger = build_ledger(rentals, phase_end, now)

    # Only machines that are genuinely spare may be moved: their site stops
    # needing them before the contract runs out. Everything else is committed.
    donors = sorted(
        (m for m in ledger if m.is_surplus),
        key=lambda m: m.freed_at,
    )
    taken: set[str] = set()

    # Work the most urgent needs first.
    pending = sorted(
        (s for s in site_status.values()
         if s.get("next_phase") and s.get("phase_end_date")),
        key=lambda s: s["phase_end_date"],
    )

    out: list[Recommendation] = []
    horizon = now + timedelta(weeks=HORIZON_WEEKS)

    for status in pending:
        needed_by = status["phase_end_date"]
        if needed_by > horizon:
            continue

        site = config.SITE_BY_ID[status["site_id"]]

        # How big this site is relative to a typical one, from the machines it
        # is running now. Observable, and it stops every site being handed the
        # fleet-average complement regardless of its size.
        scale = (status.get("machines_on_site", 0) / typical_site_size
                 if typical_site_size else 1.0)
        scale = min(max(scale, 0.4), 2.5)

        needs = requirements_for(status["next_phase"], typical, scale)
        on_site = _on_site_counts(ledger, site.site_id, needed_by)

        # How long the machine will be wanted: the next phase's typical length.
        days_needed = int(round(
            status.get("next_phase_typical_weeks", 12.0) * 7
        ))

        for type_name, required in sorted(needs.items()):
            gap = required - on_site.get(type_name, 0)
            if gap <= 0:
                continue

            rent = _price_rental(type_name, days_needed, needed_by)

            # Price every machine that could be moved here, cheapest first.
            candidates: list[tuple[float, Machine, Option]] = []
            for machine in donors:
                if (machine.equipment_id in taken
                        or machine.type != type_name
                        or machine.site_id == site.site_id):
                    continue
                option = _price_redeployment(machine, site, needed_by,
                                             days_needed)
                if option is not None:
                    candidates.append((option.total_inr, machine, option))
            candidates.sort(key=lambda c: c[0])

            # Fill the shortfall one machine at a time, taking a donor only
            # while it actually beats renting that machine. This is what makes
            # a mixed answer possible — move the two nearby, rent the third —
            # rather than forcing the whole block one way.
            redeployments: list[Option] = []
            for cost, machine, option in candidates:
                if len(redeployments) >= gap or cost >= rent.total_inr:
                    break
                redeployments.append(option)
                taken.add(machine.equipment_id)

            rentals_needed = gap - len(redeployments)
            rented = [rent] * rentals_needed
            saving = sum(rent.total_inr - o.total_inr for o in redeployments)

            if not redeployments:
                decision = "rent"
            elif rentals_needed:
                decision = "mixed"
            else:
                decision = "redeploy"

            out.append(Recommendation(
                site_id=site.site_id,
                site_name=site.name,
                type=type_name,
                quantity=gap,
                needed_by=needed_by,
                for_phase=status["next_phase"],
                decision=decision,
                saving_inr=saving,
                redeployments=redeployments,
                rentals=rented,
                rent_unit_inr=rent.total_inr,
            ))

    return out


def _on_site_counts(ledger: list[Machine], site_id: str,
                    as_of: date) -> dict[str, int]:
    """Machines of each type still at a site on a future date.

    A machine only counts toward the next phase's requirement if it is still
    both on contract and not yet released — which is exactly ``freed_at``.
    """
    counts: dict[str, int] = {}
    for machine in ledger:
        if machine.site_id == site_id and machine.freed_at > as_of:
            counts[machine.type] = counts.get(machine.type, 0) + 1
    return counts


def surplus_report(rentals: pd.DataFrame, site_status: dict[str, dict],
                   now: date | None = None) -> list[dict]:
    """Machines being paid for past the point their site needs them.

    The counterpart to the shortfall board, and the cheaper half of the story:
    this is money already going out of the door, visible without predicting
    anything about demand.
    """
    now = now or clock_adapter.now_date()
    phase_end = {
        site_id: status["phase_end_date"]
        for site_id, status in site_status.items()
        if status.get("phase_end_date") is not None
    }

    rows = []
    for machine in build_ledger(rentals, phase_end, now):
        if not machine.is_surplus:
            continue
        day_rate = config.DAY_RATE_INR.get(machine.type, 8_000.0)
        rows.append({
            **machine.to_dict(),
            "site_name": config.SITE_BY_ID[machine.site_id].name,
            "idle_cost_inr": round(day_rate * machine.surplus_days),
            "day_rate_inr": round(day_rate),
        })

    return sorted(rows, key=lambda r: r["idle_cost_inr"], reverse=True)


__all__ = [
    "Machine", "Option", "Recommendation",
    "build_ledger", "recommend", "surplus_report",
    "requirements_for", "haversine_km", "road_km",
]
