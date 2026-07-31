# MOD-02 — Virtual Clock

**Layer:** Foundation · **Owner:** M1 · **Implements:** FR-10 (service) · **Depends on:** nothing · **Window:** H1–H3 (~2h, plus 15 min for the CI guard)
**Consumed by:** `MOD-03`, `MOD-04`, `MOD-06`, `MOD-07`, `MOD-08`, `MOD-09`, `MOD-10`, `MOD-15`

---

## 1. Purpose

Be the **only** source of `now` in the entire system.

This is the smallest module in the project and the one with the widest blast radius. It is not a convenience — it is load-bearing. Every date in the supplied dataset is in the past, so a single stray `datetime.now()` call silently produces "no rentals are active," and `FR-5` (overdue alerts) quietly returns an empty list with no error anywhere. That failure is invisible until the demo.

It also buys a feature: the **time-travel scrubber**, which is how you prove alerting actually works instead of showing static text.

## 2. Design decisions

### D1 — `T0` is a fixed literal in config, never `real_now`

```yaml
# data/gen_config.yaml
t0: "2026-07-30T09:00:00+05:30"    # Asia/Kolkata
timezone: "Asia/Kolkata"
```

If `T0` were derived from the real date, the generated fleet would change every day, every test asserting a demo state would break overnight, and `NFR-3` (determinism) would be unsatisfiable. `T0` is committed, reviewed, and changed only deliberately.

All timestamps are **timezone-aware**, IST throughout. Naive datetimes are rejected at construction.

### D2 — Default mode is FROZEN

| Mode | Behaviour | Use |
|---|---|---|
| **`FROZEN`** *(default)* | `now` changes only on explicit `scrub` / `advance` | Demo, tests, everything |
| `ACCELERATED` | `now = t0 + (real_elapsed × speed)` | Optional scripted beat only |

Frozen is the right default because an accelerated clock changes state *underneath the presenter*. At a plausible speed factor, an asset cast as "due in 2 days" flips to overdue partway through a 3-minute pitch — possibly a nice moment, more likely a confusing one, and never reproducible between rehearsal and performance.

Dynamism comes from the **scrubber**, which is deliberate and controlled. `ACCELERATED` stays in the codebase as a mode in case you want one scripted "watch it tick over live" beat, but the demo does not depend on it.

### D3 — The clock is read exactly once per request, at the API boundary

**This is the architectural rule that matters.** Engines do not call the clock. They receive `now` as an explicit argument:

```python
# API layer — the ONLY place clock.now() is called
now = clock.now()
findings = integrity.score(fleet, now=now)
alerts   = alerting.evaluate(fleet, now=now)
kpis     = kpi.summarise(fleet, now=now, trust="all")
```

Consequences, all good:

- Every engine is a **pure function** of `(data, now)` — unit-testable at any instant with no singleton, no monkeypatching, no global state.
- One request has one consistent `now`. Without this, a long request could see time change mid-computation and produce a self-inconsistent response.
- Determinism is structural rather than hoped for.

### D4 — Time travel is free because state is a fold filtered by `now`

`MOD-03` derives asset state by folding custody events. If the fold filters `ts <= now`, then scrubbing backwards automatically un-does events, and scrubbing forwards re-applies them. No snapshotting, no undo stack, no special-casing:

```python
def fold_state(events, now):
    return reduce(apply, [e for e in events if e.ts <= now], INITIAL)
```

Scrubbing never mutates or deletes events. Events are facts with timestamps; `now` only decides which facts have happened yet. This is why the append-only ledger in `MOD-03` and the virtual clock are worth building as a pair — each makes the other cheap.

### D5 — Scrub bounds are clamped

`[t0 − 365d, t0 + 90d]`. Before that there is no history; beyond it every rental is closed and the screen is meaningless. Out-of-range requests clamp and return the clamped value rather than erroring — a judge dragging a slider should never see a stack trace.

### D6 — No persistence

Clock state lives in memory. A server restart returns to `T0`, which is the correct recovery behaviour: restart gets you back to the known-good scripted state.

## 3. Interface

```python
# backend/clock/clock.py
class Mode(str, Enum):
    FROZEN = "frozen"
    ACCELERATED = "accelerated"

class VirtualClock:
    def now(self) -> datetime          # tz-aware, always
    def t0(self) -> datetime           # the canonical demo epoch
    def scrub(self, to: datetime) -> datetime      # clamped; returns actual
    def advance(self, delta: timedelta) -> datetime
    def set_mode(self, mode: Mode, speed: float = 1.0) -> None
    def reset(self) -> datetime        # back to T0
    def state(self) -> ClockState      # now, t0, mode, speed, bounds

clock: VirtualClock   # module-level singleton, constructed from config
```

### API

```
GET  /api/clock                 -> {now, t0, mode, speed, bounds:{min,max}}
POST /api/clock/scrub  {to}     -> {now}          # clamped
POST /api/clock/advance {days?, hours?} -> {now}
POST /api/clock/reset           -> {now}
```

`POST /api/clock/reset` is the **demo panic button**. If a judge scrubs somewhere strange during Q&A, one click restores the scripted state. Put it in the UI.

## 4. Enforcement — the CI guard that actually makes this work

Code review will not hold this invariant across four people at 3 a.m. A grep test will.

```python
# tests/test_no_real_clock.py
BANNED = [
    r"datetime\.now\(", r"datetime\.utcnow\(", r"datetime\.today\(",
    r"date\.today\(",   r"time\.time\(",       r"pd\.Timestamp\.now\(",
    r"pd\.Timestamp\.utcnow\(", r"np\.datetime64\(\s*['\"]now",
]
ALLOWED_PATHS = {"backend/clock/"}   # the only place real time may be read
```

Scan every `.py` under `backend/` and `scripts/`, fail with the offending file and line. **Fifteen minutes of work protecting the single most silent failure mode in the project.**

Frontend equivalent — an ESLint `no-restricted-syntax` rule banning bare `new Date()`:

### ⚠️ The frontend trap — flag this to M4 explicitly

If the console computes `daysRemaining` with `new Date()` in the browser, **the scrubber appears broken**: dates on screen change but derived countdowns and statuses do not. The bug looks like the backend is wrong and costs an hour to find.

Rules for `MOD-15`/`MOD-17`:
- `now` comes from `GET /api/clock` or is embedded in the API response — never from the browser.
- All business-logic dates (`days_remaining`, `is_overdue`, `status`) are computed **server-side** and sent as fields.
- The browser's `Date` is used only to *format* an ISO string for display, never to compute.

## 5. Files owned

```
backend/clock/__init__.py
backend/clock/clock.py          # VirtualClock, Mode, ClockState
backend/clock/routes.py         # the 4 endpoints
tests/test_clock.py
tests/test_no_real_clock.py     # the CI guard
```

## 6. Tests

| Test | Asserts |
|---|---|
| `test_initial_now_is_t0` | `clock.now() == t0` from config on a fresh process |
| `test_always_tz_aware` | `now().tzinfo is not None`; naive input rejected |
| `test_scrub_moves_now` | scrub to `t0+5d` → `now()` reflects it |
| `test_scrub_clamps` | scrub to `t0+500d` returns `t0+90d`, no exception |
| `test_advance` | `advance(days=3)` from `t0` → `t0+3d` |
| `test_reset` | after scrub, `reset()` → `t0` |
| `test_accelerated_mode` | with `speed=60`, virtual elapsed ≈ real elapsed × 60 |
| `test_fold_respects_now` | scrub back before an event → that event is absent from folded state; scrub forward → present |
| `test_determinism` | identical scrub sequences → identical folded state and identical confidence scores |
| **`test_no_real_clock_calls`** | **no banned real-clock call anywhere outside `backend/clock/`** |

`test_no_real_clock_calls` is the one that earns its keep. Run it in CI on every push.

## 7. Demo role — the 15-second beat that proves alerting is real

Scripted, in `MOD-15`:

1. EQX1001 shows **"due in 2 days"**, confidence Caution.
2. Drag the scrubber forward 3 days.
3. Live, without a page reload: status flips to **OVERDUE**, the alert badge escalates, overrun exposure appears in ₹, and a recommendation card materialises.
4. Click **Reset** — back to the scripted state.

Most teams will present overdue alerting as a static list and assert it works. This *demonstrates* it in one gesture, and it exists only because the clock is virtual.

## 8. Risks

| Risk | Mitigation |
|---|---|
| A stray `datetime.now()` silently empties the alert list | `test_no_real_clock_calls` in CI |
| Frontend computes dates locally → scrubber looks broken | D3/§4 rule: all derived dates server-side; ESLint rule |
| `T0` accidentally set to `real_now` | Config literal, covered by `test_initial_now_is_t0` |
| Timezone drift between frontend and backend | ISO-8601 with offset everywhere; browser never localizes for logic |
| Judge scrubs into a strange state during Q&A | `POST /api/clock/reset`, surfaced as a visible button |
| Engines cache `now` at import time | D3: `now` is a parameter, never module state |

## 9. Definition of Done

- [ ] All four endpoints live; `GET /api/clock` returns tz-aware `now`, `t0`, mode and bounds
- [ ] `MOD-03`'s fold filters on `now` and passes `test_fold_respects_now`
- [ ] All 10 tests pass, including the CI guard
- [ ] No engine imports `clock` — every engine takes `now` as an argument
- [ ] Scrubber round-trips in the UI and **Reset** restores `T0`
- [ ] Merged to `main` with `main` still running
