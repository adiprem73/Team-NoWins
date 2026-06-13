"""Interactive proof: see the Context Object change across scenarios.

Runs entirely in-memory (moto) — no AWS, no Docker. It:
  1. Loads 30 days of history and extracts patterns (the "learning" phase).
  2. Replays several DIFFERENT "current states" and prints the resulting
     Context Object for each, so you can verify the builder reacts correctly:
        - Scenario 1: DEPARTURE ANOMALY  (son's fan/light left ON past 08:00)
        - Scenario 2: DURATION ANOMALY   (water motor running 45 min vs ~15)
        - Scenario 3: NORMAL             (only expected devices active)

Usage:
    python scripts/demo_scenarios.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from moto import mock_aws


def _print_context(title: str, ctx) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)
    data = ctx.model_dump(mode="json")
    print(f"context_type   : {data['context_type']}")
    print(f"current_time   : {data['current_time']}")
    print(f"active_devices : {data['active_devices']}")
    print(f"anomalies      :")
    if not data["anomalies"]:
        print("    (none)")
    for a in data["anomalies"]:
        print(f"    - [{a['severity']}] {a['type']}: {a.get('detail')}")
    print(f"relevant_patterns ({len(data['relevant_patterns'])}):")
    for p in data["relevant_patterns"]:
        print(f"    - {p['description']}  (conf={p['confidence']})")


def main() -> None:
    mock = mock_aws()
    mock.start()
    try:
        from patterns.dynamodb import client as dynamo_client

        dynamo_client.get_dynamodb_resource.cache_clear()
        from patterns.dynamodb.tables import create_tables

        create_tables()

        from patterns.context_builder import build_context
        from patterns.models.state import HouseholdState
        from patterns.pattern_engine import extract_all
        from patterns.logic import event_service, pattern_service
        from patterns.tests.sample_data import HOUSEHOLD, generate

        # --- LEARNING PHASE: 30 days of history -> patterns ---
        event_service.store_events(generate(days=30, include_today_anomaly=False))
        patterns = pattern_service.extract_and_store(HOUSEHOLD)
        print(f"Learned {len(patterns)} patterns from 30 days of events:")
        for p in patterns:
            print(f"  - [{p.pattern_type.value}] {p.pattern_id} (conf={p.confidence})")

        now = datetime.now(timezone.utc).replace(hour=11, minute=0)

        # --- SCENARIO 1: departure anomaly ---
        state1 = HouseholdState(
            household_id=HOUSEHOLD,
            people_home={"father": True, "mother": False, "son": False},
            active_devices=["son_room_fan", "son_room_light"],
        )
        _print_context(
            "SCENARIO 1 — Son left for college but fan & light still ON (11:00)",
            build_context(state1, patterns, recent_events=[], now=now),
        )

        # --- SCENARIO 2: duration anomaly ---
        forty_five_min_ago = (now - timedelta(minutes=45)).isoformat()
        state2 = HouseholdState(
            household_id=HOUSEHOLD,
            people_home={"father": True, "mother": False, "son": False},
            active_devices=["water_motor"],
            device_on_since={"water_motor": forty_five_min_ago},
        )
        _print_context(
            "SCENARIO 2 — Water motor running 45 min (usual ~15 min)",
            build_context(state2, patterns, recent_events=[], now=now),
        )

        # --- SCENARIO 3: normal ---
        state3 = HouseholdState(
            household_id=HOUSEHOLD,
            people_home={"father": True, "mother": True, "son": False},
            active_devices=[],
        )
        _print_context(
            "SCENARIO 3 — Nothing unusual active",
            build_context(state3, patterns, recent_events=[], now=now),
        )

        print("\n" + "=" * 70)
        print("Done. Each context_type reflects the current state vs learned patterns.")
        print("=" * 70)
    finally:
        mock.stop()


if __name__ == "__main__":
    main()
