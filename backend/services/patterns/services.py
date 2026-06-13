"""Business logic services for pattern recognition."""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from boto3.dynamodb.conditions import Key

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import settings

from services.patterns.dynamo import get_table
from services.patterns.models import (
    Event,
    EventCreate,
    HouseholdState,
    BasePattern,
    pattern_from_item,
    pattern_to_item,
)
from services.patterns.engine import extract_all


# ─── Event Service ─────────────────────────────────────────────────────────

def _sk(event: Event) -> str:
    return f"{event.timestamp.astimezone(timezone.utc).isoformat()}#{event.event_id}"


def store_event(payload: EventCreate) -> Event:
    data = payload.model_dump()
    if data.get("timestamp") is None:
        data.pop("timestamp", None)
    event = Event(**data)
    item = event.to_item()
    item["sk"] = _sk(event)
    get_table(settings.events_table).put_item(Item=item)
    return event


def get_events(
    household_id: str, since: datetime | None = None, limit: int | None = None
) -> list[Event]:
    table = get_table(settings.events_table)
    key_cond = Key("household_id").eq(household_id)
    if since:
        key_cond = key_cond & Key("sk").gte(since.astimezone(timezone.utc).isoformat())
    kwargs = {"KeyConditionExpression": key_cond, "ScanIndexForward": True}
    if limit:
        kwargs["ScanIndexForward"] = False
        kwargs["Limit"] = limit
    items = []
    resp = table.query(**kwargs)
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp and not limit:
        resp = table.query(ExclusiveStartKey=resp["LastEvaluatedKey"], **kwargs)
        items.extend(resp.get("Items", []))
    events = [Event.from_item(i) for i in items]
    events.sort(key=lambda e: e.timestamp)
    return events


def get_recent_events(household_id: str, days: int) -> list[Event]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return get_events(household_id, since=since)


# ─── State Service ─────────────────────────────────────────────────────────

ON_ACTIONS = {"ON", "OPEN"}
OFF_ACTIONS = {"OFF", "CLOSE"}


def get_state(household_id: str) -> HouseholdState:
    resp = get_table(settings.state_table).get_item(Key={"household_id": household_id})
    item = resp.get("Item")
    return HouseholdState.from_item(item) if item else HouseholdState.empty(household_id)


def save_state(state: HouseholdState):
    get_table(settings.state_table).put_item(Item=state.to_item())


def apply_event(event: Event) -> HouseholdState:
    state = get_state(event.household_id)
    device = event.device_id
    action = event.action.value
    ts_iso = event.timestamp.astimezone(timezone.utc).isoformat()

    if event.device_type.value == "presence":
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
    save_state(state)
    return state


# ─── Pattern Service ───────────────────────────────────────────────────────

def _to_dynamo_safe(item: dict) -> dict:
    return json.loads(json.dumps(item), parse_float=Decimal)


def extract_and_store(household_id: str) -> list[BasePattern]:
    events = get_recent_events(household_id, settings.analysis_window_days)
    patterns = extract_all(household_id, events)
    table = get_table(settings.patterns_table)
    with table.batch_writer() as batch:
        for pattern in patterns:
            item = pattern_to_item(pattern)
            item["household_id"] = household_id
            batch.put_item(Item=_to_dynamo_safe(item))
    return patterns


def get_patterns(household_id: str) -> list[BasePattern]:
    table = get_table(settings.patterns_table)
    resp = table.query(KeyConditionExpression=Key("household_id").eq(household_id))
    items = resp.get("Items", [])
    while "LastEvaluatedKey" in resp:
        resp = table.query(
            KeyConditionExpression=Key("household_id").eq(household_id),
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp.get("Items", []))
    return [pattern_from_item(i) for i in items]
