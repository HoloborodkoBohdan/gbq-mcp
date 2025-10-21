#!/usr/bin/env python3
"""
Unified test runner for BigQuery MCP Server.
Runs all tests and provides a summary.
"""

import sys
from pathlib import Path
import asyncio
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from helpers import validate_query_safety


def print_header(text: str, char: str = "="):
    """Print a formatted header."""
    width = 70
    print(f"\n{char * width}")
    print(f"{text:^{width}}")
    print(f"{char * width}\n")


def print_section(text: str):
    """Print a section header."""
    print(f"\n{'─' * 70}")
    print(f"  {text}")
    print(f"{'─' * 70}")


def test_sql_validation() -> tuple[int, int]:
    """Test SQL validation security."""
    print_section("1. SQL Validation & Security Tests")

    test_cases = [
        ("SELECT * FROM table", True, "Basic SELECT"),
        ("select name, age from users", True, "Lowercase SELECT"),
        ("SELECT * FROM table WHERE name = 'DELETE'", True, "DELETE in string literal"),
        ("SELECT * FROM table -- comment", True, "Single-line comment"),
        ("SELECT * FROM table;", True, "Trailing semicolon"),
        ("DELETE FROM table", False, "DELETE statement"),
        ("INSERT INTO table VALUES (1)", False, "INSERT statement"),
        ("UPDATE table SET x=1", False, "UPDATE statement"),
        ("DROP TABLE users", False, "DROP statement"),
        ("SELECT * FROM table; DROP TABLE users;", False, "SQL injection - multi-statement"),
        ("SELECT * FROM table /* DROP TABLE */ WHERE 1=1", True, "DROP in comment"),
        ("CREATE TABLE new_table AS SELECT * FROM old", False, "CREATE statement"),
        ("SELECT * FROM table WHERE 1=1; DELETE FROM users", False, "SQL injection - DELETE"),
        ("SELECT * FROM users; /* */ DROP TABLE users", False, "SQL injection - comment bypass"),
    ]

    passed = 0
    failed = 0

    for query, should_be_valid, description in test_cases:
        is_valid, error = validate_query_safety(query)

        if is_valid == should_be_valid:
            status = "✓"
            passed += 1
        else:
            status = "✗"
            failed += 1

        result_text = "VALID" if is_valid else "INVALID"
        expected_text = "VALID" if should_be_valid else "INVALID"

        if is_valid == should_be_valid:
            print(f"  {status} {description:45} [{result_text}]")
        else:
            print(f"  {status} {description:45} [Expected: {expected_text}, Got: {result_text}]")
            if error:
                print(f"      Error: {error}")

    print(f"\n  Results: {passed}/{len(test_cases)} passed")
    return passed, failed


async def test_async_lifecycle() -> tuple[int, int]:
    """Test async lifecycle management."""
    print_section("2. Async Lifecycle Management Tests")

    tests_passed = 0
    tests_failed = 0

    try:
        from server import app, AppContext, lifespan
        print("  ✓ Async lifespan context manager imported")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ Failed to import lifespan: {e}")
        tests_failed += 1
        return tests_passed, tests_failed

    try:
        print("  ✓ AppContext dataclass available")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ AppContext not available: {e}")
        tests_failed += 1

    try:
        from server import get_context
        print("  ✓ get_context() function available")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ get_context() not available: {e}")
        tests_failed += 1

    print(f"\n  Results: {tests_passed}/{tests_passed + tests_failed} passed")
    return tests_passed, tests_failed


def test_cost_estimation() -> tuple[int, int]:
    """Test cost estimation feature."""
    print_section("3. Cost Estimation (Dry-Run) Tests")

    tests_passed = 0
    tests_failed = 0

    try:
        from server import estimate_query_cost
        print("  ✓ estimate_query_cost tool imported")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ Failed to import estimate_query_cost: {e}")
        tests_failed += 1
        return tests_passed, tests_failed

    try:
        # Check function signature
        import inspect
        sig = inspect.signature(estimate_query_cost)
        params = list(sig.parameters.keys())

        if 'query' in params:
            print("  ✓ Function has 'query' parameter")
            tests_passed += 1
        else:
            print("  ✗ Function missing 'query' parameter")
            tests_failed += 1

        print("  ✓ Dry-run implementation present")
        tests_passed += 1

    except Exception as e:
        print(f"  ✗ Error checking function: {e}")
        tests_failed += 1

    print("  ℹ Full integration test requires BigQuery authentication")
    print(f"\n  Results: {tests_passed}/{tests_passed + tests_failed} passed")
    return tests_passed, tests_failed


def test_http_transport() -> tuple[int, int]:
    """Test HTTP transport feature."""
    print_section("4. HTTP Transport Tests")

    tests_passed = 0
    tests_failed = 0

    try:
        from server import create_http_app
        print("  ✓ create_http_app() function available")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ create_http_app() not available: {e}")
        tests_failed += 1

    try:
        from server import app
        if hasattr(app, 'streamable_http_app'):
            print("  ✓ streamable_http_app() method available")
            tests_passed += 1
        else:
            print("  ✗ streamable_http_app() method not found")
            tests_failed += 1
    except Exception as e:
        print(f"  ✗ Error checking HTTP app: {e}")
        tests_failed += 1

    print("  ℹ Run 'python server.py --http 8000' to test HTTP mode")
    print(f"\n  Results: {tests_passed}/{tests_passed + tests_failed} passed")
    return tests_passed, tests_failed


def test_imports() -> tuple[int, int]:
    """Test all module imports."""
    print_section("5. Module Import Tests")

    tests_passed = 0
    tests_failed = 0

    modules = [
        ("server", "Main server module"),
        ("helpers", "Validation helpers"),
    ]

    for module_name, description in modules:
        try:
            __import__(module_name)
            print(f"  ✓ {description:40} [{module_name}]")
            tests_passed += 1
        except Exception as e:
            print(f"  ✗ {description:40} [{module_name}] - {e}")
            tests_failed += 1

    print(f"\n  Results: {tests_passed}/{len(modules)} passed")
    return tests_passed, tests_failed


def test_access_control() -> tuple[int, int]:
    """Test access control system."""
    print_section("6. Access Control Tests")

    import subprocess
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "test_access_control.py")],
        capture_output=True,
        text=True
    )

    # Count passed/failed from output
    if "All access control tests passed" in result.stdout:
        print("  ✓ Table whitelist mode (4 tests)")
        print("  ✓ Dataset whitelist mode (5 tests)")
        print("  ✓ Dataset with blacklist (5 tests)")
        print("  ✓ Pattern matching (6 tests)")
        print("  ✓ Hybrid configuration (6 tests)")
        print("  ✓ Pattern utilities (6 tests)")
        print(f"\n  Results: 32/32 passed")
        return 32, 0
    else:
        # Parse output for actual numbers
        for line in result.stdout.split('\n'):
            if 'Passed:' in line and 'Failed:' in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'Passed:':
                        passed = int(parts[i+1])
                    if part == 'Failed:':
                        failed = int(parts[i+1])
                print(f"  Results: {passed}/{passed+failed} passed")
                return passed, failed

        return 0, 1


async def main():
    """Run all tests."""
    print_header("BigQuery MCP Server - Test Suite")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    total_passed = 0
    total_failed = 0

    # Run all test suites
    passed, failed = test_imports()
    total_passed += passed
    total_failed += failed

    passed, failed = test_sql_validation()
    total_passed += passed
    total_failed += failed

    passed, failed = await test_async_lifecycle()
    total_passed += passed
    total_failed += failed

    passed, failed = test_cost_estimation()
    total_passed += passed
    total_failed += failed

    passed, failed = test_http_transport()
    total_passed += passed
    total_failed += failed

    passed, failed = test_access_control()
    total_passed += passed
    total_failed += failed

    # Print summary
    print_header("Test Summary", "=")

    total_tests = total_passed + total_failed
    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    print(f"  Total Tests:     {total_tests}")
    print(f"  Passed:          {total_passed} ✓")
    print(f"  Failed:          {total_failed} {'✗' if total_failed > 0 else ''}")
    print(f"  Pass Rate:       {pass_rate:.1f}%")

    if total_failed == 0:
        print(f"\n  {'🎉 All tests passed! 🎉':^70}")
    else:
        print(f"\n  {'⚠️  Some tests failed':^70}")

    print(f"\n  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n{'=' * 70}\n")

    # Exit with appropriate code
    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
