"""DynamoDB package: client + table schemas."""
from safety.dynamodb.client import get_dynamodb_resource, get_table  # noqa: F401
from safety.dynamodb.tables import create_tables, table_definitions  # noqa: F401
