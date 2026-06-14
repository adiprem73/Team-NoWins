"""Shared pytest fixtures.

Uses ``moto`` to spin up an in-memory DynamoDB so the full stack (services,
routes) can be tested without any AWS account or network access.
"""
from __future__ import annotations

import os

import pytest

# Force a local/test configuration before app modules import settings.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")


@pytest.fixture()
def dynamo_tables(monkeypatch):
    """Provision mocked DynamoDB tables for the duration of a test."""
    from moto import mock_aws

    with mock_aws():
        # Clear cached boto3 resource so it binds to the moto mock.
        from safety.dynamodb import client as dynamo_client

        dynamo_client.get_dynamodb_resource.cache_clear()

        from safety.dynamodb.tables import create_tables

        create_tables()
        yield


@pytest.fixture()
def client(dynamo_tables):
    from fastapi.testclient import TestClient

    from safety.app.main import create_app

    return TestClient(create_app())
