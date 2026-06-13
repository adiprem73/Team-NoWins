"""DynamoDB client and table management for pattern service."""
from functools import lru_cache
import boto3

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import settings


@lru_cache
def get_dynamodb_resource():
    kwargs = {"region_name": settings.aws_region}
    if settings.dynamodb_endpoint_url:
        kwargs["endpoint_url"] = settings.dynamodb_endpoint_url
        kwargs.update(aws_access_key_id="local", aws_secret_access_key="local")
    else:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.resource("dynamodb", **kwargs)


def get_table(name: str):
    return get_dynamodb_resource().Table(name)


def create_tables():
    resource = get_dynamodb_resource()
    client = resource.meta.client
    existing = set(client.list_tables()["TableNames"])
    tables = [
        {
            "TableName": settings.events_table,
            "KeySchema": [
                {"AttributeName": "household_id", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "household_id", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
        {
            "TableName": settings.state_table,
            "KeySchema": [{"AttributeName": "household_id", "KeyType": "HASH"}],
            "AttributeDefinitions": [{"AttributeName": "household_id", "AttributeType": "S"}],
            "BillingMode": "PAY_PER_REQUEST",
        },
        {
            "TableName": settings.patterns_table,
            "KeySchema": [
                {"AttributeName": "household_id", "KeyType": "HASH"},
                {"AttributeName": "pattern_id", "KeyType": "RANGE"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "household_id", "AttributeType": "S"},
                {"AttributeName": "pattern_id", "AttributeType": "S"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
    ]
    for defn in tables:
        if defn["TableName"] not in existing:
            resource.create_table(**defn)
            resource.Table(defn["TableName"]).wait_until_exists()
