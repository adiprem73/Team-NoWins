"""Pydantic models for the live household state snapshot.

Unlike events (append-only history), the state is a single mutable document
per household representing *right now*: who is home and which devices are on.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class HouseholdState(BaseModel):
    """Current snapshot of a single home."""

    household_id: str = Field(..., examples=["H001"])
    people_home: dict[str, bool] = Field(
        default_factory=dict,
        description="Map of person -> presence flag.",
        examples=[{"father": True, "mother": False, "son": False}],
    )
    active_devices: list[str] = Field(
        default_factory=list,
        description="Device IDs currently ON / OPEN.",
        examples=[["son_room_fan", "living_room_tv"]],
    )
    # device_id -> ISO timestamp it was switched on (for duration anomalies).
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
