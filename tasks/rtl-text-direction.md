---
id: RTL-001
title: Convert text-left/right to text-start/end
tags: [rtl, ui, tailwind]
model: gpt-5.2-codex
max_iterations: 20
completion_promise: RTL_TEXT_DONE
---

# RTL Text Direction Fix

Convert all directional text alignment classes to logical properties for RTL support.

## Changes Required

| Before | After |
|--------|-------|
| `text-left` | `text-start` |
| `text-right` | `text-end` |

## Scope

- All `.tsx` and `.ts` files in `packages/react-ui/src/`
- Tailwind CSS classes only

## Verification

```bash
# Should return 0 results after completion
grep -r "text-left\|text-right" packages/react-ui/src --include="*.tsx" --include="*.ts" | wc -l
```

## Completion

When ALL instances are converted, output:
```
<promise>RTL_TEXT_DONE</promise>
```
