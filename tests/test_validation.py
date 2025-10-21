#!/usr/bin/env python3
"""Test SQL validation for security."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from helpers import validate_query_safety

# Test cases
test_queries = [
    # Valid queries
    ("SELECT * FROM table", True),
    ("select name, age from users", True),
    ("SELECT * FROM table WHERE name = 'DELETE'", True),  # DELETE in string is OK
    ("SELECT * FROM table -- comment", True),
    ("SELECT * FROM table;", True),  # Trailing semicolon OK

    # Invalid queries
    ("DELETE FROM table", False),
    ("INSERT INTO table VALUES (1)", False),
    ("UPDATE table SET x=1", False),
    ("DROP TABLE users", False),
    ("SELECT * FROM table; DROP TABLE users;", False),  # SQL injection attempt
    ("SELECT * FROM table /* DROP TABLE */ WHERE 1=1", True),  # Comment is removed, query is valid
    ("CREATE TABLE new_table AS SELECT * FROM old", False),
    ("SELECT * FROM table WHERE 1=1; DELETE FROM users", False),
    ("SELECT * FROM users; /* */ DROP TABLE users", False),  # Actual DROP after semicolon
]

print("Testing SQL Query Validation\n" + "="*50)

passed = 0
failed = 0

for query, should_be_valid in test_queries:
    is_valid, error = validate_query_safety(query)

    if is_valid == should_be_valid:
        status = "✓ PASS"
        passed += 1
    else:
        status = "✗ FAIL"
        failed += 1

    print(f"\n{status}")
    print(f"Query: {query}")
    print(f"Expected: {'Valid' if should_be_valid else 'Invalid'}")
    print(f"Result: {'Valid' if is_valid else 'Invalid'}")
    if error:
        print(f"Error: {error}")

print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed")
