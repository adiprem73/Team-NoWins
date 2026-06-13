"""Context Builder — combines state, patterns, and events into a structured context object.

Also includes deterministic anomaly detection.
"""
from __future__ import annotations

from datetime import datetime, timezone

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import settings

from services.patterns.models import (
    Anomaly,
    AnomalyType,
    BasePattern,
    ContextObject,
    ContextType,
    DurationPattern,
    Event,
    HouseholdState,
    PatternType,
    RelevantPattern,
    SequencePattern,
    TimePattern,
)


# ─── Anomaly Detection ────────────────────────────────────────────────────

def _now_minutes(now: datetime) -> int:
    return now.hour * 60 + now.minute


def _hhmm_to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def detect_device_left_on(
    state: HouseholdState,
    patterns: list[BasePattern],
    now: datetime,
) -> list[Anomaly]:
    """Fire when a device that should be off (per a learned pattern) is still active."""
    now_min = _now_minutes(now)
    anomalies: list[Anomaly] = []

    expected_off: dict[str, tuple[str, int]] = {}

    for p in patterns:
        if isinstance(p, TimePattern) and p.action == "OFF":
            expected_off[p.device] = (p.pattern_id, _hhmm_to_minutes(p.usual_time))
        elif isinstance(p, SequencePattern) and p.usual_time:
            base = _hhmm_to_minutes(p.usual_time)
            for step in p.steps:
                device, _, action = step.partition(":")
                if action == "OFF":
                    expected_off.setdefault(device, (p.pattern_id, base))

    for device in state.active_devices:
        if device not in expected_off:
            continue
        pattern_id, expected_min = expected_off[device]
        if now_min > expected_min + settings.departure_grace_minutes:
            anomalies.append(
                Anomaly(
                    type=AnomalyType.DEVICE_LEFT_ON,
                    device=device,
                    related_pattern_id=pattern_id,
                    severity="high",
                    detail=(
                        f"{device} is still ON; usually OFF by "
                        f"{expected_min // 60:02d}:{expected_min % 60:02d}."
                    ),
                )
            )
    return anomalies


def detect_duration_exceeded(
    state: HouseholdState,
    patterns: list[BasePattern],
    now: datetime,
) -> list[Anomaly]:
    """Fire when an active device has run far beyond its learned duration."""
    dur_patterns = {
        p.device: p for p in patterns if isinstance(p, DurationPattern)
    }
    anomalies: list[Anomaly] = []

    for device in state.active_devices:
        pattern = dur_patterns.get(device)
        since_iso = state.device_on_since.get(device)
        if not pattern or not since_iso:
            continue
        since = datetime.fromisoformat(since_iso)
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        running = (now - since).total_seconds() / 60.0
        threshold = pattern.usual_duration_minutes * settings.duration_anomaly_factor
        if running > threshold:
            anomalies.append(
                Anomaly(
                    type=AnomalyType.DURATION_EXCEEDED,
                    device=device,
                    related_pattern_id=pattern.pattern_id,
                    severity="high",
                    detail=(
                        f"{device} running {running:.0f} min; "
                        f"usual ~{pattern.usual_duration_minutes:.0f} min."
                    ),
                )
            )
    return anomalies


def detect_all(
    state: HouseholdState,
    patterns: list[BasePattern],
    recent_events: list[Event],
    now: datetime,
) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    anomalies.extend(detect_device_left_on(state, patterns, now))
    anomalies.extend(detect_duration_exceeded(state, patterns, now))
    return anomalies


# ─── Context Builder ──────────────────────────────────────────────────────

def _pattern_description(p: BasePattern) -> str:
    if isinstance(p, SequencePattern):
        return p.description
    if isinstance(p, TimePattern):
        return f"{p.device} usually {p.action} around {p.usual_time}"
    return f"{p.pattern_type.value} pattern"


def _classify(anomalies: list[Anomaly]) -> ContextType:
    types = {a.type for a in anomalies}
    if AnomalyType.DEVICE_LEFT_ON in types or AnomalyType.MISSED_ROUTINE in types:
        return ContextType.DEPARTURE_ANOMALY
    if AnomalyType.DURATION_EXCEEDED in types:
        return ContextType.DURATION_ANOMALY
    return ContextType.NORMAL


def _select_relevant_patterns(
    patterns: list[BasePattern], anomalies: list[Anomaly]
) -> list[RelevantPattern]:
    related_ids = {a.related_pattern_id for a in anomalies if a.related_pattern_id}
    selected: list[BasePattern] = [p for p in patterns if p.pattern_id in related_ids]

    if not selected:
        selected = sorted(patterns, key=lambda p: p.confidence, reverse=True)[:5]

    return [
        RelevantPattern(
            pattern_id=p.pattern_id,
            pattern_type=p.pattern_type.value,
            description=_pattern_description(p),
            confidence=p.confidence,
        )
        for p in selected
    ]


def build_context(
    state: HouseholdState,
    patterns: list[BasePattern],
    recent_events: list[Event],
    now: datetime | None = None,
) -> ContextObject:
    now = now or datetime.now(timezone.utc)

    anomalies = detect_all(state, patterns, recent_events, now)
    context_type = _classify(anomalies)
    relevant = _select_relevant_patterns(patterns, anomalies)

    return ContextObject(
        context_type=context_type,
        household_id=state.household_id,
        current_time=f"{now.hour:02d}:{now.minute:02d}",
        people_home=state.people_home,
        active_devices=state.active_devices,
        relevant_patterns=relevant,
        anomalies=anomalies,
        recent_events=[
            {
                "timestamp": e.timestamp.isoformat(),
                "device_id": e.device_id,
                "action": e.action.value,
                "room": e.room,
                "triggered_by": e.triggered_by,
            }
            for e in sorted(recent_events, key=lambda e: e.timestamp, reverse=True)[:20]
        ],
    )
