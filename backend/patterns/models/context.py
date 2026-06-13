"""Pydantic models for the AI-ready Context Object.

This is the final artefact of the MVP. It is the structured payload that, in a
future phase, will be handed to Amazon Bedrock for reasoning. Today we stop
once this object is built and validated.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class ContextType(str, Enum):
    DEPARTURE_ANOMALY = "departure_anomaly"
    DURATION_ANOMALY = "duration_anomaly"
    ROUTINE_SUGGESTION = "routine_suggestion"
    NORMAL = "normal"


class AnomalyType(str, Enum):
    DEVICE_LEFT_ON = "device_left_on"
    DURATION_EXCEEDED = "duration_exceeded"
    MISSED_ROUTINE = "missed_routine"
    DEVICE_ACTIVE_TOO_LONG = "device_active_too_long"


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
    time: str | None = None   # "HH:MM" the routine is anchored to, when known


class ContextObject(BaseModel):
    """The structured context ready to be sent to Bedrock (future phase)."""

    context_type: ContextType
    household_id: str
    current_time: str  # "HH:MM" local clock for human-readable reasoning
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    people_home: dict[str, bool] = Field(default_factory=dict)
    active_devices: list[str] = Field(default_factory=list)

    relevant_patterns: list[RelevantPattern] = Field(default_factory=list)
    anomalies: list[Anomaly] = Field(default_factory=list)

    # Compact recent-event tail to give the LLM short-term memory.
    recent_events: list[dict] = Field(default_factory=list)
