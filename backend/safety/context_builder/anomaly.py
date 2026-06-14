"""Deterministic anomaly detection.

Compares the *current* household state against *learned patterns* to surface
deviations. Every detector is a pure function of (state, patterns, recent
events, now) so it is trivially testable and explainable.

All time reasoning is **date-aware**: instead of comparing bare
minutes-since-midnight (which silently breaks for late-evening routines and
cross-midnight cases), expected ON/OFF times are anchored to concrete
``datetime`` instants relative to ``now``. Durations are computed from absolute
``device_on_since`` timestamps and clamped to be non-negative so a simulated
"what-if" clock can never silently disable a detector.

Detectors implemented
=====================
1. device_left_on    — a device that a sequence/time pattern says should be OFF
                       by now is still active (Example 1: son's fan left on).
2. duration_exceeded — an active device has been running far longer than its
                       learned usual duration (Example 4: water motor 45 vs 15).
3. device_active_too_long — absolute safety-net for devices with no learned
                       duration pattern (e.g. a door left open for a full day).
4. missed_routine    — a high-confidence ON/OPEN routine whose window has passed
                       but which did not happen today (Example 2/3 support).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from safety.app.config import get_settings
from safety.models.context import Anomaly, AnomalyType
from safety.models.events import Event
from safety.models.patterns import (
    BasePattern,
    DurationPattern,
    PatternType,
    SequencePattern,
    TimePattern,
)
from safety.models.state import HouseholdState


# ─── Date-aware time helpers ─────────────────────────────────────────────────


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _now_minutes(now: datetime) -> int:
    return now.hour * 60 + now.minute


def _hhmm_to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _parse_since(since_iso: str) -> datetime:
    return _ensure_utc(datetime.fromisoformat(since_iso))


def _at_time_of_day(reference: datetime, minute_of_day: int) -> datetime:
    """``reference``'s date at the given minute-of-day (seconds zeroed)."""
    return reference.replace(
        hour=minute_of_day // 60,
        minute=minute_of_day % 60,
        second=0,
        microsecond=0,
    )


def _most_recent_occurrence(now: datetime, minute_of_day: int) -> datetime:
    """Latest datetime ``<= now`` whose time-of-day == ``minute_of_day``."""
    candidate = _at_time_of_day(now, minute_of_day)
    if candidate > now:
        candidate -= timedelta(days=1)
    return candidate


def _next_occurrence_at_or_after(start: datetime, minute_of_day: int) -> datetime:
    """Earliest datetime ``>= start`` whose time-of-day == ``minute_of_day``."""
    candidate = _at_time_of_day(start, minute_of_day)
    if candidate < start:
        candidate += timedelta(days=1)
    return candidate


def _elapsed_minutes(since: datetime, now: datetime) -> float:
    """Minutes a device has been running, clamped to be non-negative.

    With a simulated clock the caller can set ``now`` to a time-of-day *before*
    the device's real ``device_on_since`` timestamp. Rather than yield a
    negative duration (which used to silently disable the duration detectors),
    we treat that as "not yet running" → 0 minutes.
    """
    return max(0.0, (now - since).total_seconds() / 60.0)


def _usual_on_window(patterns: list[BasePattern]) -> dict[str, tuple[int, int]]:
    """device -> (usual_on_minute, window_minutes) from learned ON time patterns."""
    out: dict[str, tuple[int, int]] = {}
    for p in patterns:
        if isinstance(p, TimePattern) and p.action in {"ON", "OPEN"}:
            out[p.device] = (_hhmm_to_minutes(p.usual_time), p.window_minutes)
    return out


# ─── Detector 1: device left on ──────────────────────────────────────────────


def detect_device_left_on(
    state: HouseholdState,
    patterns: list[BasePattern],
    now: datetime,
) -> list[Anomaly]:
    """Fire when a device that *should* be off (per a learned OFF time/sequence
    pattern) is still in ``active_devices`` past its scheduled OFF time.

    Date-aware logic:

      * When we know ``device_on_since``, the relevant OFF time is the **first
        scheduled OFF after the device turned on**. A device switched on in the
        evening is therefore measured against the *next* morning OFF, not a
        morning OFF that already passed — this is what stops fresh evening
        activations from being mislabelled "left on" (Issue 1) without relying
        on a loose ON-window heuristic.
      * When ``device_on_since`` is unknown, we fall back to the **most recent
        past occurrence** of the OFF time relative to ``now``. This makes
        late-evening OFF routines (e.g. 23:30) fire correctly after midnight,
        which the old minutes-since-midnight comparison could never do.

    Devices with a learned ``DurationPattern`` are skipped here — the duration
    detector judges "running too long" far more precisely.
    """
    s = get_settings()
    now = _ensure_utc(now)
    grace = timedelta(minutes=s.departure_grace_minutes)
    anomalies: list[Anomaly] = []

    has_duration = {p.device for p in patterns if isinstance(p, DurationPattern)}

    # Devices a pattern expects to be OFF, with the usual OFF minute-of-day and
    # the routine's own jitter window. TimePattern OFF wins over SequencePattern
    # (assignment vs setdefault), so the more precise per-device OFF time is
    # always used regardless of order.
    # device -> (pattern_id, off_minute, window_minutes)
    expected_off: dict[str, tuple[str, int, int]] = {}
    for p in patterns:
        if isinstance(p, TimePattern) and p.action == "OFF":
            expected_off[p.device] = (
                p.pattern_id,
                _hhmm_to_minutes(p.usual_time),
                p.window_minutes,
            )
        elif isinstance(p, SequencePattern) and p.usual_time:
            base = _hhmm_to_minutes(p.usual_time)
            win = getattr(p, "window_minutes", 30) or 30
            for step in p.steps:
                device, _, action = step.partition(":")
                if action == "OFF":
                    expected_off.setdefault(device, (p.pattern_id, base, win))

    for device in state.active_devices:
        if device not in expected_off or device in has_duration:
            continue
        pattern_id, off_min, window = expected_off[device]

        since_iso = state.device_on_since.get(device)
        since = _parse_since(since_iso) if since_iso else None

        if since is not None and since <= now:
            # We know exactly when the device turned on: it is "left on" only
            # once the first scheduled OFF *after it turned on* (plus the
            # departure grace) has passed. This handles real, persisted state.
            scheduled_off = _next_occurrence_at_or_after(since, off_min)
            if now < scheduled_off + grace:
                continue
        else:
            # What-if / unknown on-time (the "set the state + clock, hit Go"
            # flow sends no on-since timestamp). Judge purely on the clock with
            # an intuitive same-day comparison:
            #   * BEFORE the usual OFF time  -> being ON is normal, not flagged.
            #   * AFTER it (beyond the routine's own jitter window) -> the device
            #     should already be off, so it was "left on".
            # A same-day comparison keeps the result dynamic both ways and
            # avoids the cross-midnight wrap that used to (wrongly) flag a device
            # in the small hours and leave a dead zone right after the OFF time.
            now_min = _now_minutes(now)
            if now_min <= off_min + window:
                continue

        anomalies.append(
            Anomaly(
                type=AnomalyType.DEVICE_LEFT_ON,
                device=device,
                related_pattern_id=pattern_id,
                severity="high",
                detail=(
                    f"{device} is still ON; usually OFF by "
                    f"{off_min // 60:02d}:{off_min % 60:02d}."
                ),
            )
        )
    return anomalies


# ─── Detector 2: duration exceeded ───────────────────────────────────────────


def detect_duration_exceeded(
    state: HouseholdState,
    patterns: list[BasePattern],
    now: datetime,
) -> list[Anomaly]:
    """Fire when an active device has run far beyond its learned duration."""
    s = get_settings()
    now = _ensure_utc(now)
    dur_patterns = {p.device: p for p in patterns if isinstance(p, DurationPattern)}
    on_windows = _usual_on_window(patterns)
    anomalies: list[Anomaly] = []

    for device in state.active_devices:
        pattern = dur_patterns.get(device)
        if not pattern:
            continue

        since_iso = state.device_on_since.get(device)
        if since_iso:
            # We know exactly when it turned on (real / persisted state).
            since = _parse_since(since_iso)
        elif pattern.usual_start_time:
            # What-if / unknown on-time (the "set the state + clock, hit Go"
            # flow). Assume the device started at its usual start time today and
            # judge how long it has been running by the clock. If the clock is
            # earlier than the usual start, ``_elapsed_minutes`` clamps to 0 so
            # nothing fires (the run simply hasn't begun yet).
            start_min = _hhmm_to_minutes(pattern.usual_start_time)
            since = _at_time_of_day(now, start_min)
        else:
            continue

        running = _elapsed_minutes(since, now)
        threshold = pattern.usual_duration_minutes * s.duration_anomaly_factor
        if running <= threshold:
            continue

        detail = (
            f"{device} running {running:.0f} min; "
            f"usual ~{pattern.usual_duration_minutes:.0f} min."
        )
        # If the device also has a usual ON window and it started well outside
        # it, surface that — explains motor-in-the-evening style anomalies.
        window = on_windows.get(device)
        if window:
            on_min, tol = window
            since_min = since.hour * 60 + since.minute
            if abs(since_min - on_min) > tol + s.departure_grace_minutes:
                detail += (
                    f" Also outside its usual ON window of "
                    f"{on_min // 60:02d}:{on_min % 60:02d}."
                )
        anomalies.append(
            Anomaly(
                type=AnomalyType.DURATION_EXCEEDED,
                device=device,
                related_pattern_id=pattern.pattern_id,
                severity="high",
                detail=detail,
            )
        )
    return anomalies


# ─── Detector 3: device active too long (absolute safety-net) ────────────────


def detect_active_too_long(
    state: HouseholdState,
    patterns: list[BasePattern],
    now: datetime,
) -> list[Anomaly]:
    """Absolute safety-net: a device continuously active beyond
    ``max_continuous_active_minutes`` with NO learned duration pattern to judge
    it by (e.g. a door left open for a full day) is flagged regardless of any
    routine. Devices that *do* have a duration pattern are handled by
    :func:`detect_duration_exceeded` to avoid double-reporting.
    """
    s = get_settings()
    now = _ensure_utc(now)
    has_duration = {p.device for p in patterns if isinstance(p, DurationPattern)}
    anomalies: list[Anomaly] = []

    for device in state.active_devices:
        if device in has_duration:
            continue
        since_iso = state.device_on_since.get(device)
        if not since_iso:
            continue
        since = _parse_since(since_iso)
        running = _elapsed_minutes(since, now)
        if running > s.max_continuous_active_minutes:
            hours = running / 60.0
            anomalies.append(
                Anomaly(
                    type=AnomalyType.DEVICE_ACTIVE_TOO_LONG,
                    device=device,
                    severity="high",
                    detail=(
                        f"{device} has been active for {hours:.1f} h, "
                        f"far longer than expected."
                    ),
                )
            )
    return anomalies


# ─── Detector 4: missed routine (devices + people + medicine) ────────────────

# Actions that represent an *expected activation* — something the home expects
# to happen around a learned time each day. A device turning ON/OPEN, a person
# ARRIVE-ing, an elderly person's ACTIVE ping, or a medicine being TAKEN.
ROUTINE_ACTIVATIONS = {"ON", "OPEN", "ARRIVE", "ACTIVE", "TAKEN"}

# Map the missed activation's action to a specific, well-typed anomaly so the
# narrator can phrase a care alert ("Grandpa hasn't been active") differently
# from a plain device suggestion ("the porch light didn't turn on").
_MISSED_TYPE_BY_ACTION = {
    "ARRIVE": AnomalyType.MISSED_ARRIVAL,
    "ACTIVE": AnomalyType.INACTIVITY,
    "TAKEN": AnomalyType.MISSED_MEDICINE,
}
_CARE_TYPES = {
    AnomalyType.MISSED_ARRIVAL,
    AnomalyType.INACTIVITY,
    AnomalyType.MISSED_MEDICINE,
}


def _missed_detail(p: TimePattern, atype: AnomalyType) -> str:
    if atype is AnomalyType.INACTIVITY:
        return (
            f"No activity from {p.device} since the usual {p.usual_time}; "
            f"the routine appears to have been missed."
        )
    if atype is AnomalyType.MISSED_ARRIVAL:
        return (
            f"{p.device} usually arrives around {p.usual_time} "
            f"but hasn't returned today."
        )
    if atype is AnomalyType.MISSED_MEDICINE:
        return (
            f"The {p.usual_time} medicine routine ({p.device}) "
            f"has not been confirmed today."
        )
    return f"{p.device} usually {p.action} around {p.usual_time} but hasn't today."


def detect_missed_routine(
    state: HouseholdState,
    patterns: list[BasePattern],
    recent_events: list[Event],
    now: datetime,
) -> list[Anomaly]:
    """Fire when a high-confidence *activation* routine's window has passed today
    but the action never happened.

    This single detector covers four shapes of "an expected thing didn't occur":

      * a device that usually turns ON/OPEN didn't  -> ``missed_routine``
      * a person who usually ARRIVEs didn't (e.g. a child late from tuition)
        -> ``missed_arrival``
      * an elderly person's usual ACTIVE ping is absent -> ``inactivity``
      * a medicine usually TAKEN wasn't confirmed -> ``missed_medicine``

    Conservative by design so it complements (rather than duplicates)
    ``device_left_on``:

      * only activation actions (see ``ROUTINE_ACTIVATIONS``);
      * only confident patterns (``missed_routine_min_confidence``);
      * only for a bounded horizon after the window passes
        (``missed_routine_horizon_minutes``) so the signal is transient;
      * suppressed if the device is currently active or a matching event is
        present in today's recent events.
    """
    s = get_settings()
    now = _ensure_utc(now)
    now_min = _now_minutes(now)

    # (device, action) pairs that already happened on ``now``'s calendar day.
    todays: set[tuple[str, str]] = set()
    for e in recent_events:
        ets = _ensure_utc(e.timestamp)
        if ets.date() == now.date():
            todays.add((e.device_id, e.action.value))

    active = set(state.active_devices)
    anomalies: list[Anomaly] = []

    for p in patterns:
        if not isinstance(p, TimePattern) or p.action not in ROUTINE_ACTIVATIONS:
            continue
        if p.confidence < s.missed_routine_min_confidence:
            continue

        expected = _hhmm_to_minutes(p.usual_time)
        window_passed = expected + p.window_minutes + s.departure_grace_minutes
        # Only within a transient horizon after the window passes.
        if not (
            window_passed
            <= now_min
            <= window_passed + s.missed_routine_horizon_minutes
        ):
            continue
        # The routine did happen → not missed.
        if p.device in active or (p.device, p.action) in todays:
            continue

        atype = _MISSED_TYPE_BY_ACTION.get(p.action, AnomalyType.MISSED_ROUTINE)
        anomalies.append(
            Anomaly(
                type=atype,
                device=p.device,
                related_pattern_id=p.pattern_id,
                # People-safety misses are high severity; a device that simply
                # didn't switch on is a gentle suggestion.
                severity="high" if atype in _CARE_TYPES else "medium",
                detail=_missed_detail(p, atype),
            )
        )
    return anomalies


# ─── Detector 5: unexpected activity (off-schedule entry) ────────────────────


def detect_unexpected_activity(
    state: HouseholdState,
    patterns: list[BasePattern],
    recent_events: list[Event],
    now: datetime,
) -> list[Anomaly]:
    """Inverse of ``missed_routine``: fire when an ARRIVE/ACTIVE event *did*
    happen today but at a time well outside its learned window.

    This captures the Indian-household "domestic helper / caretaker entered the
    house outside the usual schedule" case (e.g. the maid normally arrives ~09:00
    but an arrival is detected at 02:30). It reads today's events from
    ``recent_events`` and compares each against the learned ARRIVE/ACTIVE time
    pattern for that exact ``(device, action)``.

    Only ARRIVE patterns are considered — an arrival (a person/helper entering)
    at an off-schedule hour is a genuine *security* signal. In the safety
    engine we deliberately do NOT flag a resident's own ACTIVE movement as a
    security event: an elderly person moving around at night is a health/care
    consideration, not an intruder, and is covered by other detectors.
    """
    s = get_settings()
    now = _ensure_utc(now)
    tolerance = s.departure_grace_minutes  # how far outside the window is "off-schedule"

    # (device, action) -> (pattern_id, usual_minute, window, usual_str)
    expected: dict[tuple[str, str], tuple[str, int, int, str]] = {}
    for p in patterns:
        if isinstance(p, TimePattern) and p.action == "ARRIVE":
            expected[(p.device, p.action)] = (
                p.pattern_id,
                _hhmm_to_minutes(p.usual_time),
                p.window_minutes,
                p.usual_time,
            )

    anomalies: list[Anomaly] = []
    flagged: set[tuple[str, str]] = set()
    for e in recent_events:
        key = (e.device_id, e.action.value)
        if key not in expected or key in flagged:
            continue
        ets = _ensure_utc(e.timestamp)
        if ets.date() != now.date():
            continue
        pattern_id, usual_min, window, usual_str = expected[key]
        ev_min = ets.hour * 60 + ets.minute
        if abs(ev_min - usual_min) <= window + tolerance:
            continue  # within the normal window → fine

        flagged.add(key)
        observed = f"{ets.hour:02d}:{ets.minute:02d}"
        anomalies.append(
            Anomaly(
                type=AnomalyType.UNEXPECTED_ACTIVITY,
                device=e.device_id,
                related_pattern_id=pattern_id,
                severity="high",
                detail=(
                    f"{e.device_id} detected at {observed}, well outside the "
                    f"usual {usual_str} schedule."
                ),
            )
        )
    return anomalies


# ─── Detector 6: global inactivity (elderly-alone safety net) ────────────────


def detect_global_inactivity(
    state: HouseholdState,
    recent_events: list[Event],
    now: datetime,
) -> list[Anomaly]:
    """Fire when there has been NO activity of any kind for a long stretch.

    Unlike ``detect_missed_routine`` (a specific learned routine didn't happen),
    this is an aggregate safety net for someone living alone: if no movement,
    presence, device toggle, or activity ping has been seen for hours, that is a
    concern regardless of any routine. The longer the silence, the higher the
    severity (warn -> emergency).

    Activity is measured from the most recent of: any event today, or any
    ``device_on_since`` timestamp (a device currently running counts as a sign
    of life). Only meaningful when someone is actually home.
    """
    s = get_settings()
    now = _ensure_utc(now)

    if not any(state.people_home.values()):
        return []  # nobody home -> silence is expected

    # Latest sign of life: newest recent event, or newest device_on_since.
    last_seen: datetime | None = None
    for e in recent_events:
        ets = _ensure_utc(e.timestamp)
        if ets <= now and (last_seen is None or ets > last_seen):
            last_seen = ets
    for since_iso in state.device_on_since.values():
        try:
            ts = _parse_since(since_iso)
        except (ValueError, TypeError):
            continue
        if ts <= now and (last_seen is None or ts > last_seen):
            last_seen = ts

    if last_seen is None:
        return []  # no data to judge

    quiet_minutes = max(0.0, (now - last_seen).total_seconds() / 60.0)
    if quiet_minutes < s.global_inactivity_warn_minutes:
        return []

    hours = quiet_minutes / 60.0
    severity = "high" if quiet_minutes < s.global_inactivity_emergency_minutes else "critical"
    return [
        Anomaly(
            type=AnomalyType.GLOBAL_INACTIVITY,
            device=None,
            severity=severity,
            detail=(
                f"No activity of any kind detected for about {hours:.1f} h while "
                f"someone is home — this may need a check-in."
            ),
        )
    ]


# ─── Detector 7: unsafe at night (open door/window overnight) ────────────────


def detect_unsafe_at_night(
    state: HouseholdState,
    now: datetime,
) -> list[Anomaly]:
    """Fire when a door or window is open during the night window.

    An open entry point overnight is a security concern; the safety overlay then
    escalates it further if a vulnerable person is home alone. Doors/windows are
    identified by id suffix (``_door`` / ``_window``) among active devices.
    """
    s = get_settings()
    now = _ensure_utc(now)
    hour = now.hour
    # Night spans midnight: e.g. 22:00 -> 06:00.
    is_night = (
        hour >= s.night_start_hour or hour < s.night_end_hour
        if s.night_start_hour > s.night_end_hour
        else s.night_start_hour <= hour < s.night_end_hour
    )
    if not is_night:
        return []

    anomalies: list[Anomaly] = []
    for device in state.active_devices:
        if device.endswith("_door") or device.endswith("_window"):
            kind = "window" if device.endswith("_window") else "door"
            anomalies.append(
                Anomaly(
                    type=AnomalyType.UNSAFE_AT_NIGHT,
                    device=device,
                    severity="high",
                    detail=(
                        f"The {device.replace('_', ' ')} is open at "
                        f"{now.hour:02d}:{now.minute:02d}, during the night."
                    ),
                )
            )
    return anomalies


# ─── Detector 8: health / SOS signals (from wearable ALERT/SOS events) ───────


def detect_health_signals(
    recent_events: list[Event],
    now: datetime,
) -> list[Anomaly]:
    """Turn today's wearable ALERT / SOS events into anomalies.

    A wearable adapter (or a panic button) ingests an event with action
    ``ALERT`` (a vital crossed a safe threshold, details in ``metadata``) or
    ``SOS`` (explicit help request). These are surfaced as the highest-priority
    anomalies and drive the EMERGENCY status in the overlay.
    """
    now = _ensure_utc(now)
    anomalies: list[Anomaly] = []
    seen: set[tuple[str, str]] = set()
    for e in recent_events:
        action = e.action.value
        if action not in {"ALERT", "SOS"}:
            continue
        ets = _ensure_utc(e.timestamp)
        if ets.date() != now.date() or ets > now:
            continue
        key = (e.device_id, action)
        if key in seen:
            continue
        seen.add(key)

        if action == "SOS":
            anomalies.append(
                Anomaly(
                    type=AnomalyType.SOS,
                    device=e.device_id,
                    severity="critical",
                    detail=f"SOS triggered from {e.device_id.replace('_', ' ')}.",
                )
            )
        else:
            meta = e.metadata or {}
            signal = meta.get("signal", "a vital sign")
            value = meta.get("value")
            threshold = meta.get("threshold", "")
            val_txt = f" ({signal} = {value}{', threshold ' + str(threshold) if threshold else ''})" if value is not None else f" ({signal})"
            anomalies.append(
                Anomaly(
                    type=AnomalyType.HEALTH_ALERT,
                    device=e.device_id,
                    severity="critical",
                    detail=f"A health reading is outside its safe range{val_txt}.",
                )
            )
    return anomalies


# ─── Orchestration ───────────────────────────────────────────────────────────


def detect_all(
    state: HouseholdState,
    patterns: list[BasePattern],
    recent_events: list[Event],
    now: datetime,
) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    anomalies.extend(detect_device_left_on(state, patterns, now))
    anomalies.extend(detect_duration_exceeded(state, patterns, now))
    anomalies.extend(detect_active_too_long(state, patterns, now))
    anomalies.extend(detect_missed_routine(state, patterns, recent_events, now))
    anomalies.extend(detect_unexpected_activity(state, patterns, recent_events, now))
    # --- Adaptive Safety Intelligence detectors ---
    anomalies.extend(detect_global_inactivity(state, recent_events, now))
    anomalies.extend(detect_unsafe_at_night(state, now))
    anomalies.extend(detect_health_signals(recent_events, now))
    return anomalies
