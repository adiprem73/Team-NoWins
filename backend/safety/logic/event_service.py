"""Event service: persistence + retrieval of household events.

Encapsulates all DynamoDB access for the Events table so routes never touch
boto3 directly. The composite sort key ``sk = "{timestamp}#{event_id}"``
keeps items time-ordered and unique within a household partition.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from boto3.dynamodb.conditions import Key

from safety.app.config import get_settings
from safety.dynamodb.client import get_table
from safety.models.events import Event, EventCreate


def _sk(event: Event) -> str:
    return f"{event.timestamp.astimezone(timezone.utc).isoformat()}#{event.event_id}"


def _to_event(payload: EventCreate) -> Event:
    data = payload.model_dump()
    # Drop an absent timestamp so Event's default_factory assigns ingest time.
    if data.get("timestamp") is None:
        data.pop("timestamp", None)
    return Event(**data)


def store_event(payload: EventCreate) -> Event:
    """Persist a single event and return the materialised record."""
    event = _to_event(payload)
    item = event.to_item()
    item["sk"] = _sk(event)
    get_table(get_settings().events_table).put_item(Item=item)
    return event


def store_events(payloads: list[EventCreate]) -> list[Event]:
    """Batch write helper used by the seed script / bulk ingest."""
    settings = get_settings()
    table = get_table(settings.events_table)
    stored: list[Event] = []
    with table.batch_writer() as batch:
        for payload in payloads:
            event = _to_event(payload)
            item = event.to_item()
            item["sk"] = _sk(event)
            batch.put_item(Item=item)
            stored.append(event)
    return stored


def get_events(
    household_id: str,
    *,
    since: datetime | None = None,
    limit: int | None = None,
) -> list[Event]:
    """Query events for a household, optionally constrained to ``since``.

    Returns events in chronological (ascending) order.
    """
    table = get_table(get_settings().events_table)
    key_cond = Key("household_id").eq(household_id)
    if since is not None:
        key_cond = key_cond & Key("sk").gte(since.astimezone(timezone.utc).isoformat())

    kwargs: dict = {"KeyConditionExpression": key_cond, "ScanIndexForward": True}
    if limit:
        # When a limit is supplied we usually want the *latest* events.
        kwargs["ScanIndexForward"] = False
        kwargs["Limit"] = limit

    items: list[dict] = []
    resp = table.query(**kwargs)
    items.extend(resp.get("Items", []))
    # Paginate only when no explicit limit was requested.
    while "LastEvaluatedKey" in resp and not limit:
        resp = table.query(ExclusiveStartKey=resp["LastEvaluatedKey"], **kwargs)
        items.extend(resp.get("Items", []))

    events = [Event.from_item(i) for i in items]
    events.sort(key=lambda e: e.timestamp)
    return events


def get_recent_events(household_id: str, days: int) -> list[Event]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return get_events(household_id, since=since)


def delete_household_events(household_id: str) -> int:
    """Delete every stored event for a household. Returns the count removed.

    Used to make (re-)seeding idempotent: clear the partition first so running
    the demo seed twice doesn't accumulate duplicate events.
    """
    table = get_table(get_settings().events_table)
    deleted = 0
    resp = table.query(KeyConditionExpression=Key("household_id").eq(household_id))
    items = resp.get("Items", [])
    while "LastEvaluatedKey" in resp:
        resp = table.query(
            KeyConditionExpression=Key("household_id").eq(household_id),
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp.get("Items", []))

    with table.batch_writer() as batch:
        for it in items:
            batch.delete_item(
                Key={"household_id": it["household_id"], "sk": it["sk"]}
            )
            deleted += 1
    return deleted
