---
id: RTL-001
title: Convert text-left to text-start in Button.tsx
tags: [rtl, ui, tailwind]
model: gpt-5.2-codex
max_iterations: 10
completion_promise: RTL_TEXT_DONE
---

# Convert text-left to text-start in Button Component

## Objective
Replace directional text alignment class with logical property in Button.tsx.

---

## Scope

- **ONLY modify:** `src/components/Button.tsx`
- **DO NOT read:** Any other files or directories
- **DO NOT touch:** `node_modules/`, `dist/`, other components

---

## Pre-work

1. Confirm `src/components/Button.tsx` exists and is writable
2. Identify all `text-left` and `text-right` occurrences in this file only
3. Confirm no other files are required

---

## Changes Required (Mandatory)

1. **Change text alignment class** in `Button.tsx`:
   - Find: `text-left` 
   - Replace with: `text-start`
   
2. **Change text alignment class** (if exists):
   - Find: `text-right`
   - Replace with: `text-end`

> Each instance of `text-left` or `text-right` must be converted

---

## Acceptance Criteria

- [ ] All `text-left` replaced with `text-start` in Button.tsx
- [ ] All `text-right` replaced with `text-end` in Button.tsx  
- [ ] Changes visible in `git diff`
- [ ] **If no text-left/right exists, task FAILS**

---

## Verification

```bash
# Should return 0 (no old classes)
grep -c "text-left\|text-right" src/components/Button.tsx || echo "0"

# Should return at least 1 (new classes exist)
grep -c "text-start\|text-end" src/components/Button.tsx
```

---

## Completion

**Only** when ALL changes are made, output:

```
<promise>RTL_TEXT_DONE</promise>
```

---

## Notes

- Do NOT scan the entire codebase
- Do NOT read other component files
- Focus ONLY on Button.tsx
