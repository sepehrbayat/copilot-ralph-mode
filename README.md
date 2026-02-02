# 🔄 Copilot Ralph Mode

> Implementation of the Ralph Wiggum technique for iterative, self-referential AI development loops with GitHub Copilot CLI.

[![GitHub](https://img.shields.io/badge/GitHub-Copilot-blue)](https://github.com/features/copilot)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
[![Cross-Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Sepehr%20Bayat-blue?logo=linkedin)](https://www.linkedin.com/in/sepehrbayat/)

**Author:** [Sepehr Bayat](https://www.linkedin.com/in/sepehrbayat/)

---

## 📑 Table of Contents

- [What is Ralph?](#-what-is-ralph)
- [How It Works](#-how-it-works)
- [Quick Start](#-quick-start)
- [Usage Modes](#-usage-modes)
- [Commands Reference](#-commands-reference)
- [Best Practices](#-best-practices)
- [File Structure](#-file-structure)
- [Cross-Platform Support](#-cross-platform-support)
- [Testing](#-testing)
- [Philosophy](#-philosophy)
- [Credits](#-credits)

---

## 🤔 What is Ralph?

Ralph is a development methodology based on continuous AI agent loops. As Geoffrey Huntley describes it: **"Ralph is a Bash loop"** - a simple `while true` that repeatedly feeds an AI agent a prompt, allowing it to iteratively improve its work until completion.

The technique is named after Ralph Wiggum from The Simpsons, embodying the philosophy of persistent iteration despite setbacks.

---

## 🎯 How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    Ralph Loop                           │
│                                                         │
│   ┌──────────┐     ┌────────────┐     ┌──────────┐     │
│   │  Prompt  │────▶│ gh copilot │────▶│   Work   │     │
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

# Authenticate
gh auth login

# Verify Copilot access
gh copilot --help
```

### Installation

```bash
# Clone the repository
git clone https://github.com/sepehrbayat/copilot-ralph-mode.git
cd copilot-ralph-mode

# Make scripts executable (Linux/macOS)
chmod +x ralph_mode.py ralph-loop.sh
```

### Your First Ralph Loop

```bash
# 1. Enable Ralph mode with a task
python3 ralph_mode.py enable "Create a Python calculator with unit tests" \
    --max-iterations 20 \
    --completion-promise "DONE"

# 2. Run the loop
./ralph-loop.sh run
```

That's it! Ralph will iterate until the task is complete.

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

### Mode 3: Individual Task Files with Groups (Recommended)

**The most precise and scalable approach.** Each task lives in its own `.md` file:

```bash
# Create tasks directory
mkdir -p tasks tasks/_groups

# Let Copilot generate task files (see Best Practices section)
# Or create manually:
```

**Example task file (`tasks/HXA-001-flexbox-rtl.md`):**

```markdown
# HXA-001: RTL Flexbox Conversion

## Objective
Convert all flexbox classes to use logical properties for RTL support.

## Scope
- ONLY modify: `src/components/**/*.tsx`
- DO NOT touch: `src/api/`, `src/utils/`, `node_modules/`

## Pre-work
1. List all files using `flex-row`, `flex-row-reverse`
2. Create dependency graph of affected components
3. Identify parent-child relationships

## Changes Required
- Replace `flex-row` with `flex-row` + `rtl:flex-row-reverse`
- Replace `ml-*` with `ms-*` (margin-start)
- Replace `mr-*` with `me-*` (margin-end)

## Acceptance Criteria
- [ ] All flexbox layouts work correctly in RTL mode
- [ ] No visual regression in LTR mode
- [ ] Tests pass

## Completion
When done, output: <promise>DONE</promise>
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
python3 ralph_mode.py batch-init \
    --tasks-dir tasks/ \
    --group rtl \
    --max-iterations 100 \
    --completion-promise "DONE"

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
| `single` | Run single iteration |
| `help` | Show help |

### Options

```bash
# ralph_mode.py options
--max-iterations <n>        # Max iterations (0 = unlimited)
--completion-promise <text> # Phrase that signals completion
--tasks-file <path>         # Path to tasks JSON file
--tasks-dir <path>          # Path to tasks directory
--group <name>              # Task group to run

# ralph-loop.sh options
--sleep <seconds>           # Sleep between iterations (default: 2)
--allow-tools <tools>       # Tools to allow gh copilot to use
--model <model>             # Model to use (e.g., gpt-5.2-codex)
--dry-run                   # Print commands without executing
--verbose                   # Verbose output
```

### Customizing Allowed Tools

By default, Ralph allows these shell tools:

```bash
shell(git,npm,node,python3,cat,ls,grep,find,mkdir,cp,mv,rm,touch,echo,head,tail,wc)
```

Customize with:

```bash
./ralph-loop.sh run --allow-tools "shell(git,npm,docker)"
```

---

## 🏆 Best Practices

Follow these practices to maximize Ralph Mode's effectiveness:

### 1. Let AI Generate Your Tasks

Instead of manually writing task files, use VS Code's Copilot Chat:

```
Prompt Example:
"Create 30 individual task files for Ralph Mode in the tasks/ folder.
Each file should be named like: HXA-001-description.md
The task is to implement complete two-factor authentication.
Include detailed instructions, scope boundaries, and acceptance criteria in each file.
Also create group files in tasks/_groups/ to organize them by: backend, frontend, tests."
```

Copilot will generate structured task files like:

```
tasks/
├── HXA-001-setup-2fa-database.md
├── HXA-002-totp-generation.md
├── HXA-003-qr-code-component.md
├── HXA-004-verification-api.md
├── HXA-005-backup-codes.md
├── ...
├── HXA-030-e2e-tests.md
└── _groups/
    ├── backend.json
    ├── frontend.json
    └── tests.json
```

**Why this works:** You spend time *reviewing* tasks rather than *writing* them. The AI understands task decomposition and creates comprehensive coverage.

### 2. Always Review Before Execution

⚠️ **Read every generated task before running.** This ensures:
- Tasks align with your actual requirements
- No unintended changes will be made
- The scope boundaries are correct
- You understand what Ralph will do

### 3. Use High Iteration Counts

Set `--max-iterations` high (50-100) so the loop doesn't terminate prematurely:

```bash
python3 ralph_mode.py batch-init \
    --tasks-dir tasks/ \
    --group backend \
    --max-iterations 100 \
    --completion-promise "DONE"
```

**Why:** Complex tasks may need many iterations to:
- Gather context about the codebase
- Fix errors and edge cases
- Refine the solution
- Run and fix tests

Low limits cause incomplete work.

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
│   ├── output.txt            # Last gh copilot output
│   └── tasks/                # Task files (batch mode)
│       ├── 01-HXA-001.md
│       └── 02-HXA-002.md
│
├── tasks/                    # Your task definitions (recommended)
│   ├── HXA-001-feature.md
│   ├── HXA-002-tests.md
│   └── _groups/
│       ├── backend.json
│       └── frontend.json
│
└── .ralph-rules/             # Custom rules (optional)
    ├── safety.mdc
    └── coding-standards.mdc
```

---

## 📦 Cross-Platform Support

| Platform | State Management | Loop Runner |
|----------|-----------------|-------------|
| **Linux/macOS** | `python3 ralph_mode.py` | `./ralph-loop.sh` |
| **Windows (WSL)** | `python3 ralph_mode.py` | `./ralph-loop.sh` |
| **Windows (PowerShell)** | `python ralph_mode.py` | `./ralph-mode.ps1` or WSL |
| **Windows (CMD)** | `python ralph_mode.py` | `ralph-mode.cmd` or WSL |

### Requirements

- Python 3.7+
- GitHub CLI (`gh`) with Copilot access
- Bash shell (for loop runner) or PowerShell on Windows
- `jq` for JSON parsing (optional but recommended)

---

## 🧪 Testing

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run specific test
python3 -m pytest tests/test_ralph_mode.py -v
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

🤖 Running gh copilot...
[AI creates calculator.py]

╔══════════════════════════════════════════════════════════╗
║          🔄 Ralph Iteration 2                            ║
╚══════════════════════════════════════════════════════════╝

🤖 Running gh copilot...
[AI creates test_calculator.py]
[AI runs tests - they pass]

<promise>DONE</promise>

═══════════════════════════════════════════════════════════
✅ COMPLETION PROMISE DETECTED!
═══════════════════════════════════════════════════════════

🏁 Ralph loop finished after 2 iterations
```

---

## 🔗 Credits

- Original technique: [ghuntley.com/ralph](https://ghuntley.com/ralph/)
- Inspiration: Geoffrey Huntley's Ralph Wiggum approach
- GitHub Copilot: [github.com/features/copilot](https://github.com/features/copilot)

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.
