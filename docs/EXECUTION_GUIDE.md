# 📘 Ralph Mode Execution Guide

This guide standardizes Ralph Mode execution, effective task design, and prevents read-only behavior.

---

## Part 1: Execution Principles

1. **Always run from project root** - Never cd into subdirectories
2. **Dedicated terminal for loop** - Don't run other commands in the same terminal
3. **Real file changes required** - Every iteration must produce visible diffs
4. **Tasks must be measurable and scoped** - Vague tasks lead to read-only behavior

---

## Part 2: Standard Task Template (Required for Code Changes)

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
One sentence describing the exact change to make.

## Scope

- **ONLY modify:** `path/to/specific/file.ts` (max 1-2 files)
- **DO NOT read:** Any other files or directories
- **DO NOT touch:** [forbidden paths]

## Pre-work

1. Confirm the target file exists and is writable
2. Identify the exact lines/locations to change
3. Confirm no other files are required

## Changes Required (Mandatory & Measurable)

1. **Add constant X** to line Y in `file.ts`
2. **Change type of Z** from `string` to `number`
3. [Each change must have exact element name and expected result]

## Acceptance Criteria

- [ ] At least one real change in allowed files
- [ ] Changes visible in `git diff`
- [ ] If no change needed, task MUST fail (not DONE)

## Verification

```bash
# Specific check command
grep "NEW_CONSTANT" path/to/file.ts
```

## Completion

Only when ALL items are done:
```
<promise>TASK_DONE</promise>
```

## Notes

- Do NOT read any other files
- If new file needed, task must explicitly allow it
```

---

## Part 3: Common Problem - Read-Only Behavior

### Symptoms
- Model only runs `grep`, `cat`, `find`
- No actual file modifications
- Loop exits with DONE but no changes

### Causes
1. **Vague tasks** - "Fix all RTL issues" is too broad
2. **Change already exists** - Model verifies instead of modifying
3. **No explicit modification instruction** - Task asks to "check" not "change"

### Permanent Solutions

1. **One file, one change** - Task must specify exactly which file and what change
2. **Add "DO NOT read other files"** - Prevents scanning behavior
3. **Use imperative language** - "Add constant X" not "Ensure constant X exists"
4. **Require visible diff** - Task fails if no `git diff` output

---

## Part 4: Docker Execution Flow

```bash
# 1. Start Docker Desktop

# 2. Run container with volume mount
docker run -it --name ralph-ubuntu \
  -v /path/to/target/project:/workspace \
  -v /path/to/ralph-mode:/ralph-mode \
  ubuntu:22.04 bash

# 3. Inside container - Install dependencies
apt update && apt install -y python3 python3-pip python3-venv git curl

# 4. Create venv (required for PEP 668)
cd /ralph-mode
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # if exists

# 5. Copy tasks to ralph-mode
cp /workspace/my-tasks/*.md /ralph-mode/tasks/

# 6. For batch mode - use tasks-file JSON (required)
cat > /tmp/tasks.json << 'EOF'
[
  {"prompt": "tasks/task1.md"},
  {"prompt": "tasks/task2.md"}
]
EOF

# 7. Initialize and run
cd /workspace  # Run from target project root!
python3 /ralph-mode/ralph_mode.py batch-init --tasks-file /tmp/tasks.json
/ralph-mode/ralph-loop.sh run
```

---

## Part 4.1: Task Library Groups (Non-JSON)

If you use task files and groups in `tasks/_groups/`, load them directly:

```bash
# Run from target project root
python3 /ralph-mode/ralph_mode.py run --group rtl
/ralph-mode/ralph-loop.sh run
```

---

## Part 5: Pre-Execution Checklist

- [ ] Copilot account active with sufficient quota
- [ ] Running from project root (not ralph-mode folder)
- [ ] Tasks are scoped and specific
- [ ] Loop terminal is dedicated (no other commands)
- [ ] Target files exist and are writable
- [ ] Git initialized (for diff verification)

---

## Part 6: Quick Debugging

| Problem | Solution |
|---------|----------|
| Only read/grep, no changes | Make task more specific, add "ONLY modify" |
| batch-init error | Use `--tasks-file` (tasks-dir not supported) |
| Quota error | Copilot needs subscription/charge |
| Loop exits immediately | Check `completion_promise` format |
| No diff after completion | Task was already satisfied, redesign it |
| Permission denied | Check file ownership in Docker |

---

## Part 7: Task Design Anti-Patterns

### ❌ Bad Task
```markdown
Fix all RTL issues in the codebase.
```

### ✅ Good Task
```markdown
## Scope
- ONLY modify: `src/components/Button.tsx`
- DO NOT read: Any other files

## Changes Required
1. Line 15: Change `ml-4` to `ms-4`
2. Line 23: Change `text-left` to `text-start`

## Acceptance Criteria
- File must have exactly 2 lines changed
- `git diff` shows modifications
```

---

## Part 8: Verification Commands

```bash
# Check if ralph-mode is active
python3 ralph_mode.py status

# View current prompt
python3 ralph_mode.py prompt

# Check iteration history
python3 ralph_mode.py history

# Verify changes were made
git diff
git diff --stat

# Count modified files
git diff --name-only | wc -l
```

---

## Part 9: Real-World Lessons (Quick Reference)

- **Copilot CLI install**: use a user-writable prefix to avoid EACCES
  - `npm config set prefix "$HOME/.local"`
  - `NPM_CONFIG_PREFIX="$HOME/.local" npm install -g @github/copilot`
- **Loop terminal**: avoid interactive prompts; they break unattended runs
- **Batch mode**: always provide `tasks.json` for grouped tasks
- **Target repo**: ensure `.ralph-mode/` exists before running the loop
- **PR hygiene**: keep branch names neutral and use standard PR sections

Full notes: [docs/LESSONS_LEARNED.md](docs/LESSONS_LEARNED.md)
