# 🔄 Copilot Ralph Mode Instructions

> Repository-wide custom instructions for GitHub Copilot CLI integration.

## Overview

This repository implements **Ralph Mode** - an iterative, self-referential AI development loop for GitHub Copilot CLI. These instructions help Copilot understand how to work within the Ralph loop pattern.

---

## Detecting Ralph Mode

Check if `.ralph-mode/state.json` exists in the workspace root. If it exists, Ralph Mode is active.

```bash
# Check if active
test -f .ralph-mode/state.json && echo "Ralph Mode is ACTIVE"
```

---

## When Ralph Mode is Active

### Step 1: Read the State

```bash
cat .ralph-mode/state.json
```

Important fields:
- `iteration`: Current iteration number
- `max_iterations`: Maximum allowed (0 = unlimited)
- `completion_promise`: Text to output when genuinely done
- `started_at`: When the loop started
- `mode`: `single` or `batch`
- `current_task_index`: Only in batch mode
- `model`: The AI model being used

### Step 2: Read the Task

```bash
cat .ralph-mode/prompt.md
```

This contains the task you need to work on.

### Step 3: Check Previous Work

```bash
# See recent changes
git diff HEAD~1

# Or check the history
cat .ralph-mode/history.jsonl
```

### Step 4: Work on the Task

- Make incremental improvements each iteration
- Run tests if applicable
- Fix errors you encounter
- Build on previous work (visible in files and git history)

### Step 5: Check Completion

Are ALL requirements met?

- **YES**: Output `<promise>COMPLETION_PROMISE_VALUE</promise>`
- **NO**: Continue working, iterate again

---

## Batch Mode

When `mode` is `batch`:

- Task list: `.ralph-mode/tasks.json`
- Task files: `.ralph-mode/tasks/*.md`
- Current task: `current_task_index` in `state.json`

After completing one task, the loop automatically moves to the next.

---

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

---

## Memory System (mem0-inspired)

Ralph Mode includes a multi-level memory system inspired by [mem0](https://github.com/mem0ai/mem0) that persists knowledge across iterations.

### Memory Levels

| Level | Purpose | Persistence |
|-------|---------|-------------|
| **Working** | Current iteration scratch notes | Cleared each iteration |
| **Episodic** | Per-iteration summaries (what happened, what changed) | Survives across iterations |
| **Semantic** | Extracted facts, patterns, relationships | Survives across tasks |
| **Procedural** | Learned workflows ("to fix X, run Y then Z") | Long-term |

### Memory Categories

`file_changes`, `errors`, `decisions`, `blockers`, `progress`, `patterns`, `dependencies`, `test_results`, `environment`, `task_context`

### How Memory Works in the Loop

Each iteration automatically:
1. **Clears** working memory (fresh start)
2. Runs the AI with full context including Memory Bank
3. **Extracts** episodic memories from output (files changed, errors, test results)
4. **Extracts** semantic facts (dependencies, decisions, fix patterns)
5. **Decays** old memory scores (recency bias)
6. **Promotes** frequently-accessed episodic memories to semantic

### Using Memory from CLI

```bash
python3 ralph_mode.py memory stats       # View memory bank statistics
python3 ralph_mode.py memory show        # Display formatted memory for context
python3 ralph_mode.py memory search "auth login"  # Search by relevance
python3 ralph_mode.py memory add "project uses React" --category dependencies
python3 ralph_mode.py memory extract     # Extract from last output
python3 ralph_mode.py memory decay       # Apply temporal decay
python3 ralph_mode.py memory promote     # Promote episodic → semantic
python3 ralph_mode.py memory reset       # Clear all memories
```

---

## File Editing Best Practices

### BEFORE Editing

1. **Read first** — always read the file (or relevant section) before editing.
2. **Check git** — run `git diff` to see if a previous iteration already made changes.
3. **Check Memory Bank** — search for prior edits to the same file.

### WHEN Editing

1. Use precise, targeted edits — replace only the lines that need to change.
2. Include enough context (3+ surrounding lines) to anchor the edit uniquely.
3. Preserve whitespace, indentation, and coding style.
4. Never guess at file contents — always read before editing.

### AFTER Editing

1. **Verify** — read the modified section back to confirm correctness.
2. **Test** — run relevant tests or linters if available.
3. **Record** — note what you changed in progress.

### Common Mistakes

- Editing without reading first (stale content).
- Remaking changes that already exist from a previous iteration.
- Using `...existing code...` placeholders instead of actual content.
- Trying to edit too many lines at once — split into smaller edits.

---

## Copilot CLI Integration

### Slash Commands

While in Ralph Mode, you can use these Copilot CLI commands:

| Command | Description |
|---------|-------------|
| `/context` | View current token usage |
| `/compact` | Compress conversation history |
| `/usage` | View session statistics |
| `/review` | Review code changes |
| `/agent` | Select a custom agent |
| `/cwd` | Change working directory |
| `/add-dir` | Add a trusted directory |
| `/resume` | Resume a previous session |
| `/mcp add` | Add an MCP server |

### Custom Agents

Available agents in `.github/agents/`:

| Agent | Use For |
|-------|---------|
| `ralph` | Main Ralph Mode iteration work |
| `plan` | Creating implementation plans |
| `code-review` | Reviewing changes |
| `task` | Running tests and builds |
| `explore` | Codebase exploration without context pollution |
| `agent-creator` | Meta-agent for creating new agents |

### Dynamic Sub-Agent Creation (Auto-Agents)

When `--auto-agents` is enabled, you can **dynamically create sub-agents** during iterations:

#### How to Create Sub-Agents

1. Create a `.agent.md` file in `.github/agents/`:

```markdown
---
name: my-custom-agent
description: What this agent does
tools:
  - read_file
  - edit_file
  - run_in_terminal
---

# Agent Instructions

Your specialized instructions here...
```

2. Invoke with: `@my-custom-agent <task description>`

#### When to Create Sub-Agents

- Complex subtasks requiring focused context
- Repetitive operations benefiting from dedicated tooling
- Parallel workstreams needing isolation
- Code review, testing, or refactoring tasks

#### Agent Design Guidelines

- **Single Responsibility**: Each agent should do one thing well
- **Minimal Tools**: Only include tools the agent needs
- **Clear Instructions**: Be explicit about capabilities

Use `@agent-creator` for guidance on creating new agents.

### File References

Use `@` to reference files in prompts:
```
Fix the bug in @src/auth/login.ts
```

### Plan Mode

Press `Shift+Tab` to enter plan mode - collaborate on implementation plans before writing code.

### Delegating to Copilot Coding Agent

Use `/delegate` or prefix with `&` to hand off tasks to Copilot coding agent:
```
/delegate complete the API integration tests
& fix all failing edge cases
```

---

## Tracking Progress

- Update files with your changes
- History is logged in `.ralph-mode/history.jsonl`
- Check test results if applicable
- Document what's done vs remaining

---

## Context Management

Copilot CLI automatically manages context. To help:

1. Keep changes focused on the current task
2. Don't load unnecessary files into context
3. Use `/compact` if context fills up
4. Use the `explore` agent for quick questions
5. Use `/context` to check token usage

---

## Example Workflow

```
Iteration 1: Read task → Analyze codebase → Create initial implementation
Iteration 2: Run tests → Identify failures → Fix issues
Iteration 3: Handle edge cases → Add error handling
Iteration 4: Final tests pass → <promise>COMPLETE</promise>
```

---

## Philosophy

- **Iteration > Perfection**: Small improvements compound
- **Failures Are Data**: Learn from errors
- **Persistence Wins**: Keep iterating
- **Trust the Loop**: Let progress accumulate

---

## Commands Reference

```bash
# Check status
python ralph_mode.py status

# View prompt
python ralph_mode.py prompt

# View history
python ralph_mode.py history

# Increment iteration (done by loop)
python ralph_mode.py iterate

# Move to next task (batch mode)
python ralph_mode.py next-task

# Disable Ralph Mode
python ralph_mode.py disable
```

---

## Permissions

Ralph Mode uses Copilot CLI with:
- `--allow-all-tools`: Allow all tools
- `--allow-all-paths`: Allow access to all paths in workspace

For more restricted usage:
- `--allow-url <domain>`: Pre-approve specific domains
- `--allow-tool 'shell(git)'`: Allow specific shell commands
- `--deny-tool 'shell(rm)'`: Deny dangerous commands

### Tool Approval Syntax

```bash
# Allow specific shell command
--allow-tool 'shell(git)'

# Allow specific subcommand
--allow-tool 'shell(git push)'

# Allow file modifications
--allow-tool 'write'

# Allow MCP server tools
--allow-tool 'MCP_SERVER_NAME'
```

---

## Hooks

Custom hooks in `.github/hooks/` run at key points:

| Hook | When |
|------|------|
| `pre-iteration.sh` | Before each iteration |
| `post-iteration.sh` | After each iteration |
| `on-completion.sh` | When task completes |

Environment variables available:
- `RALPH_ITERATION` - Current iteration
- `RALPH_MAX_ITERATIONS` - Limit
- `RALPH_TASK_ID` - Task ID (batch mode)
- `RALPH_MODE` - "single" or "batch"

---

## MCP Server Integration

Ralph Mode supports MCP (Model Context Protocol) servers for extended functionality.

### Configuration Format

MCP servers are configured in `.ralph-mode-config/mcp-config.json`:

```json
{
  "mcpServers": {
    "server-name": {
      "type": "local|stdio|http|sse",
      "tools": ["tool1", "tool2"],
      "command": "npx",
      "args": ["@server/package"],
      "env": {
        "API_KEY": "COPILOT_MCP_API_KEY"
      }
    }
  }
}
```

### Key Fields

- **type**: `"local"`, `"stdio"`, `"http"`, or `"sse"`
- **tools**: Array of tools to enable (`["*"]` for all)
- **command/args**: For local servers
- **url/headers**: For remote servers
- **env**: Environment variables (prefix with `COPILOT_MCP_`)

### GitHub MCP Server (Default)

The GitHub MCP server provides read-only access to:
- Repository operations (`repos`)
- Issue management (`issues`)
- Pull requests (`pull_requests`)
- Code security (`code_security`)
- GitHub Actions (`actions`)

---

## Copilot Memory

Copilot Memory allows persistent understanding of your repository:
- Memories are stored automatically
- Reduces need to explain context repeatedly
- Future sessions become more productive

---

## Skills

Custom skills in `.github/skills/` enhance Copilot's abilities for specialized tasks.
Each skill is a folder containing a `SKILL.md` file with instructions.

### Available Skills

| Skill | Description |
|-------|-------------|
| `ralph-iteration` | Guides through completing a Ralph Mode iteration |
| `test-runner` | Standardized test execution across languages |
| `code-analysis` | Quick codebase analysis techniques |

### Creating Skills

Create a new directory under `.github/skills/` with a `SKILL.md` file:

```markdown
---
name: my-skill-name
description: What this skill does. When to use it.
---

# Skill Instructions

Your detailed instructions here...
```

Skills are automatically loaded by Copilot when relevant to the task.

---

## Special Hooks

Ralph Mode includes special hooks for session management:

### Stop Hook (`.github/hooks/stop.sh`)

Intercepts session exit attempts to continue the Ralph iteration loop. When the AI tries to exit:
- Checks if Ralph Mode is active
- Validates iteration limits
- Blocks exit and feeds back the same prompt for next iteration

### Session Start Hook (`.github/hooks/session-start.sh`)

Displays Ralph Mode status when a Copilot CLI session starts:
- Shows current iteration number
- Displays max iterations limit
- Shows completion promise
- Indicates current mode (single/batch)
