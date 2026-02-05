---
applyTo: "**/ralph-loop.sh,**/*.sh"
---

# Shell Script Instructions

When working with shell scripts:

## Style

- Use `#!/usr/bin/env bash` shebang
- Enable strict mode: `set -euo pipefail`
- Use lowercase for local variables, UPPERCASE for constants
- Quote all variable expansions: `"$variable"`

## Functions

- Use `local` for function-local variables
- Document functions with comments
- Return meaningful exit codes

## Compatibility

- Prefer POSIX-compatible constructs when possible
- Test on both Linux and macOS
- Use `$()` for command substitution, not backticks

## Copilot CLI Integration

- Use `copilot` command (not `gh copilot`)
- Default options: `--allow-all-tools --allow-all-paths`
- Support model fallback on failure
- Capture output to files for completion checking
