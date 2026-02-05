---
name: test-runner
description: Guide for running and analyzing test results across different languages and frameworks. Use this when you need to run tests, interpret test failures, or ensure test coverage.
---

# Test Runner Skill

This skill provides standardized ways to run tests and interpret results.

## Test Commands by Language

### Python
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_specific.py -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=term-missing
```

### JavaScript/TypeScript
```bash
# Run all tests
npm test

# Run specific test
npm test -- --grep "test name"

# With coverage
npm run test:coverage
```

### Go
```bash
# Run all tests
go test ./...

# With verbose output
go test -v ./...

# With coverage
go test -cover ./...
```

## Interpreting Results

### Success Indicators
- All tests pass
- No deprecation warnings
- Coverage meets threshold

### Failure Patterns

#### Test Assertion Failed
```
AssertionError: Expected X, got Y
```
→ Fix the code to produce expected output

#### Import Error
```
ModuleNotFoundError: No module named 'xyz'
```
→ Install missing dependency or fix import path

#### Timeout
```
TimeoutError: Test exceeded 30s limit
```
→ Optimize the code or increase timeout

## Quick Actions

### Fix Failing Test
1. Read the error message carefully
2. Find the relevant code
3. Fix the issue
4. Re-run just that test

### Add Missing Test
1. Identify untested code
2. Create test file if needed
3. Write test following existing patterns
4. Run to verify it passes
