# Test Suite for BigQuery MCP Server

Comprehensive test coverage for security, features, and functionality.

## Quick Start

### Run All Tests

```bash
# From project root
python tests/run_all_tests.py

# Or from tests directory
cd tests
python run_all_tests.py
```

### Run Individual Tests

```bash
# SQL validation tests
python tests/test_validation.py

# Feature tests (async, HTTP, cost estimation)
python tests/test_features.py
```

## Test Files

### 1. `run_all_tests.py` ⭐ **Run This!**

**Unified test runner** - runs all tests and provides summary.

**Coverage:**
- Module imports
- SQL validation (14 test cases)
- Async lifecycle management
- Cost estimation (dry-run)
- HTTP transport availability

**Output:**
```
========================================================================
              BigQuery MCP Server - Test Suite
========================================================================

──────────────────────────────────────────────────────────────────────
  1. SQL Validation & Security Tests
──────────────────────────────────────────────────────────────────────
  ✓ Basic SELECT                                     [VALID]
  ✓ DELETE in string literal                         [VALID]
  ✓ DELETE statement                                  [INVALID]
  ...

  Results: 14/14 passed

========================================================================
                           Test Summary
========================================================================
  Total Tests:     23
  Passed:          23 ✓
  Failed:          0
  Pass Rate:       100.0%

  🎉 All tests passed! 🎉
========================================================================
```

### 2. `test_validation.py`

**SQL security validation tests** - ensures only safe SELECT queries are allowed.

**Test Cases (14 total):**

✅ **Valid Queries:**
- Basic SELECT statements
- Lowercase queries
- String literals containing forbidden keywords
- Comments (single-line and multi-line)
- Trailing semicolons

❌ **Invalid Queries (Blocked):**
- DELETE, INSERT, UPDATE, DROP, CREATE, ALTER
- Multi-statement SQL injection attempts
- Semicolon-separated malicious queries

**Example:**
```python
# This should PASS (DELETE is in a string)
"SELECT * FROM table WHERE name='DELETE'"  ✓

# This should FAIL (actual DELETE)
"DELETE FROM table"  ✗
```

### 3. `test_features.py`

**Feature availability tests** - verifies new features are present.

**Tests:**
- Async lifecycle management
- Dry-run cost estimation
- HTTP transport capability
- Security validation (quick check)

**Note:** This tests that features exist and are importable. Full integration testing requires BigQuery authentication.

## Test Coverage

### Security Tests (14 cases)
- ✅ Basic query validation
- ✅ Keyword blocking (DELETE, UPDATE, INSERT, etc.)
- ✅ String literal handling
- ✅ Comment removal
- ✅ Multi-statement detection
- ✅ SQL injection prevention

### Feature Tests (9 cases)
- ✅ Module imports
- ✅ Async lifecycle context manager
- ✅ AppContext dataclass
- ✅ get_client() function
- ✅ estimate_query_cost tool
- ✅ create_http_app() function
- ✅ streamable_http_app() method

### Integration Tests
**Note:** Full integration tests require:
- Service account authentication
- Active BigQuery project
- Network access to BigQuery API

These are tested separately in development/staging environments.

## Running Tests in CI/CD

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python tests/run_all_tests.py
```

### Exit Codes

- `0` - All tests passed ✓
- `1` - Some tests failed ✗

## Test Organization

```
tests/
├── __init__.py              # Package marker
├── README.md                # This file
├── run_all_tests.py         # 🎯 Unified test runner
├── test_validation.py       # SQL security tests
└── test_features.py         # Feature availability tests
```

## Writing New Tests

### Adding to run_all_tests.py

```python
def test_my_feature() -> tuple[int, int]:
    """Test my new feature."""
    print_section("X. My Feature Tests")

    tests_passed = 0
    tests_failed = 0

    try:
        # Your test logic
        assert something == expected
        print("  ✓ Test description")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        tests_failed += 1

    return tests_passed, tests_failed

# Add to main():
passed, failed = test_my_feature()
total_passed += passed
total_failed += failed
```

### Creating Standalone Test

```python
#!/usr/bin/env python3
"""Test description."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Your imports
from server import my_function

# Your tests
def test_something():
    result = my_function()
    assert result == expected
    print("✓ Test passed")

if __name__ == "__main__":
    test_something()
```

## Common Issues

### Import Errors

If you get `ModuleNotFoundError`:

```bash
# Make sure you're running from project root
python tests/run_all_tests.py

# Or ensure parent directory is in path (already handled in tests)
```

### Authentication Errors

Some tests check feature availability without needing auth. Full integration tests require:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="service-account.json"
```

## Test Philosophy

### What We Test

✅ **Security validation** - Critical for production
✅ **Feature presence** - Ensure features exist
✅ **Module imports** - Catch missing dependencies
✅ **Function signatures** - API compatibility

### What We Don't Test (in unit tests)

❌ **BigQuery API calls** - Requires auth and network
❌ **End-to-end workflows** - Tested in staging
❌ **Performance** - Separate benchmarking suite

## Continuous Testing

### During Development

```bash
# Watch mode (requires entr or similar)
ls **/*.py | entr python tests/run_all_tests.py
```

### Before Commit

```bash
# Quick validation
python tests/run_all_tests.py

# If all pass, commit
git add .
git commit -m "Your changes"
```

### Before Deployment

```bash
# Run all tests
python tests/run_all_tests.py

# If tests pass, deploy
python server.py
```

## Test Results Archive

### Latest Results

Run `python tests/run_all_tests.py` to see current results.

### Expected Output

```
Total Tests:     23
Passed:          23 ✓
Failed:          0
Pass Rate:       100.0%
```

## Contributing

When adding new features:

1. Add tests to `run_all_tests.py`
2. Run full test suite
3. Ensure 100% pass rate
4. Update this README if needed

## Support

- **Issues**: Check test output for specific failures
- **Questions**: See main README.md
- **Bugs**: Create issue with test output

---

**Remember:** Run `python tests/run_all_tests.py` before deploying! 🚀
