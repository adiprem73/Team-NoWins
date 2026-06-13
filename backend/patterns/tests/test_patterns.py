"""Tests for the deterministic pattern engine over synthetic 30-day data."""
from __future__ import annotations

from patterns.models.patterns import DurationPattern, PatternType, SequencePattern, TimePattern
from patterns.pattern_engine import extract_all
from patterns.tests.sample_data import HOUSEHOLD, generate


def _materialise(payloads):
    from patterns.models.events import Event

    return [Event(**p.model_dump()) for p in payloads]


def test_extracts_time_pattern_for_porch_light():
    events = _materialise(generate(days=30, include_today_anomaly=False))
    patterns = extract_all(HOUSEHOLD, events)

    porch = [
        p for p in patterns
        if isinstance(p, TimePattern) and p.device == "porch_light" and p.action == "ON"
    ]
    assert porch, "expected a time pattern for porch_light ON"
    assert porch[0].usual_time.startswith("19:")
    assert porch[0].confidence >= 0.6


def test_extracts_duration_pattern_for_water_motor():
    events = _materialise(generate(days=30, include_today_anomaly=False))
    patterns = extract_all(HOUSEHOLD, events)

    motor = [
        p for p in patterns
        if isinstance(p, DurationPattern) and p.device == "water_motor"
    ]
    assert motor, "expected a duration pattern for water_motor"
    assert 12 <= motor[0].usual_duration_minutes <= 18


def test_extracts_departure_sequence():
    events = _materialise(generate(days=30, include_today_anomaly=False))
    patterns = extract_all(HOUSEHOLD, events)

    sequences = [p for p in patterns if isinstance(p, SequencePattern)]
    assert sequences, "expected at least one sequence pattern"
    # The departure burst (LEAVE -> fan OFF -> light OFF) should be captured.
    found = any(
        any("son_room_fan:OFF" in step for step in s.steps) for s in sequences
    )
    assert found


def test_confidence_bounds():
    events = _materialise(generate(days=30, include_today_anomaly=False))
    for p in extract_all(HOUSEHOLD, events):
        assert 0.0 <= p.confidence <= 1.0
        assert p.pattern_type in set(PatternType)
