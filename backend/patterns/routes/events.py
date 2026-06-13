"""Event ingest + query API."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query, status

from patterns.models.events import Event, EventCreate
from patterns.logic import event_service, state_service

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=Event, status_code=status.HTTP_201_CREATED)
def ingest_event(payload: EventCreate) -> Event:
    """Persist an event and fold it into the live household state."""
    event = event_service.store_event(payload)
    state_service.apply_event(event)
    return event


@router.get("", response_model=list[Event])
def list_events(
    household_id: str = Query(..., examples=["H001"]),
    since: datetime | None = Query(
        None, description="ISO-8601 UTC lower bound (inclusive)."
    ),
    limit: int | None = Query(None, ge=1, le=1000),
) -> list[Event]:
    if since and since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    return event_service.get_events(household_id, since=since, limit=limit)
