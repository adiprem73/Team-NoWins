"""Run the API locally against an IN-MEMORY DynamoDB (moto).

No AWS account, no Docker, no real tables. Everything lives in RAM for the
lifetime of this process — ideal for clicking through Swagger at /docs.

Usage:
    python scripts/run_local.py
    # then open http://localhost:8080/docs

Optional: set SEED to pre-load sample data + extracted patterns so the context
endpoints immediately return anomalies:
    SEED=1   python scripts/run_local.py   # H001 — son departure scenario
    SEED=2   python scripts/run_local.py   # H002 — AC / motor / light scenario
    SEED=all python scripts/run_local.py   # both households
"""
from __future__ import annotations

import os
import sys

# Allow running as `python scripts/run_local.py` by putting the backend root
# (this file's parent's parent) on the import path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import uvicorn
from moto import mock_aws


def main() -> None:
    # Activate the in-memory DynamoDB mock for the whole process.
    mock = mock_aws()
    mock.start()

    # Rebind the cached boto3 resource to the mock, then create tables.
    from patterns.dynamodb import client as dynamo_client

    dynamo_client.get_dynamodb_resource.cache_clear()

    from patterns.dynamodb.tables import create_tables

    create_tables()
    print("In-memory DynamoDB ready (tables created in RAM).")

    seed = os.environ.get("SEED", "")
    if seed in {"1", "all"}:
        from patterns.logic import event_service, pattern_service, state_service
        from patterns.tests.sample_data import HOUSEHOLD, generate

        event_service.store_events(generate(days=30, include_today_anomaly=True))
        for ev in event_service.get_recent_events(HOUSEHOLD, 2):
            state_service.apply_event(ev)
        patterns = pattern_service.extract_and_store(HOUSEHOLD)
        print(f"Seeded {HOUSEHOLD} (son departure scenario): {len(patterns)} patterns.")

    if seed in {"2", "all"}:
        from patterns.logic import event_service, pattern_service, state_service
        from patterns.tests.sample_data_h002 import HOUSEHOLD as H2, generate as gen2

        event_service.store_events(gen2(days=30))
        for ev in event_service.get_recent_events(H2, 2):
            state_service.apply_event(ev)
        patterns2 = pattern_service.extract_and_store(H2)
        print(f"Seeded {H2} (AC/motor/light scenario): {len(patterns2)} patterns.")

    from patterns.app.main import create_app

    # lifespan create_tables() is a harmless no-op (tables already exist).
    app = create_app()
    print("Open http://localhost:8080/docs")
    try:
        uvicorn.run(app, host="127.0.0.1", port=8080)
    finally:
        mock.stop()


if __name__ == "__main__":
    main()
