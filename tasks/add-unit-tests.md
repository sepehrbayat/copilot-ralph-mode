---
id: TEST-001
title: Add unit tests for components
tags: [testing, jest, react]
model: claude-sonnet-4.5
max_iterations: 30
completion_promise: TESTS_ADDED
---

# Add Unit Tests

Add comprehensive unit tests for React components.

## Requirements

1. Use Jest and React Testing Library
2. Test all exported components
3. Cover edge cases
4. Mock external dependencies
5. Aim for 80%+ coverage

## Test Structure

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { ComponentName } from './ComponentName';

describe('ComponentName', () => {
  it('renders correctly', () => {
    render(<ComponentName />);
    expect(screen.getByRole('...')).toBeInTheDocument();
  });

  it('handles user interaction', () => {
    // ...
  });
});
```

## Verification

```bash
npm run test -- --coverage
```

## Completion

When tests are added and passing, output:
```
<promise>TESTS_ADDED</promise>
```
