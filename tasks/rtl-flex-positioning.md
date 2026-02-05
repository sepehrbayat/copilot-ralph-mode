---
id: RTL-003
title: Convert left/right positioning to start/end in Modal.tsx
tags: [rtl, ui, tailwind, css]
model: gpt-5.2-codex
max_iterations: 10
completion_promise: RTL_POS_DONE
---

# Convert Directional Positioning to Logical in Modal Component

## Objective
Replace left-*/right-* with start-*/end-* in Modal.tsx for RTL support.

---

## Scope

- **ONLY modify:** `src/components/Modal.tsx`
- **DO NOT read:** Any other files or directories
- **DO NOT touch:** `node_modules/`, `dist/`, other components

---

## Pre-work

1. Confirm `src/components/Modal.tsx` exists and is writable
2. Identify all Tailwind `left-*` and `right-*` classes in this file only
3. Confirm no other files are required

---

## Changes Required (Mandatory)

1. **Change left positioning** in `Modal.tsx`:
   - `left-0` → `start-0`
   - `left-1` → `start-1`
   - `left-4` → `start-4`
   - (any `left-*` → `start-*`)

2. **Change right positioning** in `Modal.tsx`:
   - `right-0` → `end-0`
   - `right-1` → `end-1`
   - `right-4` → `end-4`
   - (any `right-*` → `end-*`)

---

## Acceptance Criteria

- [ ] All `left-*` (positioning) replaced with `start-*`
- [ ] All `right-*` (positioning) replaced with `end-*`
- [ ] Changes visible in `git diff`
- [ ] **If no directional positioning exists, task FAILS**

---

## Verification

```bash
# Should return 0 (no old positioning classes)
grep -E "\bleft-[0-9]|\bright-[0-9]" src/components/Modal.tsx | wc -l

# Should show the file was modified  
git diff --stat src/components/Modal.tsx
```

---

## Completion

**Only** when ALL changes are made, output:

```
<promise>RTL_POS_DONE</promise>
```

---

## Notes

- Do NOT scan the entire codebase
- Do NOT read other component files
- Focus ONLY on Modal.tsx
- Be careful not to change CSS `left:` properties, only Tailwind classes
