"""DynamoDB package: client + table schemas."""
from patterns.dynamodb.client import get_dynamodb_resource, get_table  # noqa: F401
from patterns.dynamodb.tables import create_tables, table_definitions  # noqa: F401
