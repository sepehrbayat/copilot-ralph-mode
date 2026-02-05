---
id: RTL-002
title: Convert ml/mr to ms/me in Card.tsx
tags: [rtl, ui, tailwind]
model: gpt-5.2-codex
max_iterations: 10
completion_promise: RTL_MARGIN_DONE
---

# Convert Directional Margins to Logical in Card Component

## Objective
Replace ml-*/mr-* with ms-*/me-* in Card.tsx for RTL support.

---

## Scope

- **ONLY modify:** `src/components/Card.tsx`
- **DO NOT read:** Any other files or directories
- **DO NOT touch:** `node_modules/`, `dist/`, other components

---

## Pre-work

1. Confirm `src/components/Card.tsx` exists and is writable
2. Identify all `ml-*`, `mr-*`, `pl-*`, `pr-*` classes in this file only
3. Confirm no other files are required

---

## Changes Required (Mandatory)

1. **Change left margin classes** in `Card.tsx`:
   - `ml-1` → `ms-1`
   - `ml-2` → `ms-2`
   - `ml-4` → `ms-4`
   - (any `ml-*` → `ms-*`)

2. **Change right margin classes** in `Card.tsx`:
   - `mr-1` → `me-1`
   - `mr-2` → `me-2`
   - `mr-4` → `me-4`
   - (any `mr-*` → `me-*`)

3. **Change left padding classes** (if exist):
   - `pl-*` → `ps-*`

4. **Change right padding classes** (if exist):
   - `pr-*` → `pe-*`

---

## Acceptance Criteria

- [ ] All `ml-*` replaced with `ms-*`
- [ ] All `mr-*` replaced with `me-*`
- [ ] All `pl-*` replaced with `ps-*`
- [ ] All `pr-*` replaced with `pe-*`
- [ ] Changes visible in `git diff`
- [ ] **If no directional classes exist, task FAILS**

---

## Verification

```bash
# Should return 0 (no old classes)
grep -E "ml-|mr-|pl-|pr-" src/components/Card.tsx | grep -v "ms-\|me-\|ps-\|pe-" | wc -l

# Should show the file was modified
git diff --name-only | grep Card.tsx
```

---

## Completion

**Only** when ALL changes are made, output:

```
<promise>RTL_MARGIN_DONE</promise>
```

---

## Notes

- Do NOT scan the entire codebase
- Do NOT read other component files
- Focus ONLY on Card.tsx
