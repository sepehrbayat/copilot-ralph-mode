---
applyTo: "**/tasks/**/*.md"
---

# Task File Instructions

When creating or modifying task files:

## Format

Task files should use this structure:

```markdown
---
id: TASK-001
title: Short Title
tags: [tag1, tag2]
model: gpt-5.2-codex
max_iterations: 10
completion_promise: TASK_DONE
---

# Task Title

## Objective
One sentence describing the exact change to make.

## Scope
- ONLY modify: `path/to/specific/file.ts`
- DO NOT read: Any other files or directories
- DO NOT touch: `other/paths`

## Pre-work
1. Confirm the target file exists and is writable
2. Identify exact lines/locations to change
3. Confirm no other files are required

## Changes Required
1. Specific change with before/after values
2. Specific change with before/after values

## Acceptance Criteria
- [ ] At least one real file change
- [ ] Changes visible in `git diff`
- [ ] If no change needed, task MUST fail (not DONE)

## Verification
```bash
grep "expected_string" path/to/specific/file.ts
```

## Completion
Only when all criteria are met: <promise>TASK_DONE</promise>
```

## Best Practices

- Be specific about file paths (max 1-2 files)
- Include clear boundaries (ONLY modify / DO NOT read / DO NOT touch)
- List acceptance criteria as checkboxes
- Require visible `git diff`
- If a change already exists, the task must FAIL
