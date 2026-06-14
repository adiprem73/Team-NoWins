"""Pydantic models for household device events.

An *event* is the atomic unit of the platform: a single, immutable fact about
something that happened in the home (a fan turned off, a door opened, etc.).
Events are append-only and never mutated.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class DeviceAction(str, Enum):
    """Canonical set of actions a device/sensor can report."""

    ON = "ON"
    OFF = "OFF"
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    ARRIVE = "ARRIVE"  # presence sensor: a person arrived
    LEAVE = "LEAVE"    # presence sensor: a person left
    # --- Human-/routine-centric momentary pings (no ON/OFF state) ---
    ACTIVE = "ACTIVE"  # activity sensor: a person was detected moving/awake
    TAKEN = "TAKEN"    # a scheduled action was confirmed done (e.g. medicine)
    # --- Adaptive Safety Intelligence (elderly-alone) signals ---
    ALERT = "ALERT"    # a wearable/sensor threshold breach (e.g. heart_rate<50)
    SOS = "SOS"        # explicit panic / fall / help button press


class DeviceType(str, Enum):
    """Coarse device taxonomy used for grouping and reasoning."""

    FAN = "fan"
    LIGHT = "light"
    AC = "ac"
    TV = "tv"
    DOOR = "door"
    MOTOR = "motor"
    PRESENCE = "presence"
    # --- Indian-context care/security sensors ---
    ACTIVITY = "activity"   # motion/activity tied to a person (elderly care)
    MEDICINE = "medicine"   # smart pill box / medicine reminder
    # --- Adaptive Safety Intelligence sensors ---
    WINDOW = "window"       # window open/close contact sensor
    WEARABLE = "wearable"   # smartwatch/band streaming vitals (value in metadata)
    GAS = "gas"             # gas stove / leak sensor
    OTHER = "other"


class EventCreate(BaseModel):
    """Payload accepted by the ingest API. ``timestamp`` is optional and
    defaults to ingest time so simple devices need not carry a clock."""

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
    # Optional free-form metadata (e.g. duration for motor stop events).
    metadata: dict | None = None

    @field_validator("timestamp")
    @classmethod
    def _ensure_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        return v.astimezone(timezone.utc) if v.tzinfo else v.replace(tzinfo=timezone.utc)


class Event(EventCreate):
    """Persisted event. Adds the server-assigned identity & guaranteed time."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_item(self) -> dict:
        """Serialise to a DynamoDB-friendly dict (ISO strings, no None)."""
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
