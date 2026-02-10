# 🔄 Copilot Ralph Mode

> Implementation of the Ralph Wiggum technique for iterative, self-referential AI development loops with GitHub Copilot CLI.

[![GitHub](https://img.shields.io/badge/GitHub-Copilot-blue)](https://github.com/features/copilot)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Cross-Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()
[![Copilot CLI](https://img.shields.io/badge/Copilot%20CLI-Compatible-brightgreen.svg)]()
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Sepehr%20Bayat-blue?logo=linkedin)](https://www.linkedin.com/in/sepehrbayat/)

**Author:** [Sepehr Bayat](https://www.linkedin.com/in/sepehrbayat/)

---

## 📑 Table of Contents

- [What is Ralph?](#-what-is-ralph)
- [How It Works](#-how-it-works)
- [Quick Start](#-quick-start)
- [Dev Container](#-dev-container)
- [Copilot CLI Integration](#-copilot-cli-integration)
- [Custom Agents](#-custom-agents)
- [Auto-Agents](#-auto-agents)
- [Skills](#-skills)
- [Hooks](#-hooks)
- [Security Considerations](#-security-considerations)
- [Network Resilience](#-network-resilience)
- [Usage Modes](#-usage-modes)
- [Commands Reference](#-commands-reference)
- [Best Practices](#-best-practices)
- [Field Notes (Real-World Trial)](#-field-notes-real-world-trial)
- [File Structure](#-file-structure)
- [MCP Server Integration](#-mcp-server-integration)
- [Cross-Platform Support](#-cross-platform-support)
- [Testing](#-testing)
- [Philosophy](#-philosophy)
- [Credits](#-credits)

---

## 🤔 What is Ralph?

Ralph is a development methodology based on continuous AI agent loops. As Geoffrey Huntley describes it: **"Ralph is a Bash loop"** - a simple `while true` that repeatedly feeds an AI agent a prompt, allowing it to iteratively improve its work until completion.

The technique is named after Ralph Wiggum from The Simpsons, embodying the philosophy of persistent iteration despite setbacks.

**This implementation is fully compatible with GitHub Copilot CLI**, supporting all its features including custom agents, plan mode, MCP servers, and context management.

---

## 🎯 How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    Ralph Loop                           │
│                                                         │
│   ┌──────────┐     ┌────────────┐     ┌──────────┐     │
│   │  Prompt  │────▶│  copilot   │────▶│   Work   │     │
│   │   File   │     │   -p ...   │     │  on Task │     │
│   └──────────┘     └────────────┘     └────┬─────┘     │
│        ▲                                    │          │
│        │           ┌──────────┐             │          │
│        └───────────│  Check   │◀────────────┘          │
│                    │ Complete │                         │
│                    └────┬─────┘                         │
│                         │                               │
│              ┌──────────┴──────────┐                   │
│              │                     │                    │
│              ▼                     ▼                    │
│        [Not Done]            [Done! ✅]                 │
│         Continue               Exit                     │
└─────────────────────────────────────────────────────────┘
```

The **Completion Promise** is how the AI signals it's done:

```
<promise>DONE</promise>
```

⚠️ **Rules for Completion:**
- Only output when task is GENUINELY complete
- The statement must be TRUE
- Never lie to exit the loop

---

## 🚀 Quick Start

### Prerequisites

```bash
# Install GitHub CLI
# macOS
brew install gh

# Linux
sudo apt install gh

# Windows
winget install GitHub.cli

# Install GitHub Copilot CLI
# Recommended:
#   npm install -g @github/copilot
# See: https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli

# Authenticate
gh auth login

# Verify Copilot CLI access
copilot --help

# ⚠️ If GITHUB_TOKEN is set, Copilot CLI may fail auth (401).
# Unset it for CLI usage:
#   unset GITHUB_TOKEN
```

### Installation

#### 🐳 Dev Container (Recommended)

The easiest way to get started is using VS Code Dev Containers. This ensures a consistent development environment across all platforms.

**Prerequisites:**
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [VS Code](https://code.visualstudio.com/) with [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

**Quick Start:**
1. Clone the repository
2. Open in VS Code
3. Click "Reopen in Container" when prompted (or run `Dev Containers: Reopen in Container` from command palette)
4. Wait for container to build (~2-3 minutes first time)
5. Done! All tools pre-installed.

```bash
git clone https://github.com/sepehrbayat/copilot-ralph-mode.git
code copilot-ralph-mode
# VS Code will prompt to reopen in container
```

**Dev Container Features:**
- ✅ Python 3.11 with all dependencies
- ✅ GitHub CLI pre-configured
- ✅ Zsh with helpful aliases (`ralph`, `test`, `lint`)
- ✅ VS Code extensions auto-installed
- ✅ Git configured with useful aliases
- ✅ Consistent environment on Windows, macOS, Linux

#### One-Line Install (Alternative)

**macOS/Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/sepehrbayat/copilot-ralph-mode/main/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/sepehrbayat/copilot-ralph-mode/main/install.ps1 | iex
```

**Windows (CMD):**
Download and run [install.cmd](install.cmd)

#### Manual Installation

```bash
# Clone the repository
git clone https://github.com/sepehrbayat/copilot-ralph-mode.git
cd copilot-ralph-mode

# Make scripts executable (Linux/macOS)
chmod +x ralph_mode.py ralph-loop.sh

# Install development dependencies (optional)
pip install -r requirements-dev.txt
```

#### Using pip

```bash
pip install copilot-ralph-mode
```

#### Using Make

```bash
git clone https://github.com/sepehrbayat/copilot-ralph-mode.git
cd copilot-ralph-mode
make install      # Install to ~/.local/bin
make dev-install  # Install with dev dependencies
```

### Your First Ralph Loop

```bash
# 1. Enable Ralph mode with a task
python3 ralph_mode.py enable "Create a Python calculator with unit tests" \
    --max-iterations 20 \
    --completion-promise "DONE"

# 2. Run the loop
./ralph-loop.sh run

# Or with a specific agent
./ralph-loop.sh run --agent ralph
```

That's it! Ralph will iterate until the task is complete.

---

## 🤖 Copilot CLI Integration

Ralph Mode is fully integrated with GitHub Copilot CLI features.

### Slash Commands

While running Ralph loops, you can use these Copilot CLI commands:

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
| `/delegate` | Hand off to Copilot coding agent |

### Plan Mode

Press `Shift+Tab` during an interactive session to enter plan mode - collaborate on implementation plans before writing code.

### File References

Use `@` to reference files in prompts:
```
Fix the bug in @src/auth/login.ts
Explain @config/ci/ci-required-checks.yml
```

### Delegating to Copilot Coding Agent

Hand off complex tasks to Copilot coding agent:
```
/delegate complete the API integration tests
& fix all failing edge cases
```

### Context Management

Copilot CLI automatically manages context. Commands for context control:

```bash
# View current token usage
/context

# Compress conversation history when context fills up
/compact

# View session statistics
/usage
```

### Resuming Sessions

```bash
# Resume the most recent session
copilot --continue

# Or cycle through previous sessions
copilot --resume
```

### Permissions

Ralph Mode uses these permission flags:

```bash
# Enable all permissions (for trusted environments)
./ralph-loop.sh run --allow-all

# Pre-approve specific URLs
./ralph-loop.sh run --allow-url github.com

# Restrict permissions
./ralph-loop.sh run --no-allow-tools --no-allow-paths
```

---

## 🧪 Field Notes (Real-World Trial)

Real‑world lessons learned from running Ralph on a public repository are captured here:

- [docs/LESSONS_LEARNED.md](docs/LESSONS_LEARNED.md)

Highlights include Copilot CLI install pitfalls, strict task scoping, and PR hygiene for upstream contributions.

---

## 🤖 Custom Agents

Ralph Mode includes custom agents optimized for different tasks.

### Available Agents

| Agent | Description | Use For |
|-------|-------------|---------|
| `ralph` | Main iteration agent | Ralph Mode loop work |
| `plan` | Planning agent | Creating implementation plans |
| `code-review` | Review agent | Reviewing changes |
| `task` | Task runner | Running tests and builds |
| `explore` | Exploration agent | Quick codebase questions |
| `agent-creator` | Meta-agent | Creating new specialized agents |

### Using Agents

```bash
# Use the ralph agent for iterations
./ralph-loop.sh run --agent ralph

# Use plan agent to create a plan first
copilot --agent=plan --prompt "Create a plan for implementing user authentication"

# Use task agent to run tests
copilot --agent=task --prompt "Run all tests and summarize results"
```

### Creating Custom Agents

Create agent profiles in `.github/agents/`:

```markdown
# my-agent.md

## Description
What this agent does.

## Prompts
Instructions for behavior.

## Tools
Which tools it can use.

## Behavior
How it should act.
```

---

## 🤖 Auto-Agents

Auto-Agents is a powerful feature that allows Ralph to **dynamically create specialized sub-agents** during task execution.

### Enabling Auto-Agents

```bash
python ralph_mode.py enable "Complex refactoring task" \
    --max-iterations 20 \
    --auto-agents \
    --completion-promise "DONE"
```

### How It Works

When `--auto-agents` is enabled:

1. **Agent Creator Available**: The `@agent-creator` meta-agent provides guidance
2. **Dynamic Creation**: Ralph can create new `.agent.md` files in `.github/agents/`
3. **Tracking**: Each created agent is tracked in `state.json` under `created_agents`
4. **Invocation**: Created agents can be invoked with `@agent-name <task>`

### Example Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  1. Ralph encounters complex testing subtask                │
│                                                             │
│  2. Creates .github/agents/test-specialist.agent.md         │
│     with specialized testing instructions                   │
│                                                             │
│  3. Invokes @test-specialist to handle testing workload     │
│                                                             │
│  4. Continues main task while sub-agent handles tests       │
└─────────────────────────────────────────────────────────────┘
```

### Agent File Format

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

### When to Create Sub-Agents

- Complex subtasks requiring focused context
- Repetitive operations benefiting from dedicated tooling
- Parallel workstreams needing isolation
- Code review, testing, or refactoring tasks

### Design Guidelines

- **Single Responsibility**: Each agent should do one thing well
- **Minimal Tools**: Only include tools the agent needs
- **Clear Instructions**: Be explicit about capabilities and limitations

---

## 📚 Skills

Skills are folders of instructions, scripts, and resources that enhance Copilot's abilities for specialized tasks. Skills follow the [Agent Skills](https://docs.github.com/en/copilot/customizing-copilot/extending-copilot/agent-skills) open standard.

### Available Skills

Located in `.github/skills/` (each skill in its own directory with `SKILL.md`):

| Skill | Description |
|-------|-------------|
| `ralph-iteration` | Guides through completing a Ralph Mode iteration |
| `test-runner` | Standardized test execution across languages |
| `code-analysis` | Quick codebase analysis techniques |

### Skill Structure

```
.github/skills/
├── ralph-iteration/
│   └── SKILL.md           # Required: skill instructions
├── test-runner/
│   └── SKILL.md
└── code-analysis/
    └── SKILL.md
```

### Creating Custom Skills

Create a new skill directory with a `SKILL.md` file:

```markdown
---
name: my-custom-skill
description: What this skill does. When Copilot should use it.
---

# My Custom Skill

Instructions for Copilot to follow...
```

### SKILL.md Requirements

- **name** (required): Lowercase, hyphens for spaces
- **description** (required): What it does and when to use it
- **license** (optional): License information

Skills can also include scripts, examples, or other resources in the same directory.

---

## 🪝 Hooks

Hooks allow you to execute custom shell commands at key points during Ralph Mode execution.

### Available Hooks

Located in `.github/hooks/`:

| Hook | When it Runs |
|------|--------------|
| `pre-iteration.sh` | Before each Copilot CLI iteration |
| `post-iteration.sh` | After each iteration completes |
| `pre-tool.sh` | Before Copilot executes a tool |
| `on-completion.sh` | When completion promise is detected |
| `on-network-wait.sh` | When network wait begins (for notifications) |

### Environment Variables

Hooks have access to these environment variables:

```bash
RALPH_ITERATION      # Current iteration number
RALPH_MAX_ITERATIONS # Maximum iterations allowed
RALPH_TASK_ID        # Current task ID (batch mode)
RALPH_MODE           # "single" or "batch"
RALPH_EXIT_CODE      # Exit code from Copilot CLI
RALPH_PROMISE        # Completion promise (on-completion only)
```

### Example: Auto-commit Progress

```bash
# .github/hooks/post-iteration.sh
#!/usr/bin/env bash
git add -A && git commit -m "Ralph iteration $RALPH_ITERATION" --no-verify 2>/dev/null || true
```

### Example: Security Scan

```bash
# .github/hooks/post-iteration.sh
#!/usr/bin/env bash
npm audit --audit-level=high 2>/dev/null || echo "Security issues found"
```

---

## 🔒 Security Considerations

### Trusted Directories

Copilot CLI asks to confirm trust for directories. Only launch Ralph Mode from directories you trust.

**Warning**: Do not launch from:
- Home directory
- Directories with untrusted executable files
- Directories with sensitive data you don't want modified

### Tool Approval

Ralph Mode runs with `--allow-all-tools --allow-all-paths` by default for automation. To restrict:

```bash
# Deny dangerous commands
./ralph-loop.sh run --deny-tool 'shell(rm)' --deny-tool 'shell(git push)'

# Allow only specific tools
./ralph-loop.sh run --no-allow-tools --allow-tool 'shell(git)' --allow-tool 'write'
```

### Tool Approval Syntax

| Syntax | Description |
|--------|-------------|
| `'shell(COMMAND)'` | Allow/deny specific shell command |
| `'shell(git push)'` | Allow/deny specific subcommand |
| `'shell'` | Allow/deny all shell commands |
| `'write'` | Allow/deny file modifications |
| `'MCP_SERVER(tool)'` | Allow/deny MCP server tool |

### Risk Mitigation

For maximum safety:
1. Use a virtual machine or container
2. Restrict network access
3. Review hooks before running
4. Use `--deny-tool` for dangerous commands

---

## 🌐 Network Resilience

Ralph Mode includes **professional-grade network resilience** to handle connection interruptions gracefully. When network connectivity is lost, Ralph will automatically:

1. **Detect** the disconnection
2. **Wait** with exponential backoff
3. **Resume** from the exact point where it stopped

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                  Network Resilience Flow                    │
│                                                             │
│   ┌────────────┐     ┌─────────────┐     ┌──────────────┐  │
│   │  Iteration │────▶│   Network   │────▶│   Success    │  │
│   │   Start    │     │   Check     │     │   Continue   │  │
│   └────────────┘     └──────┬──────┘     └──────────────┘  │
│                             │                               │
│                      [Connection Lost]                      │
│                             │                               │
│                             ▼                               │
│                    ┌─────────────┐                          │
│                    │    Save     │                          │
│                    │ Checkpoint  │                          │
│                    └──────┬──────┘                          │
│                           │                                 │
│                           ▼                                 │
│                    ┌─────────────┐                          │
│                    │    Wait     │◀─────┐                   │
│                    │  (backoff)  │      │                   │
│                    └──────┬──────┘      │                   │
│                           │             │                   │
│                    [Still Down?]────────┘                   │
│                           │                                 │
│                    [Restored!]                              │
│                           │                                 │
│                           ▼                                 │
│                    ┌─────────────┐                          │
│                    │   Resume    │                          │
│                    │ from Point  │                          │
│                    └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

### Exponential Backoff

Wait times increase progressively to avoid hammering the network:

| Attempt | Wait Time |
|---------|-----------|
| 1       | 5 seconds |
| 2       | 10 seconds |
| 3       | 20 seconds |
| 4       | 40 seconds |
| 5       | 80 seconds |
| 6+      | 300 seconds (max) |

### Checkpoint System

Ralph automatically saves checkpoints at key moments:

- `iteration_started` - Before each iteration begins
- `network_disconnected` - When network loss is detected
- `network_error` - When a network-related error occurs
- `network_restored` - When connection is restored
- `max_failures_reached` - When too many consecutive failures occur

### CLI Options

```bash
# Default: Network resilience ENABLED
./ralph-loop.sh run

# Disable network checking (for offline work)
./ralph-loop.sh run --no-network-check

# Customize retry timing
./ralph-loop.sh run --network-retry 10 --network-max 600

# Manual network check
./ralph-loop.sh check-network

# Resume from checkpoint
./ralph-loop.sh resume
```

### PowerShell (Windows)

```powershell
# Default: Network resilience ENABLED
.\ralph-mode.ps1 run

# Manual network check
.\ralph-mode.ps1 check-network

# Resume from checkpoint
.\ralph-mode.ps1 resume
```

### Network Hook

The `on-network-wait.sh` hook runs when network wait begins. Use it for notifications:

```bash
# .github/hooks/on-network-wait.sh
#!/usr/bin/env bash
echo "⚠️ Network lost at iteration $RALPH_ITERATION"

# Example: Send notification
# curl -X POST "https://ntfy.sh/my-topic" -d "Ralph waiting for network"
```

### Hosts Checked

By default, Ralph checks these hosts for connectivity:

1. `api.github.com` - GitHub API (primary for Copilot)
2. `github.com` - GitHub main
3. `1.1.1.1` - Cloudflare DNS (as fallback)

### Consecutive Failure Protection

If **3 consecutive iterations** fail (even with network available), Ralph will:

1. Stop the loop to prevent infinite failure loops
2. Save a checkpoint with `max_failures_reached` status
3. Allow you to resume after investigating

```bash
# After fixing the issue, resume
./ralph-loop.sh resume
```

---

## 💻 Usage Modes

Ralph supports three modes of operation:

### Mode 1: Single Task (Simple)

Best for straightforward, focused tasks:

```bash
# Enable with a single prompt
python3 ralph_mode.py enable "Fix all TypeScript errors in src/" \
    --max-iterations 20 \
    --completion-promise "DONE"

# Run the loop
./ralph-loop.sh run
```

### Mode 2: Batch Mode (Multiple Tasks in JSON)

Best for a series of related tasks defined in one file:

```bash
# Create tasks file
cat > my-tasks.json << 'EOF'
[
  {"id": "TASK-001", "title": "Setup project", "prompt": "Initialize npm project with TypeScript"},
  {"id": "TASK-002", "title": "Add tests", "prompt": "Add Jest tests for all functions"},
  {"id": "TASK-003", "title": "Add docs", "prompt": "Add JSDoc comments to all exports"}
]
EOF

# Initialize batch mode
python3 ralph_mode.py batch-init \
    --tasks-file my-tasks.json \
    --max-iterations 50 \
    --completion-promise "DONE"

# Run the loop (processes all tasks sequentially)
./ralph-loop.sh run
```

### Mode 3: Task Library with Groups (Recommended)

**The most precise and scalable approach.** Each task lives in its own `.md` file and groups are defined in `tasks/_groups/`.

```bash
# Create tasks directory
mkdir -p tasks tasks/_groups

# Let Copilot generate task files (see Best Practices section)
# Or create manually:
```

**Example task file (`tasks/HXA-001-flexbox-rtl.md`):**

```markdown
---
id: HXA-001
title: RTL Flexbox Conversion in Header
tags: [rtl, ui]
model: gpt-5.2-codex
max_iterations: 10
completion_promise: HXA_RTL_DONE
---

# RTL Flexbox Conversion in Header

## Objective
Convert flexbox classes to RTL-safe logical properties in `src/components/Header.tsx`.

## Scope
- ONLY modify: `src/components/Header.tsx`
- DO NOT read: Any other files
- DO NOT touch: `src/api/`, `src/utils/`, `node_modules/`

## Pre-work
1. Confirm `src/components/Header.tsx` exists and is writable
2. Identify all `flex-row`, `flex-row-reverse`, `ml-*`, `mr-*` in this file
3. Confirm no other files are required

## Changes Required
1. Replace `flex-row` with `flex-row` + `rtl:flex-row-reverse`
2. Replace `ml-*` with `ms-*`
3. Replace `mr-*` with `me-*`

## Acceptance Criteria
- [ ] Changes visible in `git diff`
- [ ] No `ml-*` or `mr-*` remain in the file
- [ ] If no changes needed, task FAILS

## Verification
```bash
grep -E "ml-|mr-" src/components/Header.tsx | wc -l
```

## Completion
When done, output: <promise>HXA_RTL_DONE</promise>
```

**Group configuration (`tasks/_groups/rtl.json`):**

```json
{
  "name": "RTL Support",
  "description": "Complete RTL implementation",
  "tasks": [
    "HXA-001-flexbox-rtl.md",
    "HXA-002-border-classes.md",
    "HXA-003-spacing-utilities.md"
  ],
  "max_iterations_per_task": 20
}
```

**Run the group:**

```bash
python3 ralph_mode.py run --group rtl
./ralph-loop.sh run
```

### Manual Iteration Mode

For debugging or step-by-step control:

```bash
# Enable Ralph mode
python3 ralph_mode.py enable "Build a REST API" --max-iterations 10

# Check status
python3 ralph_mode.py status

# Run ONE iteration at a time
./ralph-loop.sh single

# Review changes, then run another iteration
./ralph-loop.sh single

# Or start the continuous loop
./ralph-loop.sh run
```

---

## 🛠️ Commands Reference

### ralph_mode.py (State Management)

| Command | Description |
|---------|-------------|
| `enable "prompt"` | Enable Ralph mode with a task |
| `batch-init` | Initialize batch mode with multiple tasks |
| `disable` | Disable Ralph mode |
| `status` | Show current status |
| `prompt` | Show current prompt |
| `iterate` | Increment iteration counter |
| `next-task` | Move to next task in batch mode |
| `complete` | Check if output contains completion promise |
| `history` | Show iteration history |
| `help` | Show help |

### ralph-loop.sh (Loop Runner)

| Command | Description |
|---------|-------------|
| `run` | Start the continuous loop |
| `run --group <name>` | Run a specific task group |
| `run --agent <name>` | Run with a specific agent |
| `single` | Run single iteration |
| `resume` | Resume previous session (with checkpoint support) |
| `check-network` | Manual network connectivity test |
| `help` | Show help |

### Options

```bash
# ralph_mode.py options
--max-iterations <n>        # Max iterations (0 = unlimited)
--completion-promise <text> # Phrase that signals completion
--tasks-file <path>         # Path to tasks JSON file
--group <name>              # Task group to run
--auto-agents               # Enable dynamic sub-agent creation

# ralph-loop.sh options
--sleep <seconds>           # Sleep between iterations (default: 2)
--agent <name>              # Custom agent to use (ralph, plan, etc.)
--model <model>             # Model to use (e.g., gpt-5.2-codex)
--allow-all                 # Enable all permissions (--yolo mode)
--allow-url <domain>        # Pre-approve specific URL domain
--no-allow-tools            # Don't auto-allow all tools
--no-allow-paths            # Don't auto-allow all paths
--dry-run                   # Print commands without executing
--verbose                   # Verbose output

# Network resilience options
--no-network-check          # Disable network resilience
--network-retry <seconds>   # Initial retry wait (default: 5)
--network-max <seconds>     # Maximum retry wait (default: 300)
```

### Customizing Allowed Tools

By default, Ralph runs with `--allow-all-tools --allow-all-paths` for full automation. Customize permissions:

```bash
# Restrict to specific URLs only
./ralph-loop.sh run --allow-url github.com --allow-url api.github.com

# Disable auto-approval of tools
./ralph-loop.sh run --no-allow-tools

# Full unrestricted mode
./ralph-loop.sh run --allow-all
```

---

## 🏆 Best Practices

Follow these practices to maximize Ralph Mode's effectiveness.

> 📘 **See [docs/EXECUTION_GUIDE.md](docs/EXECUTION_GUIDE.md) for comprehensive documentation.**

### ⚠️ Preventing Read-Only Behavior

The most common issue is Ralph only reading/scanning files without making changes. **Prevent this by:**

1. **Specify exact files** - Max 1-2 files per task
2. **Add "DO NOT read"** - Prevents scanning the codebase
3. **Use imperative language** - "Add X" not "Ensure X exists"
4. **Require visible diff** - Task fails if no `git diff` output

#### ❌ Bad Task (causes read-only)
```markdown
Fix all RTL issues in the codebase.
```

#### ✅ Good Task (makes changes)
```markdown
## Scope
- ONLY modify: `src/components/Button.tsx`
- DO NOT read: Any other files

## Changes Required
1. Line 15: Change `ml-4` to `ms-4`
2. Line 23: Change `text-left` to `text-start`

## Acceptance Criteria
- git diff must show changes
- If no changes needed, task FAILS
```

### 1. Design Scoped Tasks

Each task should target **ONE file with specific changes**:

```markdown
---
id: TASK-001
title: Add RTL margin to Button
---

## Scope
- **ONLY modify:** `src/components/Button.tsx`
- **DO NOT read:** Any other files

## Changes Required
1. **Change margin** on line 15: `ml-4` → `ms-4`

## Acceptance Criteria
- [ ] Change visible in `git diff`
- [ ] If already changed, task FAILS
```

### 2. Always Review Before Execution

⚠️ **Read every generated task before running.** This ensures:
- Tasks align with your actual requirements
- No unintended changes will be made
- The scope boundaries are correct
- You understand what Ralph will do

### 3. Use Reasonable Iteration Counts

Set `--max-iterations` based on task complexity:
- Simple change: 5-10
- Medium task: 10-20
- Complex task: 20-50

```bash
python3 ralph_mode.py enable "Fix Button margin" \
    --max-iterations 10 \
    --completion-promise "DONE"
```

### 4. Always Run From Project Root

**Critical:** Execute Ralph from your project's root directory:

```bash
# ✅ Correct - run from project root
cd /path/to/your-project
./ralph-loop.sh run

# ❌ Wrong - running from a subdirectory
cd /path/to/your-project/src/components
./ralph-loop.sh run  # AI won't have access to full codebase!
```

When Ralph runs from root, it has visibility into ALL files and understands the full project structure.

### 5. Define Scope Boundaries in Every Task

Instruct the AI to build a dependency graph and respect boundaries:

```markdown
# Task: Implement User Authentication

## Pre-work Requirements
1. Map all files that will be affected
2. Identify dependencies between modules
3. List files that should NOT be modified
4. Create a change plan before editing

## Scope Boundaries
- ONLY modify files in: `src/auth/`, `src/api/auth.ts`
- DO NOT touch: `src/payments/`, `src/admin/`, `src/legacy/`
```

This prevents unintended side effects and keeps changes focused.

### 6. Use Custom Rules (.mdc files)

Create reusable rule files that Ralph should follow:

```markdown
# .ralph-rules/safety.mdc

## Rules for All Tasks
1. Never modify public API signatures without deprecation
2. All changes must be backwards compatible
3. Run existing tests before AND after changes
4. Never delete files without explicit instruction
5. Always add comments explaining complex logic
```

Reference rules in your tasks or tell Copilot:
> "Run Ralph Mode tasks following rules in .ralph-rules/safety.mdc"

### 7. Choose the Right Model

For complex, multi-file tasks, use more capable models:

```bash
./ralph-loop.sh run --model gpt-5.2-codex
```

More capable models:
- Better understand large codebases
- Make fewer errors requiring iterations
- Handle complex multi-step reasoning
- Produce higher quality code

### 8. Use Individual Task Files (Not JSON)

**For maximum precision, create a separate `.md` file for each task:**

| Approach | Pros | Cons |
|----------|------|------|
| Single JSON file | Quick setup | Less context per task |
| Individual `.md` files | Full context, clear scope, git-friendly | More files to manage |

Individual files are better because:
- Each task has complete context
- Easier to review and edit individually
- AI gets clearer, focused instructions
- Better version control (git diff per task)
- Can be generated by AI in VS Code Chat

### Summary Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. 💬 Use VS Code Chat to generate 20-50 detailed task files   │
│     "Create task files for implementing [feature] completely"   │
├─────────────────────────────────────────────────────────────────┤
│  2. 👀 Review ALL generated tasks - ensure scope is correct     │
├─────────────────────────────────────────────────────────────────┤
│  3. 📋 Create custom rules (.mdc) if needed for constraints     │
├─────────────────────────────────────────────────────────────────┤
│  4. 📁 cd to PROJECT ROOT (critical!)                           │
├─────────────────────────────────────────────────────────────────┤
│  5. 🚀 Initialize batch mode with high iteration limit          │
│     python3 ralph_mode.py batch-init --max-iterations 100       │
├─────────────────────────────────────────────────────────────────┤
│  6. ▶️  Execute the loop with a capable model                   │
│     ./ralph-loop.sh run --model gpt-5.2-codex                   │
├─────────────────────────────────────────────────────────────────┤
│  7. ☕ Let Ralph iterate until completion promise is detected   │
└─────────────────────────────────────────────────────────────────┘
```

### Anti-Patterns to Avoid

| ❌ Don't | ✅ Do Instead |
|----------|---------------|
| Write tasks manually | Let AI generate tasks, you review |
| Set `--max-iterations 5` | Use `--max-iterations 50-100` |
| Run from subdirectory | Always run from project root |
| Skip task review | Read every task before execution |
| Vague task descriptions | Include scope boundaries in each task |
| One giant task | Break into 20-50 focused tasks |
| Put all tasks in one JSON | Create individual `.md` files per task |
| Use basic models for complex work | Use capable models like gpt-5.2-codex |

---

## 📁 File Structure

When Ralph mode is active, it creates:

```
your-project/
├── .ralph-mode/              # Ralph state directory
│   ├── state.json            # Current state (iteration, limits, etc.)
│   ├── prompt.md             # The current task prompt
│   ├── INSTRUCTIONS.md       # Instructions for AI
│   ├── history.jsonl         # Log of all iterations
│   ├── output.txt            # Last Copilot CLI output
│   ├── summary.md            # Iteration summary report
│   ├── session.json          # Session info for resume
│   ├── checkpoint.json       # Network resilience checkpoint
│   └── tasks/                # Task files (batch mode)
│       ├── 01-HXA-001.md
│       └── 02-HXA-002.md
│
├── .ralph-mode-config/       # Ralph configuration (optional)
│   ├── config.json           # Default settings
│   └── mcp-config.json       # MCP server configuration
│
├── .github/                  # GitHub/Copilot integration
│   ├── copilot-instructions.md  # Repository-wide instructions
│   ├── agents/               # Custom agent profiles
│   │   ├── ralph.md
│   │   ├── plan.md
│   │   ├── code-review.md
│   │   ├── task.md
│   │   ├── explore.md
│   │   └── agent-creator.agent.md
│   ├── hooks/                # Lifecycle hooks
│   │   ├── pre-iteration.sh
│   │   ├── post-iteration.sh
│   │   ├── pre-tool.sh
│   │   ├── on-completion.sh
│   │   ├── on-network-wait.sh
│   │   ├── stop.sh           # Loop continuation hook (blocks exit)
│   │   └── session-start.sh  # Session start status display
│   ├── instructions/         # Path-specific instructions
│   │   ├── ralph-mode-python.instructions.md
│   │   ├── shell-scripts.instructions.md
│   │   ├── task-files.instructions.md
│   │   └── tests.instructions.md
│   └── skills/               # Agent skills (each in own folder)
│       ├── ralph-iteration/
│       │   └── SKILL.md
│       ├── test-runner/
│       │   └── SKILL.md
│       └── code-analysis/
│           └── SKILL.md
│
├── tasks/                    # Your task definitions (recommended)
│   ├── HXA-001-feature.md
│   ├── HXA-002-tests.md
│   └── _groups/
│       ├── backend.json
│       └── frontend.json
│
├── tests/                    # Test files
│   ├── test_ralph_mode.py
│   ├── test_network_integration.ps1
│   ├── test_network_resilience.ps1
│   ├── test_network_resilience.sh
│   └── demo_network_resilience.ps1
│
└── .ralph-rules/             # Custom rules (optional)
    ├── safety.mdc
    └── coding-standards.mdc
```

---

## 🔗 MCP Server Integration

Ralph Mode supports [MCP (Model Context Protocol)](https://docs.github.com/en/copilot/customizing-copilot/extending-copilot/extending-copilot-coding-agent-with-mcp) servers for extended functionality.

### Configuration

MCP servers are configured using JSON format with the `mcpServers` object:

**Project config**: `.ralph-mode-config/mcp-config.json`

### JSON Configuration Format

```json
{
  "mcpServers": {
    "server-name": {
      "type": "local|stdio|http|sse",
      "tools": ["tool1", "tool2"],
      ...
    }
  }
}
```

### Required Keys

| Key | Type | Description |
|-----|------|-------------|
| `tools` | string[] | Tools to enable (`["*"]` for all) |
| `type` | string | `"local"`, `"stdio"`, `"http"`, or `"sse"` |

### Local MCP Server Keys

| Key | Type | Description |
|-----|------|-------------|
| `command` | string | Command to start the server |
| `args` | string[] | Arguments for the command |
| `env` | object | Environment variables (use `COPILOT_MCP_` prefix) |

### Remote MCP Server Keys

| Key | Type | Description |
|-----|------|-------------|
| `url` | string | Server URL |
| `headers` | object | Request headers |

### Example: GitHub MCP Server (Default)

```json
{
  "mcpServers": {
    "github-mcp-server": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/readonly",
      "tools": ["*"],
      "headers": {
        "X-MCP-Toolsets": "repos,issues,users,pull_requests,code_security,actions"
      }
    }
  }
}
```

### Example: Local MCP Server (Sentry)

```json
{
  "mcpServers": {
    "sentry": {
      "type": "local",
      "command": "npx",
      "args": ["@sentry/mcp-server@latest", "--host=$SENTRY_HOST"],
      "tools": ["get_issue_details", "get_issue_summary"],
      "env": {
        "SENTRY_HOST": "COPILOT_MCP_SENTRY_HOST",
        "SENTRY_ACCESS_TOKEN": "COPILOT_MCP_SENTRY_ACCESS_TOKEN"
      }
    }
  }
}
```

### Example: Remote MCP Server (Cloudflare)

```json
{
  "mcpServers": {
    "cloudflare": {
      "type": "sse",
      "url": "https://docs.mcp.cloudflare.com/sse",
      "tools": ["*"]
    }
  }
}
```

### Environment Variables

For MCP servers requiring secrets:
- Prefix all environment variables with `COPILOT_MCP_`
- Reference in config: `"API_KEY": "COPILOT_MCP_API_KEY"`
- Or use `$COPILOT_MCP_API_KEY` in string values

### Available Toolsets (GitHub MCP)

| Toolset | Description |
|---------|-------------|
| `repos` | Repository operations |
| `issues` | Issue management |
| `users` | User information |
| `pull_requests` | PR operations |
| `code_security` | Security scanning |
| `secret_protection` | Secret scanning |
| `actions` | GitHub Actions |
| `web_search` | Web search |

---

## � Dev Container

**Recommended for all developers** - eliminates "works on my machine" issues.

### Why Dev Container?

| Problem | Solution |
|---------|----------|
| Different Python versions | Container uses Python 3.11 |
| Missing dependencies | All packages pre-installed |
| Path issues (Windows vs Unix) | Consistent Linux paths |
| Shell script compatibility | Bash/Zsh always available |
| IDE configuration | VS Code extensions auto-install |

### Container Structure

```
.devcontainer/
├── devcontainer.json    # VS Code Dev Container config
├── Dockerfile           # Container image definition
├── docker-compose.yml   # Services and volumes
├── post-create.sh       # One-time setup script
└── post-start.sh        # Runs on every start
```

### Pre-installed Tools

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11 | Core runtime |
| Git | Latest | Version control |
| GitHub CLI | Latest | `gh` commands |
| pytest | 7.0+ | Testing |
| black | 23.0+ | Code formatting |
| flake8 | 6.0+ | Linting |
| mypy | 1.0+ | Type checking |
| Zsh + Oh My Zsh | Latest | Better shell |

### Quick Commands (in container)

```bash
# Ralph Mode
ralph-quick 'Build a REST API'  # Enable and show status
ralph-loop                       # Start the loop
ralph-status                     # Check status

# Testing
test                            # Run all tests
test-fast                       # Quick test (stop on first fail)
test-cov                        # With coverage

# Code Quality
lint                            # Check all
format                          # Auto-fix formatting
typecheck                       # MyPy type checking

# Git
gs                              # git status
gc                              # git commit
gp                              # git push
```

### Rebuilding Container

```bash
# From VS Code Command Palette:
Dev Containers: Rebuild Container

# Or from terminal:
docker compose -f .devcontainer/docker-compose.yml build --no-cache
```

---

## 📦 Cross-Platform Support

| Platform | State Management | Loop Runner |
|----------|-----------------|-------------|
| **Dev Container** ⭐ | `ralph` | `ralph-loop` |
| **Linux/macOS** | `python3 ralph_mode.py` | `./ralph-loop.sh` |
| **Windows (WSL)** | `python3 ralph_mode.py` | `./ralph-loop.sh` |
| **Windows (PowerShell)** | `python ralph_mode.py` | `./ralph-mode.ps1` or WSL |
| **Windows (CMD)** | `python ralph_mode.py` | `ralph-mode.cmd` or WSL |

### Requirements

**Using Dev Container (Recommended):**
- Docker Desktop
- VS Code with Dev Containers extension

**Manual Installation:**
- Python 3.7+
- GitHub CLI (`gh`) with Copilot access
- Bash shell (for loop runner) or PowerShell on Windows
- `jq` for JSON parsing (optional but recommended)

---

## 🧪 Testing

### Quick Test Commands

```bash
# Using Make (recommended)
make test           # Run all tests
make test-cov       # Run with coverage report
make lint           # Run code quality checks

# Using pytest directly
pytest tests/ -v                    # All tests
pytest tests/test_ralph_mode.py -v  # Core tests
pytest tests/test_advanced.py -v    # Advanced/edge case tests
pytest tests/test_cross_platform.py -v  # Cross-platform tests

# Using Python
python -m pytest tests/ -v --timeout=30
```

### Test Suites

| Suite | Tests | Description |
|-------|-------|-------------|
| `test_ralph_mode.py` | 38 | Core functionality |
| `test_advanced.py` | 78 | Edge cases, property-based (hypothesis) |
| `test_cross_platform.py` | 38 | Windows/macOS/Linux compatibility |
| **Total** | **154** | Full test coverage |

### CI/CD

GitHub Actions runs tests on every push:
- **Platforms:** Ubuntu, macOS, Windows
- **Python versions:** 3.9, 3.10, 3.11, 3.12
- **Matrix:** 12 combinations

[![Tests](https://github.com/sepehrbayat/copilot-ralph-mode/actions/workflows/test.yml/badge.svg)](https://github.com/sepehrbayat/copilot-ralph-mode/actions/workflows/test.yml)

### Code Quality

```bash
make lint    # flake8 + black check + isort check + mypy
make format  # Auto-format with black + isort
```

---

## 🤔 Philosophy

- **Iteration > Perfection**: Don't aim for perfect on first try
- **Failures Are Data**: Use errors to improve
- **Persistence Wins**: Keep trying until success
- **Trust the Loop**: Let the AI learn from its mistakes
- **Review > Write**: Let AI generate, you review and approve

---

## 🔄 Example Session

```bash
$ python3 ralph_mode.py enable "Create a Python calculator with tests" \
    --max-iterations 15 --completion-promise "DONE"

╔════════════════════════════════════════════════════════════╗
║                    🔄 RALPH MODE ENABLED                    ║
╚════════════════════════════════════════════════════════════╝

Iteration:          1
Max Iterations:     15
Completion Promise: DONE

📝 Task:
Create a Python calculator with tests

✅ Ralph mode is now active!

$ ./ralph-loop.sh run

╔══════════════════════════════════════════════════════════╗
║              🔄 RALPH LOOP STARTING                      ║
╚══════════════════════════════════════════════════════════╝

Press Ctrl+C to stop the loop

╔══════════════════════════════════════════════════════════╗
║          🔄 Ralph Iteration 1                            ║
╚══════════════════════════════════════════════════════════╝

🌐 Checking network connectivity...
✅ Network is available

🤖 Running copilot...
[AI creates calculator.py]

╔══════════════════════════════════════════════════════════╗
║          🔄 Ralph Iteration 2                            ║
╚══════════════════════════════════════════════════════════╝

🌐 Checking network connectivity...
✅ Network is available

🤖 Running copilot...
[AI creates test_calculator.py]
[AI runs tests - they pass]

<promise>DONE</promise>

═══════════════════════════════════════════════════════════
✅ COMPLETION PROMISE DETECTED!
═══════════════════════════════════════════════════════════

🏁 Ralph loop finished after 2 iterations
```

### Example: Network Resilience in Action

```bash
╔══════════════════════════════════════════════════════════╗
║          🔄 Ralph Iteration 5                            ║
╚══════════════════════════════════════════════════════════╝

🌐 Checking network connectivity...

═══════════════════════════════════════════════════════════════
🔌 Network connection lost - waiting for reconnection...
═══════════════════════════════════════════════════════════════

[2026-02-02 15:31:49] Attempt 1: Waiting 5s for network... (total: 0s)
[2026-02-02 15:31:54] Attempt 2: Waiting 10s for network... (total: 5s)
[2026-02-02 15:32:04] Attempt 3: Waiting 20s for network... (total: 15s)

[2026-02-02 15:32:24] ✅ Network connection restored after 35s!

🤖 Running copilot... (resuming)
[AI continues work from where it stopped]
```

---

## 🔗 Credits

- Original technique: [ghuntley.com/ralph](https://ghuntley.com/ralph/)
- Inspiration: Geoffrey Huntley's Ralph Wiggum approach
- GitHub Copilot: [github.com/features/copilot](https://github.com/features/copilot)
- GitHub Copilot CLI: [docs.github.com/copilot-cli](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli)

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.
