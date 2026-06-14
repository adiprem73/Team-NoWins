"""Tests for the Indian-context event kinds and care/security detectors (H003).

Covers the new event streams (elderly activity, child return, medicine,
domestic-helper schedule) end to end: deterministic pattern extraction +
the new anomaly detectors (inactivity, missed arrival, missed medicine,
unexpected off-schedule entry) and the resulting context classification.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from patterns.context_builder import build_context
from patterns.context_builder.anomaly import ROUTINE_ACTIVATIONS
from patterns.models.context import AnomalyType, ContextType
from patterns.models.events import DeviceAction, DeviceType, Event
from patterns.models.patterns import DurationPattern, SequencePattern, TimePattern
from patterns.models.state import HouseholdState
from patterns.pattern_engine import extract_all
from patterns.tests.sample_data_h003 import HOUSEHOLD, generate


def _materialise(payloads):
    return [Event(**p.model_dump()) for p in payloads]


def _mins(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def _assert_near(usual_time: str, target_hhmm: str, tol: int = 25) -> None:
    """Assert a learned ``HH:MM`` is within ``tol`` minutes of a target time.

    The seeds add per-day jitter, so the clustered mean lands close to — but not
    exactly on — the nominal time (e.g. 20:58 for a ~21:00 routine).
    """
    assert abs(_mins(usual_time) - _mins(target_hhmm)) <= tol, (
        f"{usual_time} not within {tol} min of {target_hhmm}"
    )


def _clean_history():
    return _materialise(
        generate(
            days=30,
            include_unexpected_entry=False,
            include_motor_anomaly=False,
            include_left_on=False,
        )
    )


def _patterns():
    return extract_all(HOUSEHOLD, _clean_history())


def _today_satisfied(patterns, now: datetime, skip: str | None) -> list[Event]:
    """Today's activation events for every routine except ``skip``."""
    out: list[Event] = []
    for p in patterns:
        if not isinstance(p, TimePattern) or p.action not in ROUTINE_ACTIVATIONS:
            continue
        if p.device == skip:
            continue
        h, m = map(int, p.usual_time.split(":"))
        out.append(
            Event(
                household_id=HOUSEHOLD,
                device_id=p.device,
                device_type=DeviceType.OTHER,
                room="x",
                action=DeviceAction(p.action),
                triggered_by="x",
                timestamp=now.replace(hour=h, minute=m, second=0, microsecond=0),
            )
        )
    return out


# ─── Pattern extraction ──────────────────────────────────────────────────────


def test_extracts_activity_time_pattern_for_grandpa():
    patterns = _patterns()
    grandpa = [
        p for p in patterns
        if isinstance(p, TimePattern)
        and p.device == "grandpa_activity"
        and p.action == "ACTIVE"
    ]
    assert grandpa, "expected a time pattern for grandpa_activity ACTIVE"
    _assert_near(grandpa[0].usual_time, "06:45")
    assert grandpa[0].confidence >= 0.6


def test_extracts_arrival_patterns_for_child_and_helper():
    patterns = _patterns()
    by_device = {
        (p.device, p.action): p
        for p in patterns
        if isinstance(p, TimePattern) and p.action == "ARRIVE"
    }
    assert ("ananya_presence", "ARRIVE") in by_device
    assert ("maid_presence", "ARRIVE") in by_device
    _assert_near(by_device[("ananya_presence", "ARRIVE")].usual_time, "18:15")
    _assert_near(by_device[("maid_presence", "ARRIVE")].usual_time, "09:00")


def test_extracts_medicine_time_pattern():
    patterns = _patterns()
    med = [
        p for p in patterns
        if isinstance(p, TimePattern)
        and p.device == "grandma_medicine"
        and p.action == "TAKEN"
    ]
    assert med, "expected a time pattern for grandma_medicine TAKEN"
    _assert_near(med[0].usual_time, "21:00")


def test_extracts_pooja_sequence_and_motor_duration():
    patterns = _patterns()
    sequences = [p for p in patterns if isinstance(p, SequencePattern)]
    assert any(
        any("pooja_lamp:ON" in step for step in s.steps) for s in sequences
    ), "expected the morning pooja sequence"

    motor = [
        p for p in patterns
        if isinstance(p, DurationPattern) and p.device == "water_motor"
    ]
    assert motor and 12 <= motor[0].usual_duration_minutes <= 18


# ─── Care / safety detectors ─────────────────────────────────────────────────


def _now(hour: int, minute: int = 0) -> datetime:
    return datetime.now(timezone.utc).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )


def test_inactivity_anomaly_when_grandpa_inactive():
    patterns = _patterns()
    now = _now(10, 0)
    state = HouseholdState(household_id=HOUSEHOLD, people_home={"grandpa": True})
    ctx = build_context(
        state, patterns, _today_satisfied(patterns, now, skip="grandpa_activity"), now=now
    )
    assert ctx.context_type == ContextType.CARE_ALERT
    assert any(a.type == AnomalyType.INACTIVITY for a in ctx.anomalies)


def test_missed_arrival_anomaly_when_child_not_home():
    patterns = _patterns()
    now = _now(20, 0)
    state = HouseholdState(household_id=HOUSEHOLD, people_home={"ananya": False})
    ctx = build_context(
        state, patterns, _today_satisfied(patterns, now, skip="ananya_presence"), now=now
    )
    assert ctx.context_type == ContextType.CARE_ALERT
    assert any(a.type == AnomalyType.MISSED_ARRIVAL for a in ctx.anomalies)


def test_missed_medicine_anomaly():
    patterns = _patterns()
    now = _now(22, 45)
    state = HouseholdState(household_id=HOUSEHOLD, people_home={"grandma": True})
    ctx = build_context(
        state, patterns, _today_satisfied(patterns, now, skip="grandma_medicine"), now=now
    )
    assert ctx.context_type == ContextType.CARE_ALERT
    assert any(a.type == AnomalyType.MISSED_MEDICINE for a in ctx.anomalies)


def test_unexpected_activity_when_helper_arrives_off_schedule():
    patterns = _patterns()
    now = _now(3, 0)
    odd_entry = Event(
        household_id=HOUSEHOLD, device_id="maid_presence",
        device_type=DeviceType.PRESENCE, room="entrance",
        action=DeviceAction.ARRIVE, triggered_by="maid",
        timestamp=now.replace(hour=2, minute=30),
    )
    state = HouseholdState(household_id=HOUSEHOLD, people_home={"maid": True})
    ctx = build_context(state, patterns, [odd_entry], now=now)
    assert ctx.context_type == ContextType.SECURITY_ALERT
    assert any(a.type == AnomalyType.UNEXPECTED_ACTIVITY for a in ctx.anomalies)


def test_on_schedule_helper_arrival_is_not_flagged():
    patterns = _patterns()
    now = _now(9, 5)
    on_time = Event(
        household_id=HOUSEHOLD, device_id="maid_presence",
        device_type=DeviceType.PRESENCE, room="entrance",
        action=DeviceAction.ARRIVE, triggered_by="maid",
        timestamp=now.replace(hour=9, minute=5),
    )
    state = HouseholdState(household_id=HOUSEHOLD, people_home={"maid": True})
    ctx = build_context(state, patterns, [on_time], now=now)
    assert not any(a.type == AnomalyType.UNEXPECTED_ACTIVITY for a in ctx.anomalies)
