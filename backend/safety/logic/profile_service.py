"""Profile service: persistence + retrieval of household PersonProfiles.

Profiles capture WHO lives in the home and HOW vulnerable they are — the single
new input the safety overlay needs to escalate severity by occupant. Stored in
the dedicated ``Safety_Profiles`` table so they live with the safety engine.
"""
from __future__ import annotations

from boto3.dynamodb.conditions import Key

from safety.app.config import get_settings
from safety.dynamodb.client import get_table
from safety.models.safety import PersonProfile


def get_profiles(household_id: str) -> dict[str, PersonProfile]:
    """Return person_id -> PersonProfile for a household (empty if none set)."""
    table = get_table(get_settings().profiles_table)
    resp = table.query(KeyConditionExpression=Key("household_id").eq(household_id))
    items = resp.get("Items", [])
    while "LastEvaluatedKey" in resp:
        resp = table.query(
            KeyConditionExpression=Key("household_id").eq(household_id),
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp.get("Items", []))
    profiles: dict[str, PersonProfile] = {}
    for it in items:
        p = PersonProfile.from_item(it)
        profiles[p.person_id] = p
    return profiles


def save_profiles(household_id: str, profiles: list[PersonProfile]) -> int:
    """Upsert a batch of profiles for a household. Returns the count written."""
    table = get_table(get_settings().profiles_table)
    with table.batch_writer() as batch:
        for p in profiles:
            batch.put_item(Item=p.to_item(household_id))
    return len(profiles)


def delete_profiles(household_id: str) -> int:
    """Remove all profiles for a household (makes re-seeding idempotent)."""
    table = get_table(get_settings().profiles_table)
    resp = table.query(KeyConditionExpression=Key("household_id").eq(household_id))
    items = resp.get("Items", [])
    while "LastEvaluatedKey" in resp:
        resp = table.query(
            KeyConditionExpression=Key("household_id").eq(household_id),
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp.get("Items", []))
    deleted = 0
    with table.batch_writer() as batch:
        for it in items:
            batch.delete_item(
                Key={"household_id": it["household_id"], "person_id": it["person_id"]}
            )
            deleted += 1
    return deleted
