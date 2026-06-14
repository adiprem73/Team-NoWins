"""Context Builder — the heart of the MVP.

Combines the live household state, the learned patterns, and a tail of recent
events into a single structured :class:`ContextObject`. This object is the
hand-off boundary to Amazon Bedrock (future phase). We deliberately stop here.

Pipeline
========
1. Take current state (who's home, active devices).
2. Take learned patterns for the home.
3. Take recent events (short-term memory).
4. Run deterministic anomaly detectors.
5. Classify an overall ``context_type`` from the detected anomalies.
6. Select the patterns relevant to those anomalies (plus high-confidence ones).
7. Emit the validated ContextObject.
"""
from __future__ import annotations

from datetime import datetime, timezone

from safety.context_builder.anomaly import detect_all
from safety.models.context import (
    Anomaly,
    AnomalyType,
    ContextObject,
    ContextType,
    RelevantPattern,
)
from safety.models.events import Event
from safety.models.patterns import (
    BasePattern,
    DurationPattern,
    SequencePattern,
    TimePattern,
)
from safety.models.state import HouseholdState


def _pattern_description(p: BasePattern) -> str:
    if isinstance(p, SequencePattern):
        when = f" around {p.usual_time}" if p.usual_time else ""
        return f"{p.description}{when}"
    if isinstance(p, TimePattern):
        return f"{p.device} usually {p.action} around {p.usual_time}"
    if isinstance(p, DurationPattern):
        when = f" starting around {p.usual_start_time}" if p.usual_start_time else ""
        return (
            f"{p.device} usually runs ~{p.usual_duration_minutes:.0f} min{when}"
        )
    return f"{p.pattern_type.value} pattern"


def _pattern_time(p: BasePattern) -> str | None:
    """The clock time a pattern is anchored to, when one exists."""
    if isinstance(p, TimePattern):
        return p.usual_time
    if isinstance(p, SequencePattern):
        return p.usual_time
    if isinstance(p, DurationPattern):
        return p.usual_start_time
    return None


def _classify(anomalies: list[Anomaly]) -> ContextType:
    """Pick the most salient context type from the detected anomalies.

    Priority (most to least urgent):
      1. an off-schedule entry (security) — a person/helper active when they
         shouldn't be outranks everything;
      2. a people-safety miss (care) — elderly inactivity, missed medicine, a
         child who hasn't returned;
      3. a device left on (departure);
      4. an over-running / too-long device (duration);
      5. a merely missed device routine (suggestion).
    """
    types = {a.type for a in anomalies}
    # --- Adaptive Safety Intelligence (highest urgency) ---
    if types & {AnomalyType.SOS, AnomalyType.HEALTH_ALERT, AnomalyType.GLOBAL_INACTIVITY}:
        return ContextType.EMERGENCY
    if AnomalyType.UNSAFE_AT_NIGHT in types:
        return ContextType.SAFETY_ALERT
    if AnomalyType.UNEXPECTED_ACTIVITY in types:
        return ContextType.SECURITY_ALERT
    if types & {
        AnomalyType.INACTIVITY,
        AnomalyType.MISSED_MEDICINE,
        AnomalyType.MISSED_ARRIVAL,
    }:
        return ContextType.CARE_ALERT
    if AnomalyType.DEVICE_LEFT_ON in types:
        return ContextType.DEPARTURE_ANOMALY
    if (
        AnomalyType.DURATION_EXCEEDED in types
        or AnomalyType.DEVICE_ACTIVE_TOO_LONG in types
    ):
        return ContextType.DURATION_ANOMALY
    if AnomalyType.MISSED_ROUTINE in types:
        return ContextType.ROUTINE_SUGGESTION
    return ContextType.NORMAL


def _select_relevant_patterns(
    patterns: list[BasePattern], anomalies: list[Anomaly]
) -> list[RelevantPattern]:
    related_ids = {a.related_pattern_id for a in anomalies if a.related_pattern_id}
    selected: list[BasePattern] = [p for p in patterns if p.pattern_id in related_ids]

    # Always include the strongest patterns so Bedrock has routine context even
    # when nothing is anomalous.
    if not selected:
        selected = sorted(patterns, key=lambda p: p.confidence, reverse=True)[:5]

    return [
        RelevantPattern(
            pattern_id=p.pattern_id,
            pattern_type=p.pattern_type.value,
            description=_pattern_description(p),
            confidence=p.confidence,
            time=_pattern_time(p),
        )
        for p in selected
    ]


def build_context(
    state: HouseholdState,
    patterns: list[BasePattern],
    recent_events: list[Event],
    now: datetime | None = None,
    *,
    profiles: dict | None = None,
) -> ContextObject:
    now = now or datetime.now(timezone.utc)

    anomalies = detect_all(state, patterns, recent_events, now)
    context_type = _classify(anomalies)
    relevant = _select_relevant_patterns(patterns, anomalies)

    context = ContextObject(
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

    # --- Adaptive Safety Intelligence overlay ---
    # Re-interpret the detected anomalies through a vulnerability lens and attach
    # a deterministic SafetyAssessment. Occupants = who is currently home.
    #
    # Residents (anyone with a PersonProfile) are considered HOME by default —
    # an elderly couple who live here are home unless a presence event explicitly
    # marked them away. This is what makes vulnerability escalation work even
    # though residents never "ARRIVE" at their own home.
    from safety.context_builder import safety_overlay

    people = state.people_home or {}
    explicit_home = {p for p, home in people.items() if home}
    explicit_away = {p for p, home in people.items() if home is False}
    resident_home = {pid for pid in (profiles or {}) if pid not in explicit_away}
    occupants = sorted(explicit_home | resident_home)

    context = safety_overlay.assess(
        context, occupants=occupants, profiles=profiles or {}
    )
    return context
