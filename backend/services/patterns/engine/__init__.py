"""Deterministic pattern engine."""
from __future__ import annotations

from services.patterns.models import Event, BasePattern
from services.patterns.engine.duration import extract_duration_patterns
from services.patterns.engine.sequence_based import extract_sequence_patterns
from services.patterns.engine.time_based import extract_time_patterns


def extract_all(household_id: str, events: list[Event]) -> list[BasePattern]:
    patterns: list[BasePattern] = []
    patterns.extend(extract_time_patterns(household_id, events))
    patterns.extend(extract_sequence_patterns(household_id, events))
    patterns.extend(extract_duration_patterns(household_id, events))
    return patterns


__all__ = [
    "extract_all",
    "extract_time_patterns",
    "extract_sequence_patterns",
    "extract_duration_patterns",
]
