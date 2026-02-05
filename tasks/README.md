# 📋 Task Library

This folder contains ready-to-use tasks for Ralph Mode.

## ⚠️ Important: Task Design Rules

Tasks **MUST** be specific and scoped to prevent read-only behavior:

1. **Specify exact files** - Max 1-2 files per task
2. **Add "DO NOT read"** - Prevents scanning behavior  
3. **Require measurable changes** - Each change must be verifiable
4. **Use imperative language** - "Add X" not "Ensure X exists"

See [docs/EXECUTION_GUIDE.md](../docs/EXECUTION_GUIDE.md) for the canonical standard.

---

## File Structure

```
tasks/
├── README.md              # This file
├── _groups/               # Task groups
│   ├── rtl.json
│   └── testing.json
├── _templates/            # Task templates
│   └── standard.md
└── *.md                   # Individual tasks
```

---

## Standard Task Format

```markdown
---
id: TASK-001
title: Descriptive title
tags: [tag1, tag2]
model: gpt-5.2-codex
max_iterations: 10
completion_promise: TASK_DONE
---

# Task Title

## Objective
[One sentence - exact change required]

## Scope

- **ONLY modify:** `path/to/file.ts`
- **DO NOT read:** Any other files
- **DO NOT touch:** [forbidden paths]

## Pre-work

1. Confirm the target file exists and is writable
2. Identify exact lines/locations to change
3. Confirm no other files are required

## Changes Required (Mandatory)

1. **Change X** in line Y: `old` → `new`
2. **Add Y** after line Z

## Acceptance Criteria

- [ ] At least one real file change
- [ ] Visible in `git diff`
- [ ] If no change needed → task FAILS

## Verification

```bash
grep "expected_string" path/to/file.ts
```

## Completion

Only when ALL done:
```
<promise>TASK_DONE</promise>
```
```

---

## Usage

```bash
# Run a single task
python3 ralph_mode.py run --task rtl-text-direction.md

# Run by ID
python3 ralph_mode.py run --task RTL-001

# Run a group
python3 ralph_mode.py run --group rtl

# List all tasks
python3 ralph_mode.py tasks list

# Search tasks
python3 ralph_mode.py tasks search "RTL"

# Show task details
python3 ralph_mode.py tasks show RTL-001
```

---

## Batch Mode (Multiple Tasks)

```bash
# Create tasks file
cat > tasks.json << 'EOF'
[
  {"prompt": "tasks/task1.md"},
  {"prompt": "tasks/task2.md"}
]
EOF

# Initialize batch
python3 ralph_mode.py batch-init --tasks-file tasks.json

# Run
./ralph-loop.sh run
```

---

## Common Mistakes

| ❌ Bad | ✅ Good |
|--------|---------|
| "Fix RTL issues" | "Change `ml-4` to `ms-4` in Button.tsx line 15" |
| No scope defined | "ONLY modify: `src/Button.tsx`" |
| "Ensure X exists" | "Add X to line Y" |
| No acceptance criteria | "git diff must show changes" |
