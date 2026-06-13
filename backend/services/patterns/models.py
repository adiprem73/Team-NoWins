"""Merged models for pattern recognition service.

Combines: events, patterns, state, and context models.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


# ─── Events ────────────────────────────────────────────────────────────────

class DeviceAction(str, Enum):
    ON = "ON"
    OFF = "OFF"
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    ARRIVE = "ARRIVE"
    LEAVE = "LEAVE"


class DeviceType(str, Enum):
    FAN = "fan"
    LIGHT = "light"
    AC = "ac"
    TV = "tv"
    DOOR = "door"
    MOTOR = "motor"
    PRESENCE = "presence"
    OTHER = "other"


class EventCreate(BaseModel):
    household_id: str = Field(..., examples=["H001"])
    device_id: str = Field(..., examples=["son_room_fan"])
    device_type: DeviceType
    room: str = Field(..., examples=["son_room"])
    action: DeviceAction
    triggered_by: str = Field(
        default="system",
        description="Person or automation that caused the event.",
        examples=["son"],
    )
    timestamp: datetime | None = Field(
        default=None,
        description="ISO-8601 UTC time. Defaults to server time if omitted.",
    )
    metadata: dict | None = None

    @field_validator("timestamp")
    @classmethod
    def _ensure_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        return v.astimezone(timezone.utc) if v.tzinfo else v.replace(tzinfo=timezone.utc)


class Event(EventCreate):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_item(self) -> dict:
        item = {
            "household_id": self.household_id,
            "event_id": self.event_id,
            "timestamp": self.timestamp.astimezone(timezone.utc).isoformat(),
            "device_id": self.device_id,
            "device_type": self.device_type.value,
            "room": self.room,
            "action": self.action.value,
            "triggered_by": self.triggered_by,
        }
        if self.metadata:
            item["metadata"] = self.metadata
        return item

    @classmethod
    def from_item(cls, item: dict) -> "Event":
        return cls(
            event_id=item["event_id"],
            household_id=item["household_id"],
            timestamp=datetime.fromisoformat(item["timestamp"]),
            device_id=item["device_id"],
            device_type=item["device_type"],
            room=item["room"],
            action=item["action"],
            triggered_by=item.get("triggered_by", "system"),
            metadata=item.get("metadata"),
        )


# ─── Patterns ──────────────────────────────────────────────────────────────

class PatternType(str, Enum):
    TIME_BASED = "time_based"
    SEQUENCE = "sequence"
    DURATION = "duration"


class BasePattern(BaseModel):
    pattern_id: str
    household_id: str
    pattern_type: PatternType
    confidence: float = Field(ge=0.0, le=1.0)
    occurrences: int = Field(ge=0, description="Support count over the window.")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TimePattern(BasePattern):
    pattern_type: PatternType = PatternType.TIME_BASED
    device: str
    action: str
    usual_time: str  # "HH:MM"
    window_minutes: int = 30


class SequencePattern(BasePattern):
    pattern_type: PatternType = PatternType.SEQUENCE
    description: str
    steps: list[str]
    usual_time: str | None = None


class DurationPattern(BasePattern):
    pattern_type: PatternType = PatternType.DURATION
    device: str
    usual_duration_minutes: float
    stddev_minutes: float = 0.0


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
    item["last_updated"] = pattern.last_updated.astimezone(timezone.utc).isoformat()
    return item


# ─── Household State ───────────────────────────────────────────────────────

class HouseholdState(BaseModel):
    household_id: str = Field(..., examples=["H001"])
    people_home: dict[str, bool] = Field(default_factory=dict)
    active_devices: list[str] = Field(default_factory=list)
    device_on_since: dict[str, str] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_item(self) -> dict:
        return {
            "household_id": self.household_id,
            "people_home": self.people_home,
            "active_devices": self.active_devices,
            "device_on_since": self.device_on_since,
            "updated_at": self.updated_at.astimezone(timezone.utc).isoformat(),
        }

    @classmethod
    def from_item(cls, item: dict) -> "HouseholdState":
        return cls(
            household_id=item["household_id"],
            people_home=item.get("people_home", {}),
            active_devices=item.get("active_devices", []),
            device_on_since=item.get("device_on_since", {}),
            updated_at=datetime.fromisoformat(
                item.get("updated_at", datetime.now(timezone.utc).isoformat())
            ),
        )

    @classmethod
    def empty(cls, household_id: str) -> "HouseholdState":
        return cls(household_id=household_id)


# ─── Context Object ───────────────────────────────────────────────────────

class ContextType(str, Enum):
    DEPARTURE_ANOMALY = "departure_anomaly"
    DURATION_ANOMALY = "duration_anomaly"
    ROUTINE_SUGGESTION = "routine_suggestion"
    NORMAL = "normal"


class AnomalyType(str, Enum):
    DEVICE_LEFT_ON = "device_left_on"
    DURATION_EXCEEDED = "duration_exceeded"
    MISSED_ROUTINE = "missed_routine"


class Anomaly(BaseModel):
    type: AnomalyType
    device: str | None = None
    detail: str | None = None
    related_pattern_id: str | None = None
    severity: str = Field(default="medium", examples=["low", "medium", "high"])


class RelevantPattern(BaseModel):
    pattern_id: str
    pattern_type: str
    description: str
    confidence: float


class ContextObject(BaseModel):
    context_type: ContextType
    household_id: str
    current_time: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    people_home: dict[str, bool] = Field(default_factory=dict)
    active_devices: list[str] = Field(default_factory=list)
    relevant_patterns: list[RelevantPattern] = Field(default_factory=list)
    anomalies: list[Anomaly] = Field(default_factory=list)
    recent_events: list[dict] = Field(default_factory=list)
