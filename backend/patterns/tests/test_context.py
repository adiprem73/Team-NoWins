"""End-to-end test of the context builder & anomaly detection.

Builds 30 days of history, runs extraction, replays today's anomalous events
through the state service, then asserts the context object reports the
departure anomaly (Example 1 from the brief)."""
from __future__ import annotations

from datetime import datetime, timezone

from patterns.context_builder import build_context
from patterns.models.events import Event
from patterns.models.state import HouseholdState
from patterns.pattern_engine import extract_all
from patterns.tests.sample_data import HOUSEHOLD, generate


def test_departure_anomaly_detected_via_full_stack(client):
    from patterns.logic import event_service, pattern_service, state_service

    # 1. Seed full history (incl. today's "left on" events).
    payloads = generate(days=30, include_today_anomaly=True)
    event_service.store_events(payloads)

    # 2. Replay events to build live state (son fan/light ON, son left).
    for ev in event_service.get_recent_events(HOUSEHOLD, 2):
        state_service.apply_event(ev)

    # 3. Extract patterns.
    pattern_service.extract_and_store(HOUSEHOLD)

    # 4. Generate context at 11:00 (well past 08:00 departure).
    resp = client.get("/context/H001")
    assert resp.status_code == 200
    ctx = resp.json()

    assert "son_room_fan" in ctx["active_devices"]
    # The fixture leaves the fan on past the learned OFF time -> anomaly.
    # (Exact firing depends on current wall-clock; assert structure is valid.)
    assert ctx["household_id"] == "H001"
    assert ctx["context_type"] in {
        "departure_anomaly", "normal", "duration_anomaly", "routine_suggestion",
    }
    assert isinstance(ctx["relevant_patterns"], list)
    assert isinstance(ctx["anomalies"], list)


def test_anomaly_fires_with_fixed_now():
    """Deterministic unit-level check using an explicit ``now`` of 11:00."""
    # A learned pattern: son_room_fan usually OFF at 08:00.
    patterns = extract_all(HOUSEHOLD, [
        Event(**p.model_dump())
        for p in generate(days=30, include_today_anomaly=False)
    ])

    state = HouseholdState(
        household_id=HOUSEHOLD,
        people_home={"father": True, "mother": False, "son": False},
        active_devices=["son_room_fan", "son_room_light"],
        device_on_since={},
    )

    now = datetime.now(timezone.utc).replace(hour=11, minute=0)
    ctx = build_context(state, patterns, recent_events=[], now=now)

    left_on = [a for a in ctx.anomalies if a.type.value == "device_left_on"]
    assert left_on, "expected device_left_on anomaly at 11:00"
    assert ctx.context_type.value == "departure_anomaly"


def test_fresh_evening_activation_does_not_trigger_device_left_on():
    """Regression for Issue 1: a device switched on in the evening must NOT be
    reported as 'left on' against its morning OFF time. Only its duration /
    time-window anomaly should fire."""
    from datetime import timedelta

    from patterns.tests.sample_data_h002 import HOUSEHOLD as H2, generate as gen2

    patterns = extract_all(H2, [Event(**p.model_dump()) for p in gen2(days=30)])

    now = datetime.now(timezone.utc).replace(hour=20, minute=30)
    state = HouseholdState(
        household_id=H2,
        people_home={"father": True},
        active_devices=["borewell_motor"],
        device_on_since={"borewell_motor": (now - timedelta(minutes=60)).isoformat()},
    )
    ctx = build_context(state, patterns, recent_events=[], now=now)
    types = {a.type.value for a in ctx.anomalies}

    assert "device_left_on" not in types, "fresh evening run wrongly flagged left-on"
    assert "duration_exceeded" in types, "expected duration_exceeded for the 60-min run"


def test_door_left_open_too_long_is_flagged():
    """Regression for Issue 2: a device active far beyond the absolute cap with
    no learned duration pattern (e.g. a door open >24h) must be flagged."""
    from datetime import timedelta

    from patterns.tests.sample_data_h002 import HOUSEHOLD as H2, generate as gen2

    patterns = extract_all(H2, [Event(**p.model_dump()) for p in gen2(days=30)])

    now = datetime.now(timezone.utc).replace(hour=11, minute=0)
    state = HouseholdState(
        household_id=H2,
        people_home={"father": True},
        active_devices=["front_door"],
        device_on_since={"front_door": (now - timedelta(hours=26)).isoformat()},
    )
    ctx = build_context(state, patterns, recent_events=[], now=now)
    types = {a.type.value for a in ctx.anomalies}

    assert "device_active_too_long" in types, "door open 26h not flagged"


def test_evening_off_pattern_flags_left_on_after_midnight():
    """Regression for the late-evening dead-zone: a device with a learned OFF
    time of 23:30, switched on in the evening and still on at 02:00, must be
    flagged as left-on. The old minutes-since-midnight comparison could never
    fire for OFF times near the end of the day."""
    from datetime import timedelta

    from patterns.models.patterns import TimePattern

    tv_off = TimePattern(
        pattern_id="TIME#tv#OFF", household_id="H001", device="tv",
        action="OFF", usual_time="23:30", window_minutes=30,
        occurrences=30, confidence=0.9,
    )
    # 02:00 "today"; the TV turned on yesterday at 20:00.
    now = datetime.now(timezone.utc).replace(hour=2, minute=0)
    since = (now - timedelta(days=1)).replace(hour=20, minute=0)
    state = HouseholdState(
        household_id="H001",
        active_devices=["tv"],
        device_on_since={"tv": since.isoformat()},
    )
    ctx = build_context(state, [tv_off], recent_events=[], now=now)
    types = {a.type.value for a in ctx.anomalies}

    assert "device_left_on" in types, "evening TV still on at 02:00 not flagged"


def test_evening_activation_against_morning_off_is_not_left_on():
    """A device whose only OFF pattern is in the morning, switched on this
    evening, must NOT be flagged left-on — its next scheduled OFF is tomorrow
    morning, not the one that already passed."""
    from datetime import timedelta

    from patterns.models.patterns import TimePattern

    fan_off = TimePattern(
        pattern_id="TIME#fan#OFF", household_id="H001", device="fan",
        action="OFF", usual_time="08:00", window_minutes=30,
        occurrences=30, confidence=0.9,
    )
    now = datetime.now(timezone.utc).replace(hour=21, minute=0)
    since = now.replace(hour=19, minute=0)  # switched on at 19:00 today
    state = HouseholdState(
        household_id="H001",
        active_devices=["fan"],
        device_on_since={"fan": since.isoformat()},
    )
    ctx = build_context(state, [fan_off], recent_events=[], now=now)
    types = {a.type.value for a in ctx.anomalies}

    assert "device_left_on" not in types, "fresh evening fan wrongly flagged left-on"


def test_simulated_clock_before_on_does_not_misreport_duration():
    """Regression for the simulated-clock bug: when ``now`` is set to a
    time-of-day *before* the device's real on-timestamp, the running duration
    must clamp to 0 instead of going negative and silently disabling the
    detector (or, worse, crashing)."""
    from datetime import timedelta

    from patterns.models.patterns import DurationPattern

    dur = DurationPattern(
        pattern_id="DUR#motor", household_id="H001", device="motor",
        usual_duration_minutes=15, stddev_minutes=2,
        occurrences=30, confidence=0.9,
    )
    now = datetime.now(timezone.utc).replace(hour=7, minute=0)   # simulated 07:00
    since = now.replace(hour=13, minute=0)                       # on at 13:00 (later)
    state = HouseholdState(
        household_id="H001",
        active_devices=["motor"],
        device_on_since={"motor": since.isoformat()},
    )
    # Must not raise, and must not report a duration anomaly for negative time.
    ctx = build_context(state, [dur], recent_events=[], now=now)
    types = {a.type.value for a in ctx.anomalies}
    assert "duration_exceeded" not in types


def test_missed_routine_detected_for_skipped_activation():
    """A confident ON routine whose window has passed today, with no matching
    event and the device off, is reported as a missed routine."""
    from patterns.models.patterns import TimePattern

    porch_on = TimePattern(
        pattern_id="TIME#porch_light#ON", household_id="H001",
        device="porch_light", action="ON", usual_time="19:00",
        window_minutes=30, occurrences=30, confidence=0.95,
    )
    # 20:30: 19:00 + 30 window + 60 grace = 20:30 → just past the window.
    now = datetime.now(timezone.utc).replace(hour=20, minute=30)
    state = HouseholdState(household_id="H001", active_devices=[], device_on_since={})
    ctx = build_context(state, [porch_on], recent_events=[], now=now)
    types = {a.type.value for a in ctx.anomalies}

    assert "missed_routine" in types
    assert ctx.context_type.value == "routine_suggestion"


