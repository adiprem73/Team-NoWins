"""Safety / vulnerability models for Adaptive Safety Intelligence.

This is the ONE genuinely new concept the safety engine adds on top of the
duplicated pattern pipeline: a notion of *who* is home and *how vulnerable*
they are, plus the deterministic safety roll-up produced by the safety overlay.

Design mirrors the rest of the codebase: plain Pydantic, no ML, every number
explainable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class Vulnerability(str, Enum):
    """How much extra protection a person needs when something goes wrong."""

    NORMAL = "normal"      # working-age, capable adult
    CHILD = "child"        # minor at home
    PREGNANT = "pregnant"  # expecting mother, home alone
    UNWELL = "unwell"      # temporarily recovering / fragile
    ELDERLY = "elderly"    # senior living independently


class PersonProfile(BaseModel):
    """A household member the safety engine reasons about."""

    person_id: str = Field(..., examples=["grandpa"])
    display_name: str = Field(..., examples=["Grandpa"])
    vulnerability: Vulnerability = Vulnerability.NORMAL
    # Who to notify when an emergency-level concern fires (children in other
    # cities, a neighbour, a doctor). Free-form ids/phone labels for the demo.
    emergency_contacts: list[str] = Field(default_factory=list)
    # Optional wearable that streams vitals as ALERT events.
    wearable_id: str | None = None
    # Relationship label shown on the dashboard ("father", "mother", ...).
    relation: str | None = None

    def to_item(self, household_id: str) -> dict:
        return {
            "household_id": household_id,
            "person_id": self.person_id,
            "display_name": self.display_name,
            "vulnerability": self.vulnerability.value,
            "emergency_contacts": self.emergency_contacts,
            "wearable_id": self.wearable_id,
            "relation": self.relation,
        }

    @classmethod
    def from_item(cls, item: dict) -> "PersonProfile":
        return cls(
            person_id=item["person_id"],
            display_name=item.get("display_name", item["person_id"].title()),
            vulnerability=item.get("vulnerability", "normal"),
            emergency_contacts=item.get("emergency_contacts", []),
            wearable_id=item.get("wearable_id"),
            relation=item.get("relation"),
        )


class SafetyStatus(str, Enum):
    """Headline status shown on the Adaptive Safety Dashboard."""

    SAFE = "safe"
    INACTIVE = "inactive"
    NEEDS_ATTENTION = "needs_attention"
    EMERGENCY = "emergency"


class SafetyAssessment(BaseModel):
    """Deterministic safety roll-up attached to every context object.

    ``safety_score`` is 0..100 where higher = safer. Every deduction is
    explainable and surfaced in ``rationale`` so judges (and the LLM) can see
    exactly *why* the home is at a given status.
    """

    status: SafetyStatus = SafetyStatus.SAFE
    safety_score: float = Field(100.0, ge=0.0, le=100.0)
    # True when a vulnerable person is home with no capable adult present.
    vulnerable_alone: bool = False
    occupants: list[str] = Field(default_factory=list)
    # person_id -> short display name (for the narrator to speak naturally).
    occupant_labels: dict[str, str] = Field(default_factory=dict)
    most_vulnerable: str | None = None
    most_vulnerable_kind: str | None = None
    vulnerability_factor: float = 1.0
    rationale: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
