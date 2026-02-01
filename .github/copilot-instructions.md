# 🔄 Copilot Ralph Mode Instructions

> This file is read by GitHub Copilot when Ralph Mode is active.

## Detecting Ralph Mode

Check if `.ralph-mode/state.json` exists in the workspace root. If it exists, Ralph Mode is active.

## When Ralph Mode is Active

### Step 1: Read the State

```bash
cat .ralph-mode/state.json
```

Look for:
- `iteration`: Current iteration number
- `max_iterations`: Maximum allowed (0 = unlimited)
- `completion_promise`: Text to output when genuinely done
- `started_at`: When the loop started
- `mode`: `single` or `batch`
- `current_task_index`: only in batch mode

### Step 2: Read the Task

```bash
cat .ralph-mode/prompt.md
```

This contains the task you need to work on.

### If Batch Mode is Active

- Task list: `.ralph-mode/tasks.json`
- Task files: `.ralph-mode/tasks/*.md`
- Current task: `current_task_index` in `state.json`

### Step 3: Work on the Task

- Make incremental improvements each iteration
- Run tests if applicable
- Fix errors you encounter
- Build on previous work (visible in files and git history)

### Step 4: Check Completion

Are ALL requirements met?

- **YES**: Output `<promise>COMPLETION_PROMISE_VALUE</promise>`
- **NO**: Continue working, iterate again

## Critical Rules

### ⚠️ Completion Promise

If a completion promise is set:

1. **ONLY** output `<promise>VALUE</promise>` when the task is **GENUINELY COMPLETE**
2. The statement must be **COMPLETELY AND UNEQUIVOCALLY TRUE**
3. **NEVER** lie to exit the loop
4. If stuck, document blockers instead of false promises

### 🔄 Iteration Pattern

Each iteration:
1. The SAME prompt is fed to you
2. Your previous work is visible in files
3. Git history shows your changes
4. You improve incrementally until done

### 📊 Tracking Progress

- Update files with your changes
- Commit meaningful progress to git
- Check test results if applicable
- Document what's done vs remaining

## Example Workflow

```
Iteration 1: Read task → Create initial implementation
Iteration 2: Run tests → Fix failing tests  
Iteration 3: Add edge cases → Handle errors
Iteration 4: All tests pass → <promise>COMPLETE</promise>
```

## Philosophy

- **Iteration > Perfection**: Small improvements compound
- **Failures Are Data**: Learn from errors
- **Persistence Wins**: Keep iterating

## Commands Reference

```bash
# Check status
python ralph_mode.py status

# View prompt
python ralph_mode.py prompt

# View history
python ralph_mode.py history

# Increment iteration
python ralph_mode.py iterate

# Disable
python ralph_mode.py disable
```
