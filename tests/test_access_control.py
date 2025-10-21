#!/usr/bin/env python3
"""Test access control with dataset whitelist and table blacklist."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from helpers import is_table_allowed, match_table_pattern


def test_table_whitelist():
    """Test specific table whitelist mode."""
    print("\n" + "="*70)
    print("Testing Table Whitelist Mode")
    print("="*70)

    config = {
        "allowed_tables": [
            "project.dataset.table1",
            "project.dataset.table2",
        ]
    }

    test_cases = [
        ("project.dataset.table1", True, "Exact match"),
        ("project.dataset.table2", True, "Another exact match"),
        ("project.dataset.table3", False, "Not in whitelist"),
        ("other.dataset.table1", False, "Different project"),
    ]

    passed = 0
    for table, should_allow, description in test_cases:
        result = is_table_allowed(table, config)
        status = "✓" if result == should_allow else "✗"
        passed += (result == should_allow)

        print(f"  {status} {description:40} [{table}] {'ALLOWED' if result else 'DENIED'}")

    print(f"\n  Results: {passed}/{len(test_cases)} passed\n")
    return passed, len(test_cases) - passed


def test_dataset_whitelist():
    """Test dataset whitelist mode (allow all tables in dataset)."""
    print("="*70)
    print("Testing Dataset Whitelist Mode")
    print("="*70)

    config = {
        "allowed_datasets": {
            "bigquery-public-data.austin_bikeshare": {
                "allow_all_tables": True,
                "blacklisted_tables": []
            }
        }
    }

    test_cases = [
        ("bigquery-public-data.austin_bikeshare.trips", True, "Table in allowed dataset"),
        ("bigquery-public-data.austin_bikeshare.stations", True, "Another table in dataset"),
        ("bigquery-public-data.austin_bikeshare.any_table", True, "Any table allowed"),
        ("bigquery-public-data.other_dataset.table", False, "Different dataset"),
        ("other-project.austin_bikeshare.trips", False, "Different project"),
    ]

    passed = 0
    for table, should_allow, description in test_cases:
        result = is_table_allowed(table, config)
        status = "✓" if result == should_allow else "✗"
        passed += (result == should_allow)

        print(f"  {status} {description:40} {' ALLOWED' if result else ' DENIED'}")

    print(f"\n  Results: {passed}/{len(test_cases)} passed\n")
    return passed, len(test_cases) - passed


def test_dataset_with_blacklist():
    """Test dataset whitelist with table blacklist."""
    print("="*70)
    print("Testing Dataset Whitelist with Table Blacklist")
    print("="*70)

    config = {
        "allowed_datasets": {
            "project.dataset": {
                "allow_all_tables": True,
                "blacklisted_tables": ["sensitive_data", "internal_users"]
            }
        }
    }

    test_cases = [
        ("project.dataset.public_data", True, "Public table allowed"),
        ("project.dataset.reports", True, "Regular table allowed"),
        ("project.dataset.sensitive_data", False, "Blacklisted table denied"),
        ("project.dataset.internal_users", False, "Another blacklisted table"),
        ("other.dataset.sensitive_data", False, "Different dataset entirely"),
    ]

    passed = 0
    for table, should_allow, description in test_cases:
        result = is_table_allowed(table, config)
        status = "✓" if result == should_allow else "✗"
        passed += (result == should_allow)

        print(f"  {status} {description:40} {'ALLOWED' if result else 'DENIED'}")

    print(f"\n  Results: {passed}/{len(test_cases)} passed\n")
    return passed, len(test_cases) - passed


def test_pattern_matching():
    """Test wildcard pattern matching."""
    print("="*70)
    print("Testing Pattern Matching (Wildcards)")
    print("="*70)

    config = {
        "allowed_patterns": [
            "bigquery-public-data.*.sales",  # All sales tables
            "my-project.public_*.*",         # All tables in datasets starting with public_
        ]
    }

    test_cases = [
        ("bigquery-public-data.iowa_liquor.sales", True, "Matches *.sales pattern"),
        ("bigquery-public-data.retail.sales", True, "Another sales table"),
        ("bigquery-public-data.iowa_liquor.transactions", False, "Not a sales table"),
        ("my-project.public_data.users", True, "Matches public_*.* pattern"),
        ("my-project.public_reports.summary", True, "Another public_* dataset"),
        ("my-project.private_data.users", False, "Not in public_* dataset"),
    ]

    passed = 0
    for table, should_allow, description in test_cases:
        result = is_table_allowed(table, config)
        status = "✓" if result == should_allow else "✗"
        passed += (result == should_allow)

        print(f"  {status} {description:40} {'ALLOWED' if result else 'DENIED'}")

    print(f"\n  Results: {passed}/{len(test_cases)} passed\n")
    return passed, len(test_cases) - passed


def test_hybrid_config():
    """Test hybrid configuration (all three modes together)."""
    print("="*70)
    print("Testing Hybrid Configuration (All Modes)")
    print("="*70)

    config = {
        "allowed_tables": [
            "specific.project.important_table"
        ],
        "allowed_datasets": {
            "bigquery-public-data.austin_bikeshare": {
                "allow_all_tables": True,
                "blacklisted_tables": ["internal_temp"]
            }
        },
        "allowed_patterns": [
            "analytics.*.sales"
        ]
    }

    test_cases = [
        # Table whitelist
        ("specific.project.important_table", True, "Specific table allowed"),

        # Dataset whitelist
        ("bigquery-public-data.austin_bikeshare.trips", True, "Dataset table allowed"),
        ("bigquery-public-data.austin_bikeshare.internal_temp", False, "Blacklisted table"),

        # Pattern matching
        ("analytics.retail.sales", True, "Matches pattern"),
        ("analytics.online.sales", True, "Another pattern match"),

        # Not allowed
        ("random.project.table", False, "Not in any allowlist"),
    ]

    passed = 0
    for table, should_allow, description in test_cases:
        result = is_table_allowed(table, config)
        status = "✓" if result == should_allow else "✗"
        passed += (result == should_allow)

        print(f"  {status} {description:40} {'ALLOWED' if result else 'DENIED'}")

    print(f"\n  Results: {passed}/{len(test_cases)} passed\n")
    return passed, len(test_cases) - passed


def test_pattern_matching_functions():
    """Test the pattern matching utility function."""
    print("="*70)
    print("Testing Pattern Matching Utility Function")
    print("="*70)

    test_cases = [
        ("project.dataset.table", "project.dataset.table", True, "Exact match"),
        ("project.dataset.sales", "project.*.sales", True, "Wildcard dataset"),
        ("project.data.sales", "project.*.sales", True, "Another wildcard match"),
        ("project.dataset.sales", "project.dataset.*", True, "Wildcard table"),
        ("any.thing.sales", "*.*.sales", True, "Multiple wildcards"),
        ("project.dataset.other", "project.*.sales", False, "No match"),
    ]

    passed = 0
    for table, pattern, should_match, description in test_cases:
        result = match_table_pattern(table, pattern)
        status = "✓" if result == should_match else "✗"
        passed += (result == should_match)

        match_text = "MATCH" if result else "NO MATCH"
        print(f"  {status} {description:40} [{table}] vs [{pattern}] {match_text}")

    print(f"\n  Results: {passed}/{len(test_cases)} passed\n")
    return passed, len(test_cases) - passed


if __name__ == "__main__":
    print("\n" + "="*70)
    print("Access Control Test Suite")
    print("="*70)

    total_passed = 0
    total_failed = 0

    passed, failed = test_table_whitelist()
    total_passed += passed
    total_failed += failed

    passed, failed = test_dataset_whitelist()
    total_passed += passed
    total_failed += failed

    passed, failed = test_dataset_with_blacklist()
    total_passed += passed
    total_failed += failed

    passed, failed = test_pattern_matching()
    total_passed += passed
    total_failed += failed

    passed, failed = test_hybrid_config()
    total_passed += passed
    total_failed += failed

    passed, failed = test_pattern_matching_functions()
    total_passed += passed
    total_failed += failed

    print("="*70)
    print("Summary")
    print("="*70)
    print(f"  Total Tests:  {total_passed + total_failed}")
    print(f"  Passed:       {total_passed} ✓")
    print(f"  Failed:       {total_failed}")

    if total_failed == 0:
        print(f"\n  🎉 All access control tests passed! 🎉\n")
    else:
        print(f"\n  ⚠️  Some tests failed\n")

    print("="*70 + "\n")

    sys.exit(0 if total_failed == 0 else 1)
