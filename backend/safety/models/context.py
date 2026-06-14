"""Pydantic models for the AI-ready Context Object.

This is the final artefact of the MVP. It is the structured payload that, in a
future phase, will be handed to Amazon Bedrock for reasoning. Today we stop
once this object is built and validated.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from safety.models.safety import SafetyAssessment


class ContextType(str, Enum):
    DEPARTURE_ANOMALY = "departure_anomaly"
    DURATION_ANOMALY = "duration_anomaly"
    ROUTINE_SUGGESTION = "routine_suggestion"
    # --- Indian-context, people-centric situations ---
    CARE_ALERT = "care_alert"          # elderly inactivity / missed medicine / missed return
    SECURITY_ALERT = "security_alert"  # someone active outside the usual schedule
    # --- Adaptive Safety Intelligence ---
    SAFETY_ALERT = "safety_alert"      # a vulnerability-escalated home-safety concern
    EMERGENCY = "emergency"            # SOS / vitals breach / prolonged total inactivity
    NORMAL = "normal"


class AnomalyType(str, Enum):
    DEVICE_LEFT_ON = "device_left_on"
    DURATION_EXCEEDED = "duration_exceeded"
    MISSED_ROUTINE = "missed_routine"
    DEVICE_ACTIVE_TOO_LONG = "device_active_too_long"
    # --- People-centric (care / safety / security) ---
    INACTIVITY = "inactivity"                # elderly person's usual activity not seen
    MISSED_ARRIVAL = "missed_arrival"        # person hasn't returned as usual (e.g. child)
    MISSED_MEDICINE = "missed_medicine"      # medicine routine not confirmed
    UNEXPECTED_ACTIVITY = "unexpected_activity"  # entry/activity outside the learned schedule
    # --- Adaptive Safety Intelligence ---
    GLOBAL_INACTIVITY = "global_inactivity"  # NO activity of any kind for hours
    UNSAFE_AT_NIGHT = "unsafe_at_night"      # door/window open during the night window
    HEALTH_ALERT = "health_alert"            # wearable vital breached a safe threshold
    SOS = "sos"                              # explicit panic / fall / help trigger


class Anomaly(BaseModel):
    type: AnomalyType
    device: str | None = None
    detail: str | None = None
    related_pattern_id: str | None = None
    severity: str = Field(default="medium", examples=["low", "medium", "high", "critical"])
    # --- Safety overlay enrichment (set by the vulnerability escalation step) ---
    base_severity: str | None = Field(
        default=None, description="Raw type-severity before vulnerability escalation."
    )
    vulnerability_factor: float = Field(
        default=1.0, description="Multiplier applied because of who is home."
    )


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

    # Deterministic safety roll-up (vulnerability + score + status). Attached by
    # the safety overlay after anomaly detection.
    safety: SafetyAssessment | None = None

    # Compact recent-event tail to give the LLM short-term memory.
    recent_events: list[dict] = Field(default_factory=list)
