---
id: RTL-003
title: Convert left/right positioning to start/end
tags: [rtl, ui, tailwind, css]
model: gpt-5.2-codex
max_iterations: 20
completion_promise: RTL_POSITION_DONE
---

# RTL Flex and Positioning Fix

Convert all directional positioning classes to logical properties for RTL support.

## Changes Required

| Before | After | Description |
|--------|-------|-------------|
| `left-*` | `start-*` | Positioning |
| `right-*` | `end-*` | Positioning |
| `border-l-*` | `border-s-*` | Border left |
| `border-r-*` | `border-e-*` | Border right |
| `rounded-l-*` | `rounded-s-*` | Border radius left |
| `rounded-r-*` | `rounded-e-*` | Border radius right |

## Scope

- All `.tsx` and `.ts` files in `packages/react-ui/src/`
- Tailwind CSS classes only

## Exceptions

Keep these as-is (they are not directional):
- `translate-x-*`
- `rotate-*`
- `scale-*`

## Verification

```bash
# Should return 0 results after completion
grep -r "\bleft-\|\bright-\|\bborder-l-\|\bborder-r-" packages/react-ui/src --include="*.tsx" --include="*.ts" | wc -l
```

## Completion

When ALL instances are converted, output:
```
<promise>RTL_POSITION_DONE</promise>
```
