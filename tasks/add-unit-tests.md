---
id: TEST-001
title: Add unit test for Button onClick handler
tags: [testing, jest, react]
model: gpt-5.2-codex
max_iterations: 10
completion_promise: TEST_BUTTON_DONE
---

# Add Unit Test for Button Click Handler

## Objective
Add one specific unit test for Button component's onClick functionality.

---

## Scope

- **ONLY modify:** `src/components/__tests__/Button.test.tsx`
- **DO NOT read:** Any other files or directories
- **DO NOT touch:** The component itself, other test files

---

## Pre-work

1. Confirm `src/components/__tests__/Button.test.tsx` exists and is writable
2. Identify current imports to avoid duplicates
3. Confirm no other files are required

---

## Changes Required (Mandatory)

1. **Add test case** to `Button.test.tsx`:

```typescript
it('calls onClick handler when clicked', () => {
  const handleClick = jest.fn();
  render(<Button onClick={handleClick}>Click me</Button>);
  
  fireEvent.click(screen.getByRole('button'));
  
  expect(handleClick).toHaveBeenCalledTimes(1);
});
```

2. **Add imports** if missing:
   - `fireEvent` from `@testing-library/react`
   - `jest` types if needed

---

## Acceptance Criteria

- [ ] New test case added to Button.test.tsx
- [ ] Test uses `fireEvent.click`
- [ ] Test verifies `onClick` was called
- [ ] Changes visible in `git diff`
- [ ] **If test already exists, task FAILS**

---

## Verification

```bash
# Should find the new test
grep -c "calls onClick handler" src/components/__tests__/Button.test.tsx

# Run the specific test
npm test -- --testPathPattern=Button.test.tsx --testNamePattern="calls onClick"
```

---

## Completion

**Only** when the test is added and can run, output:

```
<promise>TEST_BUTTON_DONE</promise>
```

---

## Notes

- Do NOT modify the Button component
- Do NOT add multiple tests
- Add ONLY the specific test described above
