"""Pydantic models for learned household patterns.

Patterns are produced *deterministically* by the pattern engine — never by an
LLM. Each pattern is a compact, reusable statement of recurring behaviour with
an attached confidence score.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class PatternType(str, Enum):
    TIME_BASED = "time_based"      # device usually toggled around a clock time
    SEQUENCE = "sequence"          # ordered chain of events (e.g. departure)
    DURATION = "duration"          # device normally runs for ~N minutes


class BasePattern(BaseModel):
    pattern_id: str
    household_id: str
    pattern_type: PatternType
    confidence: float = Field(ge=0.0, le=1.0)
    occurrences: int = Field(ge=0, description="Support count over the window.")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TimePattern(BasePattern):
    """e.g. 'living_room_light turns ON around 19:00'."""

    pattern_type: PatternType = PatternType.TIME_BASED
    device: str
    action: str                      # ON / OFF / OPEN ...
    usual_time: str                  # "HH:MM" local clock
    window_minutes: int = 30         # +/- tolerance around usual_time


class SequencePattern(BasePattern):
    """e.g. door OPEN -> fan OFF -> light OFF ('son leaves for college')."""

    pattern_type: PatternType = PatternType.SEQUENCE
    description: str
    # Ordered list of "device:action" steps.
    steps: list[str]
    usual_time: str | None = None    # typical time-of-day the sequence starts


class DurationPattern(BasePattern):
    """e.g. 'water_motor normally runs ~15 minutes, usually starting ~09:00'."""

    pattern_type: PatternType = PatternType.DURATION
    device: str
    usual_duration_minutes: float
    stddev_minutes: float = 0.0
    usual_start_time: str | None = None   # "HH:MM" the device typically turns on


# Discriminated-union helper for (de)serialisation.
def pattern_from_item(item: dict) -> BasePattern:
    ptype = item["pattern_type"]
    if ptype == PatternType.TIME_BASED.value:
        return TimePattern(**item)
    if ptype == PatternType.SEQUENCE.value:
        return SequencePattern(**item)
    if ptype == PatternType.DURATION.value:
        return DurationPattern(**item)
    raise ValueError(f"Unknown pattern_type: {ptype}")


def pattern_to_item(pattern: BasePattern) -> dict:
    item = pattern.model_dump(mode="json")
    # DynamoDB-friendly ISO timestamp.
    item["last_updated"] = pattern.last_updated.astimezone(timezone.utc).isoformat()
    return item
