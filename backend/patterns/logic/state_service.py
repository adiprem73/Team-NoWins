"""Household state service.

Maintains the single live snapshot per home. The key responsibility is
``apply_event``: given a new event it mutates the snapshot deterministically
(toggle active devices, update presence, track on-since timestamps).

This is the function the ingest Lambda calls after persisting an event so the
state is always current for the context builder.
"""
from __future__ import annotations

from datetime import timezone

from patterns.app.config import get_settings
from patterns.dynamodb.client import get_table
from patterns.models.events import Event
from patterns.models.state import HouseholdState

ON_ACTIONS = {"ON", "OPEN"}
OFF_ACTIONS = {"OFF", "CLOSE"}


def get_state(household_id: str) -> HouseholdState:
    resp = get_table(get_settings().state_table).get_item(
        Key={"household_id": household_id}
    )
    item = resp.get("Item")
    return HouseholdState.from_item(item) if item else HouseholdState.empty(household_id)


def save_state(state: HouseholdState) -> None:
    get_table(get_settings().state_table).put_item(Item=state.to_item())


def apply_event(event: Event, *, persist: bool = True) -> HouseholdState:
    """Fold a single event into the household state and (optionally) persist."""
    state = get_state(event.household_id)
    device = event.device_id
    action = event.action.value
    ts_iso = event.timestamp.astimezone(timezone.utc).isoformat()

    if event.device_type.value == "presence":
        # Presence events update people_home rather than active_devices.
        person = event.triggered_by
        if action in {"ARRIVE", "OPEN", "ON"}:
            state.people_home[person] = True
        elif action in {"LEAVE", "CLOSE", "OFF"}:
            state.people_home[person] = False
    else:
        if action in ON_ACTIONS:
            if device not in state.active_devices:
                state.active_devices.append(device)
            state.device_on_since[device] = ts_iso
        elif action in OFF_ACTIONS:
            if device in state.active_devices:
                state.active_devices.remove(device)
            state.device_on_since.pop(device, None)

    state.updated_at = event.timestamp
    if persist:
        save_state(state)
    return state
