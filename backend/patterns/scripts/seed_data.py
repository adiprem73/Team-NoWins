"""CLI: seed 30 days of synthetic events, then extract patterns.

Usage (local, against DynamoDB Local):
    DYNAMODB_ENDPOINT_URL=http://localhost:8000 python scripts/seed_data.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from patterns.dynamodb.tables import create_tables
from patterns.logic import event_service, pattern_service, state_service
from patterns.tests.sample_data import HOUSEHOLD, generate


def main() -> None:
    create_tables()

    payloads = generate(days=30, include_today_anomaly=True)
    stored = event_service.store_events(payloads)
    print(f"Stored {len(stored)} events for {HOUSEHOLD}.")

    # Rebuild live state from the most recent events.
    for ev in event_service.get_recent_events(HOUSEHOLD, 2):
        state_service.apply_event(ev)
    print("Rebuilt household state from recent events.")

    patterns = pattern_service.extract_and_store(HOUSEHOLD)
    print(f"Extracted {len(patterns)} patterns:")
    for p in patterns:
        print(f"  - [{p.pattern_type.value}] {p.pattern_id} (conf={p.confidence})")


if __name__ == "__main__":
    main()
