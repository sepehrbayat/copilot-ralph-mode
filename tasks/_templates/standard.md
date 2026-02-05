---
id: TASK-XXX
title: [Descriptive title - what exactly will change]
tags: [tag1, tag2]
model: gpt-5.2-codex
max_iterations: 10
completion_promise: TASK_DONE
---

# [Task Title]

## Objective
[One sentence describing the exact change to make]

---

## Scope

- **ONLY modify:** `path/to/specific/file.ts`
- **DO NOT read:** Any other files or directories
- **DO NOT touch:** `node_modules/`, `dist/`, `.git/`

---

## Pre-work

1. Confirm the target file exists and is writable
2. Identify exact lines/locations to change
3. Confirm no other files are required

---

## Changes Required (Mandatory & Measurable)

1. **[Action verb] [exact element]** in `file.ts`:
   - Line X: Change `old_value` → `new_value`
   
2. **[Action verb] [exact element]**:
   - Add after line Y: `new_code_here`

> ⚠️ Each change must have: exact file, line number or location, before/after values

---

## Acceptance Criteria

- [ ] At least one real change in allowed files
- [ ] Changes visible in `git diff`
- [ ] Verification command passes
- [ ] **If no change needed, task MUST FAIL (not DONE)**

---

## Verification

```bash
# Command to verify the change was made
grep "expected_new_string" path/to/file.ts

# Or check that old string is gone
! grep "old_string" path/to/file.ts
```

---

## Completion

**Only** when ALL acceptance criteria are met, output:

```
<promise>TASK_DONE</promise>
```

---

## Notes

- Do NOT read any files outside the scope
- Do NOT scan or grep the entire codebase
- If the change already exists, the task FAILS
- Focus on the specific change, nothing else
