"""Context service: orchestrate state + patterns + recent events -> context.

Thin coordination layer the API/Lambda call to produce the final
:class:`ContextObject` that will be sent to Bedrock in a future phase.
"""
from __future__ import annotations

from datetime import datetime

from safety.context_builder import build_context
from safety.models.context import ContextObject
from safety.models.state import HouseholdState
from safety.logic import event_service, pattern_service, profile_service, state_service

# Recent-event tail window (days) for short-term memory in the context.
RECENT_WINDOW_DAYS = 1


def generate_context(household_id: str, *, now: datetime | None = None) -> ContextObject:
    state = state_service.get_state(household_id)
    patterns = pattern_service.get_patterns(household_id)
    recent = event_service.get_recent_events(household_id, RECENT_WINDOW_DAYS)
    profiles = profile_service.get_profiles(household_id)
    return build_context(state, patterns, recent, now=now, profiles=profiles)


def evaluate_context(
    household_id: str,
    *,
    active_devices: list[str],
    people_home: dict[str, bool] | None = None,
    device_on_since: dict[str, str] | None = None,
    now: datetime | None = None,
) -> ContextObject:
    """Evaluate a *user-supplied* what-if state against the learned patterns.

    This is the "set the state + clock, then hit Go" flow: instead of reading
    the persisted (and possibly stale) household snapshot, the caller passes the
    exact current state — which devices are ON and (optionally) who is home — and
    we compare it against the patterns mined from history to surface anomalies.

    The state is **ephemeral**: nothing is written back to the events table or
    the state table, so repeated evaluations never pollute the demo data.

    Recent events are intentionally omitted: the user-provided ``active_devices``
    set is the single source of truth for "what is happening right now", so a
    missed-routine is judged purely against that state, not historical events.
    """
    patterns = pattern_service.get_patterns(household_id)
    state = HouseholdState(
        household_id=household_id,
        active_devices=list(active_devices),
        people_home=people_home or {},
        device_on_since=device_on_since or {},
    )
    profiles = profile_service.get_profiles(household_id)
    # In the what-if flow the supplied active_devices are the source of truth,
    # but we still pass recent events so global-inactivity / health / SOS
    # detectors (which read events, not the painted device set) can fire.
    recent = event_service.get_recent_events(household_id, RECENT_WINDOW_DAYS)
    return build_context(state, patterns, recent, now=now, profiles=profiles)
