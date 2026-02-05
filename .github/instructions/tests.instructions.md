---
applyTo: "**/tests/**"
---

# Test Instructions

When working with tests:

## Framework

- Use pytest for Python tests
- Use Jest for JavaScript/TypeScript tests

## Test Structure

- Test files should be named `test_*.py` or `*.test.ts`
- Group related tests in classes or describe blocks
- Use descriptive test names

## Coverage

- Test happy paths and error paths
- Test edge cases
- Mock external dependencies

## Running Tests

```bash
# Python
python -m pytest tests/ -v

# JavaScript
npm test
```
