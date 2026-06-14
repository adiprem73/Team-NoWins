"""Household state API."""
from __future__ import annotations

from fastapi import APIRouter

from safety.models.state import HouseholdState
from safety.logic import state_service

router = APIRouter(prefix="/state", tags=["state"])


@router.get("/{household_id}", response_model=HouseholdState)
def get_state(household_id: str) -> HouseholdState:
    return state_service.get_state(household_id)
