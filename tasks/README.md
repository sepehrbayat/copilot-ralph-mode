# 📋 Task Library

This folder contains ready-to-use tasks for Ralph Mode.

## File Structure

```
tasks/
├── README.md              # This file
├── _groups/               # Task groups
│   ├── rtl.json           # RTL tasks
│   ├── testing.json       # Testing tasks
│   └── refactor.json      # Refactoring tasks
└── *.md                   # Individual tasks
```

## Task File Format (.md)

```markdown
---
id: TASK-001
title: Task title
tags: [rtl, ui]
model: gpt-5.2-codex
max_iterations: 20
completion_promise: DONE
---

Full task description...
```

## Usage

```bash
# Run a task by filename
python3 ralph_mode.py run --task rtl-fixes.md

# Run a task by ID
python3 ralph_mode.py run --task TASK-001

# Run a group of tasks
python3 ralph_mode.py run --group rtl

# List tasks
python3 ralph_mode.py tasks list

# Search tasks
python3 ralph_mode.py tasks search "RTL"
```
