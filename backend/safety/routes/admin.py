"""Admin / demo endpoints for the Adaptive Safety engine.

Seed the elderly-alone household (E001) with 30 days of routine history, set the
person profiles (vulnerability), rebuild live state, and extract patterns — all
in one call so the dashboard's "Load Demo Data" button gives an instantly
populated, fully-learned home. Scenario flags inject a specific "today" safety
situation (gas left on, window open at night, SOS, health alert, inactivity).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from safety.logic import (
    event_service,
    pattern_service,
    profile_service,
    state_service,
)
from safety.models.safety import PersonProfile, Vulnerability
from safety.models.state import HouseholdState

router = APIRouter(prefix="/admin", tags=["admin"])

_SCENARIOS = {
    "E001": "elderly_alone",
}

# Demo scenario flag -> the generate() kwargs it sets.
_SCENARIO_FLAGS = {
    "normal": {},
    "inactivity": {"include_inactivity": True},
    "gas": {"include_gas_left_on": True},
    "window_night": {"include_window_night": True},
    "health": {"include_health_alert": True},
    "sos": {"include_sos": True},
}

# Household-composition presets. The person_ids stay "grandpa"/"grandma" so the
# learned routines, timeline, and wearable/SOS events still line up — only the
# display name + vulnerability change. Single-person presets write ONE profile
# so the dashboard shows that person "home alone".
_CONTACTS = ["son_bangalore", "daughter_pune"]


def _preset_profiles(preset: str) -> list[PersonProfile]:
    if preset == "elderly":
        return [
            PersonProfile(person_id="grandpa", display_name="Ramesh (Grandpa)",
                          vulnerability=Vulnerability.ELDERLY, relation="father",
                          wearable_id="grandpa_wearable", emergency_contacts=_CONTACTS),
            PersonProfile(person_id="grandma", display_name="Saroja (Grandma)",
                          vulnerability=Vulnerability.ELDERLY, relation="mother",
                          emergency_contacts=_CONTACTS),
        ]
    if preset == "child_alone":
        return [
            PersonProfile(person_id="grandpa", display_name="Aarav (Child)",
                          vulnerability=Vulnerability.CHILD, relation="son",
                          wearable_id="grandpa_wearable", emergency_contacts=_CONTACTS),
        ]
    if preset == "pregnant_alone":
        return [
            PersonProfile(person_id="grandpa", display_name="Meera (Expecting)",
                          vulnerability=Vulnerability.PREGNANT, relation="mother",
                          wearable_id="grandpa_wearable", emergency_contacts=_CONTACTS),
        ]
    if preset == "unwell_alone":
        return [
            PersonProfile(person_id="grandpa", display_name="Ravi (Recovering)",
                          vulnerability=Vulnerability.UNWELL, relation="father",
                          wearable_id="grandpa_wearable", emergency_contacts=_CONTACTS),
        ]
    if preset == "mixed_support":
        return [
            PersonProfile(person_id="grandma", display_name="Saroja (Grandma)",
                          vulnerability=Vulnerability.ELDERLY, relation="mother",
                          emergency_contacts=_CONTACTS),
            PersonProfile(person_id="grandpa", display_name="Arjun (Son, adult)",
                          vulnerability=Vulnerability.NORMAL, relation="son",
                          wearable_id="grandpa_wearable", emergency_contacts=_CONTACTS),
        ]
    raise HTTPException(status_code=400, detail=f"Unknown household preset: {preset}")


_HOUSEHOLD_PRESETS = [
    "elderly", "child_alone", "pregnant_alone", "unwell_alone", "mixed_support",
]


def _seed(household_id: str, *, scenario: str = "normal") -> dict:
    if household_id != "E001":
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {household_id}")

    # ``scenario`` may be a single key or several comma-separated keys so the
    # demo can inject MULTIPLE safety threats at once (e.g. "gas,window_night,sos")
    # and light up several stacked notifications, exactly like the patterns demo.
    keys = [k.strip() for k in scenario.split(",") if k.strip()] or ["normal"]
    unknown = [k for k in keys if k not in _SCENARIO_FLAGS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown safety scenario(s): {unknown}")

    # Merge the flags from every selected scenario into one generate() call.
    merged: dict = {}
    for k in keys:
        merged.update(_SCENARIO_FLAGS[k])

    from safety.tests.sample_data_elderly import generate, profiles

    # Idempotent: clear events + profiles first.
    removed = event_service.delete_household_events(household_id)
    profile_service.delete_profiles(household_id)

    payloads = generate(days=30, **merged)
    stored = event_service.store_events(payloads)
    written = profile_service.save_profiles(household_id, profiles())

    # Rebuild live snapshot from the most recent events.
    state_service.save_state(HouseholdState.empty(household_id))
    for ev in event_service.get_recent_events(household_id, 3):
        state_service.apply_event(ev)

    patterns = pattern_service.extract_and_store(household_id)
    return {
        "household_id": household_id,
        "scenario": _SCENARIOS.get(household_id),
        "safety_scenarios": keys,
        "events_cleared": removed,
        "events_stored": len(stored),
        "profiles_written": written,
        "patterns_extracted": len(patterns),
    }


@router.post("/seed/{household_id}")
def seed(household_id: str, scenario: str = "normal") -> dict:
    """Seed the home with history + profiles. ``scenario`` injects today's
    safety situation: normal | inactivity | gas | window_night | health | sos."""
    return _seed(household_id, scenario=scenario)


@router.post("/profiles/{household_id}")
def set_household_preset(household_id: str, preset: str = "elderly") -> dict:
    """Swap WHO is home and how vulnerable they are, without re-seeding events.

    Demonstrates "same home, different vulnerable person": child alone, pregnant
    woman alone, someone unwell alone, or an elderly person with a capable adult
    present (which mitigates risk). Routines/timeline are unchanged — only the
    vulnerability lens shifts, so every concern is re-escalated accordingly.
    Presets: elderly | child_alone | pregnant_alone | unwell_alone | mixed_support.
    """
    profs = _preset_profiles(preset)
    profile_service.delete_profiles(household_id)
    written = profile_service.save_profiles(household_id, profs)
    return {
        "household_id": household_id,
        "preset": preset,
        "profiles_written": written,
        "members": [
            {"name": p.display_name, "vulnerability": p.vulnerability.value}
            for p in profs
        ],
    }


@router.get("/scenarios")
def scenarios() -> dict:
    return {
        "scenarios": _SCENARIOS,
        "safety_scenarios": list(_SCENARIO_FLAGS.keys()),
        "household_presets": _HOUSEHOLD_PRESETS,
    }
