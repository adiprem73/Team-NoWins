"""Pattern API: trigger extraction + read learned patterns."""
from __future__ import annotations

from fastapi import APIRouter

from patterns.logic import pattern_service

router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.post("/{household_id}/extract")
def extract(household_id: str) -> dict:
    """Manually run the deterministic extraction job (also runs automatically
    on a fixed interval via the in-process scheduler)."""
    patterns = pattern_service.extract_and_store(household_id)
    return {
        "household_id": household_id,
        "extracted": len(patterns),
        "patterns": [p.model_dump(mode="json") for p in patterns],
    }


@router.get("/{household_id}")
def list_patterns(household_id: str) -> dict:
    patterns = pattern_service.get_patterns(household_id)
    return {
        "household_id": household_id,
        "count": len(patterns),
        "patterns": [p.model_dump(mode="json") for p in patterns],
    }
