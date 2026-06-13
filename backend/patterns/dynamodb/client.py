"""Single source of truth for the boto3 DynamoDB resource.

Using the higher-level ``resource`` API keeps service code free of low-level
attribute-value marshalling. The endpoint URL is read from settings so the
exact same code targets DynamoDB Local during development and AWS in prod.
"""
from __future__ import annotations

from functools import lru_cache

import boto3

from patterns.app.config import get_settings


@lru_cache
def get_dynamodb_resource():
    settings = get_settings()
    kwargs: dict = {"region_name": settings.aws_region}
    if settings.dynamodb_endpoint_url:
        kwargs["endpoint_url"] = settings.dynamodb_endpoint_url
        # DynamoDB Local ignores credentials but boto3 still requires them.
        kwargs.update(
            aws_access_key_id="local",
            aws_secret_access_key="local",
        )
    return boto3.resource("dynamodb", **kwargs)


def get_table(name: str):
    return get_dynamodb_resource().Table(name)
