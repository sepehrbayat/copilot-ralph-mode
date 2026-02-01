---
id: RTL-002
title: Convert ml/mr/pl/pr to ms/me/ps/pe
tags: [rtl, ui, tailwind]
model: gpt-5.2-codex
max_iterations: 20
completion_promise: RTL_SPACING_DONE
---

# RTL Margins and Padding Fix

Convert all directional margin and padding classes to logical properties for RTL support.

## Changes Required

| Before | After | Description |
|--------|-------|-------------|
| `ml-*` | `ms-*` | margin-left → margin-inline-start |
| `mr-*` | `me-*` | margin-right → margin-inline-end |
| `pl-*` | `ps-*` | padding-left → padding-inline-start |
| `pr-*` | `pe-*` | padding-right → padding-inline-end |

## Scope

- All `.tsx` and `.ts` files in `packages/react-ui/src/`
- Tailwind CSS classes only
- Include variants like `ml-auto`, `mr-2`, `pl-4`, etc.

## Verification

```bash
# Should return 0 results after completion
grep -r "\bml-\|\bmr-\|\bpl-\|\bpr-" packages/react-ui/src --include="*.tsx" --include="*.ts" | wc -l
```

## Completion

When ALL instances are converted, output:
```
<promise>RTL_SPACING_DONE</promise>
```
