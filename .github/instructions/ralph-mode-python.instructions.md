---
applyTo: "**/ralph_mode.py"
---

# Ralph Mode Python Instructions

When working with `ralph_mode.py`:

## Code Style

- Follow PEP 8 conventions
- Use type hints for all function parameters and return values
- Use dataclasses or TypedDict for structured data
- Keep functions focused and single-purpose

## Architecture

- `RalphMode` class handles all state management
- `TaskLibrary` class manages task files
- Keep CLI command handlers separate from business logic
- Use the `colors` singleton for terminal output

## Testing

- Tests are in `tests/test_ralph_mode.py`
- Use pytest for testing
- Mock file system operations when possible
- Test both success and error paths

## Error Handling

- Raise `ValueError` for user input errors
- Use descriptive error messages
- Always clean up resources on failure
