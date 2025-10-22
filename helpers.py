"""Backward-compatible helper functions using new services."""

import os
from typing import Dict, Any, Tuple

from dotenv import load_dotenv

from services.query_validator import QueryValidatorService
from services.access_control import AccessControlService
from services.configuration import AccessConfig

load_dotenv()

FORBIDDEN_KEYWORDS = (
    "DELETE", "UPDATE", "INSERT", "CREATE", "DROP", "ALTER",
    "MERGE", "TRUNCATE", "REPLACE", "GRANT", "REVOKE"
)


def validate_query_safety(query: str) -> Tuple[bool, str]:
    """Validate that query is safe (SELECT only, no forbidden keywords)."""
    validator = QueryValidatorService()
    return validator.validate_query_safety(query)


def validate_query_tables(query: str, access_config: Dict[str, Any]) -> bool:
    """Validate that query only references allowed tables."""
    config = AccessConfig(
        allowed_tables=access_config.get("allowed_tables", []),
        allowed_datasets=access_config.get("allowed_datasets", {}),
        allowed_patterns=access_config.get("allowed_patterns", [])
    )

    access_control = AccessControlService(config)
    access_control.validate_query_tables(query)
    return True


def is_table_allowed(table: str, access_config: Dict[str, Any]) -> bool:
    """Check if a table is allowed based on access control config."""
    config = AccessConfig(
        allowed_tables=access_config.get("allowed_tables", []),
        allowed_datasets=access_config.get("allowed_datasets", {}),
        allowed_patterns=access_config.get("allowed_patterns", [])
    )

    access_control = AccessControlService(config)
    return access_control.is_table_allowed(table)


def match_table_pattern(table: str, pattern: str) -> bool:
    """Match table ID against a wildcard pattern."""
    import fnmatch
    return fnmatch.fnmatch(table, pattern)
