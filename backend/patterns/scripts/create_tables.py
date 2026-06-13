"""CLI: create DynamoDB tables (idempotent).

Usage (local, against DynamoDB Local):
    DYNAMODB_ENDPOINT_URL=http://localhost:8000 python scripts/create_tables.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from patterns.dynamodb.tables import create_tables


def main() -> None:
    created = create_tables()
    if created:
        print(f"Created tables: {', '.join(created)}")
    else:
        print("All tables already exist.")


if __name__ == "__main__":
    main()
