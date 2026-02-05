---
name: ralph-iteration
description: Guide for completing a single Ralph Mode iteration effectively. Use this when working through Ralph Mode iteration loops to ensure systematic progress.
---

# Ralph Iteration Skill

This skill guides you through completing one iteration of a Ralph Mode loop effectively.

## Steps

### 1. Context Gathering (2 min)

```bash
# Check current state
cat .ralph-mode/state.json

# Read the task
cat .ralph-mode/prompt.md

# See what changed in previous iterations
git log --oneline -5
git diff HEAD~1 --stat
```

### 2. Analysis (2 min)

- What's already been done?
- What's left to do?
- Are there any errors to fix?

### 3. Implementation (5-10 min)

Make targeted changes:
- Focus on ONE aspect of the task
- Don't try to do everything at once
- Make changes that can be verified

### 4. Verification (2 min)

```bash
# Run tests if applicable
npm test  # or pytest, etc.

# Check for errors
grep -r "TODO" src/ || true
grep -r "FIXME" src/ || true
```

### 5. Completion Check

Ask yourself:
- Does this meet ALL requirements?
- Have I tested the changes?
- Am I 100% confident?

If YES: Output `<promise>COMPLETION_PROMISE</promise>`
If NO: Document progress and continue next iteration

## Common Patterns

### Bug Fix Pattern
1. Reproduce the bug
2. Identify root cause
3. Fix the issue
4. Verify fix works
5. Check for regressions

### Feature Pattern
1. Understand requirements
2. Plan the implementation
3. Implement incrementally
4. Add tests
5. Document if needed

### Refactor Pattern
1. Ensure tests exist
2. Make small changes
3. Run tests after each change
4. Verify behavior unchanged
