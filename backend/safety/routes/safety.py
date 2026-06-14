"""Adaptive Safety Intelligence API.

The dashboard's single source of truth: returns the live, vulnerability-aware
:class:`ContextObject` (with its :class:`SafetyAssessment`), the household's
person profiles, the live state, a recent-activity timeline, and a learned-
routine summary — everything the Adaptive Safety Dashboard renders.

Also exposes profile management so a home's occupants and their vulnerability
levels can be configured (and edited live from the dashboard).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from safety.logic import (
    context_service,
    event_service,
    pattern_service,
    profile_service,
    state_service,
)
from safety.models.safety import PersonProfile

router = APIRouter(prefix="/safety", tags=["safety"])


def _resolve_now(at: str | None) -> datetime | None:
    """Turn an optional ``HH:MM`` (or full ISO) into a UTC datetime (demo clock)."""
    if not at:
        return None
    try:
        if "T" in at:
            dt = datetime.fromisoformat(at)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        hour, minute = at.split(":")
        return datetime.now(timezone.utc).replace(
            hour=int(hour), minute=int(minute), second=0, microsecond=0
        )
    except (ValueError, TypeError):
        return None


@router.get("/{household_id}")
def get_safety(
    household_id: str,
    at: str | None = Query(
        None, description="Simulated current time as HH:MM (or full ISO). Demo clock.",
        examples=["10:30"],
    ),
) -> dict:
    """The full Adaptive Safety Dashboard payload for one home."""
    now = _resolve_now(at)
    context = context_service.generate_context(household_id, now=now)
    profiles = profile_service.get_profiles(household_id)
    state = state_service.get_state(household_id)
    patterns = pattern_service.get_patterns(household_id)
    recent = event_service.get_recent_events(household_id, 1)

    # Activity timeline: newest first, compact.
    timeline = [
        {
            "timestamp": e.timestamp.isoformat(),
            "device_id": e.device_id,
            "device_type": e.device_type.value,
            "room": e.room,
            "action": e.action.value,
            "triggered_by": e.triggered_by,
        }
        for e in sorted(recent, key=lambda e: e.timestamp, reverse=True)[:40]
    ]

    return {
        "household_id": household_id,
        "context": context.model_dump(mode="json"),
        "safety": context.safety.model_dump(mode="json") if context.safety else None,
        "profiles": [p.model_dump(mode="json") for p in profiles.values()],
        "state": state.to_item(),
        "patterns_count": len(patterns),
        "patterns": [
            {
                "pattern_id": p.pattern_id,
                "pattern_type": p.pattern_type.value,
                "confidence": p.confidence,
            }
            for p in sorted(patterns, key=lambda p: p.confidence, reverse=True)
        ],
        "timeline": timeline,
    }


@router.get("/{household_id}/profiles")
def list_profiles(household_id: str) -> dict:
    profiles = profile_service.get_profiles(household_id)
    return {
        "household_id": household_id,
        "profiles": [p.model_dump(mode="json") for p in profiles.values()],
    }


class ProfilesUpdate(BaseModel):
    profiles: list[PersonProfile] = Field(default_factory=list)
    replace: bool = Field(
        True, description="When true, clears existing profiles before writing."
    )


@router.post("/{household_id}/profiles")
def upsert_profiles(household_id: str, body: ProfilesUpdate) -> dict:
    if body.replace:
        profile_service.delete_profiles(household_id)
    written = profile_service.save_profiles(household_id, body.profiles)
    return {"household_id": household_id, "profiles_written": written}
