"""Tests for the Adaptive Safety engine: routine learning + the vulnerability
overlay (severity escalation, safety score/status) + the new safety detectors.

Uses the in-process pieces directly (no DynamoDB) for the overlay/detector
checks, mirroring the patterns engine's test style.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from safety.context_builder import build_context
from safety.context_builder.safety_overlay import resolve_vulnerability
from safety.models.context import AnomalyType, ContextType
from safety.models.events import DeviceAction, DeviceType, Event
from safety.models.patterns import TimePattern
from safety.models.safety import PersonProfile, SafetyStatus, Vulnerability
from safety.models.state import HouseholdState
from safety.pattern_engine import extract_all
from safety.tests.sample_data_elderly import HOUSEHOLD, generate, profiles


def _materialise(payloads):
    return [Event(**p.model_dump()) for p in payloads]


def _profiles_map():
    return {p.person_id: p for p in profiles()}


# ─── Routine learning ────────────────────────────────────────────────────────


def test_learns_elderly_routines():
    events = _materialise(generate(days=30))
    patterns = extract_all(HOUSEHOLD, events)
    # Wake activity, medicine, and the pooja sequence should all be learned.
    times = {
        (p.device, p.action)
        for p in patterns
        if isinstance(p, TimePattern)
    }
    assert ("grandpa_activity", "ACTIVE") in times
    assert ("grandpa_medicine", "TAKEN") in times


# ─── Vulnerability resolution ────────────────────────────────────────────────


def test_elderly_alone_factor_is_high():
    profs = _profiles_map()
    factor, most, alone = resolve_vulnerability(["grandpa", "grandma"], profs)
    assert factor == 2.0          # elderly weight
    assert alone is True
    assert most in {"grandpa", "grandma"}


def test_capable_adult_mitigates():
    profs = _profiles_map()
    profs["son"] = PersonProfile(
        person_id="son", display_name="Son", vulnerability=Vulnerability.NORMAL
    )
    factor, most, alone = resolve_vulnerability(["grandpa", "son"], profs)
    assert alone is False         # a capable adult is present
    assert factor < 2.0           # risk mitigated


# ─── Severity escalation (the door/window example) ───────────────────────────


def test_unsafe_at_night_escalates_for_elderly_alone():
    profs = _profiles_map()
    now = datetime.now(timezone.utc).replace(hour=2, minute=0, second=0, microsecond=0)
    state = HouseholdState(
        household_id=HOUSEHOLD,
        active_devices=["bedroom_window"],
        device_on_since={"bedroom_window": (now - timedelta(hours=1)).isoformat()},
        people_home={},  # residents inferred from profiles
    )
    ctx = build_context(state, [], [], now=now, profiles=profs)
    night = [a for a in ctx.anomalies if a.type == AnomalyType.UNSAFE_AT_NIGHT]
    assert night, "expected an unsafe-at-night anomaly"
    # Base high -> escalated to critical by the x2 elderly-alone factor.
    assert night[0].base_severity == "high"
    assert night[0].severity == "critical"
    assert ctx.safety is not None
    assert ctx.safety.vulnerable_alone is True


def test_sos_event_is_emergency():
    profs = _profiles_map()
    now = datetime.now(timezone.utc)
    sos = Event(
        household_id=HOUSEHOLD, device_id="grandpa_wearable",
        device_type=DeviceType.WEARABLE, room="living_room",
        action=DeviceAction.SOS, triggered_by="grandpa",
        timestamp=now - timedelta(minutes=2),
    )
    state = HouseholdState(household_id=HOUSEHOLD, people_home={})
    ctx = build_context(state, [], [sos], now=now, profiles=profs)
    assert any(a.type == AnomalyType.SOS for a in ctx.anomalies)
    assert ctx.context_type == ContextType.EMERGENCY
    assert ctx.safety.status == SafetyStatus.EMERGENCY


def test_normal_home_is_safe():
    profs = _profiles_map()
    now = datetime.now(timezone.utc).replace(hour=12, minute=0)
    # A recent activity ping so nothing looks inactive.
    ping = Event(
        household_id=HOUSEHOLD, device_id="grandpa_activity",
        device_type=DeviceType.ACTIVITY, room="living_room",
        action=DeviceAction.ACTIVE, triggered_by="grandpa",
        timestamp=now - timedelta(minutes=20),
    )
    state = HouseholdState(household_id=HOUSEHOLD, active_devices=[], people_home={})
    ctx = build_context(state, [], [ping], now=now, profiles=profs)
    assert ctx.safety.status == SafetyStatus.SAFE
    assert ctx.safety.safety_score == 100.0
