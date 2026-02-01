# 🔄 Copilot Ralph Mode

> Implementation of the Ralph Wiggum technique for iterative, self-referential AI development loops with GitHub Copilot CLI.

[![GitHub](https://img.shields.io/badge/GitHub-Copilot-blue)](https://github.com/features/copilot)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
[![Cross-Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

**Author:** Sepehr Bayat

---

## 🤔 What is Ralph?

Ralph is a development methodology based on continuous AI agent loops. As Geoffrey Huntley describes it: **"Ralph is a Bash loop"** - a simple `while true` that repeatedly feeds an AI agent a prompt, allowing it to iteratively improve its work until completion.

The technique is named after Ralph Wiggum from The Simpsons, embodying the philosophy of persistent iteration despite setbacks.

---

## 🎯 How It Works

```
┌─────────────────────────────────────────────────────────┐
│                  Ralph Loop                              │
│                                                          │
│   ┌──────────┐     ┌────────────┐     ┌──────────┐     │
│   │  Prompt  │────▶│ gh copilot │────▶│   Work   │     │
│   │   File   │     │   -p ...   │     │  on Task │     │
│   └──────────┘     └────────────┘     └────┬─────┘     │
│        ▲                                    │           │
│        │           ┌──────────┐             │           │
│        └───────────│  Check   │◀────────────┘           │
│                    │ Complete │                          │
│                    └────┬─────┘                          │
│                         │                                │
│              ┌──────────┴──────────┐                    │
│              │                     │                     │
│              ▼                     ▼                     │
│        [Not Done]            [Done! ✅]                  │
│         Continue               Exit                      │
└─────────────────────────────────────────────────────────┘
```

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

# The gh-copilot extension is built into newer gh versions
# Test it:
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

---

## 💻 Usage with gh copilot CLI

### Method 1: Automated Loop (Recommended)

```bash
# 1. Enable Ralph mode
python3 ralph_mode.py enable "Fix all TypeScript errors in src/" \
    --max-iterations 20 \
    --completion-promise "DONE"

# 2. Run the loop
./ralph-loop.sh run
```

The loop will:
- Call `gh copilot` with your task
- Let it make changes using shell tools
- Check for completion promise in output
- Iterate until done or max iterations reached

### Method 2: Manual Iterations

```bash
# 1. Enable Ralph mode
python3 ralph_mode.py enable "Build a REST API" --max-iterations 10

# 2. Check status
python3 ralph_mode.py status

# 3. Run single iteration
./ralph-loop.sh single

# 4. Repeat step 3 as needed, or run the loop
./ralph-loop.sh run
```

### Batch Mode (Multiple Tasks)

```bash
# 1. Create tasks file
cat > my-tasks.json << 'EOF'
[
  {"id": "TASK-001", "title": "Setup project", "prompt": "Initialize npm project with TypeScript"},
  {"id": "TASK-002", "title": "Add tests", "prompt": "Add Jest tests for all functions"},
  {"id": "TASK-003", "title": "Add docs", "prompt": "Add JSDoc comments to all exports"}
]
EOF

# 2. Initialize batch mode
python3 ralph_mode.py batch-init \
    --tasks-file my-tasks.json \
    --max-iterations 10 \
    --completion-promise "DONE"

# 3. Run the loop (will process all tasks)
./ralph-loop.sh run
```

---

## 🛠️ Commands

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
| `single` | Run single iteration |
| `help` | Show help |

### Options

```bash
# ralph_mode.py options
--max-iterations <n>        # Max iterations (0 = unlimited)
--completion-promise <text> # Phrase that signals completion

# ralph-loop.sh options
--sleep <seconds>           # Sleep between iterations (default: 2)
--allow-tools <tools>       # Tools to allow gh copilot to use
--dry-run                   # Print commands without executing
--verbose                   # Verbose output
```

---

## 🔧 Customizing Allowed Tools

By default, Ralph allows these shell tools:

```bash
shell(git,npm,node,python3,cat,ls,grep,find,mkdir,cp,mv,rm,touch,echo,head,tail,wc)
```

Customize with:

```bash
./ralph-loop.sh run --allow-tools "shell(git,npm,docker)"
```

---

## 📁 File Structure

When Ralph mode is active, it creates:

```
.ralph-mode/
├── state.json       # Current state (iteration, limits, etc.)
├── prompt.md        # The task prompt
├── INSTRUCTIONS.md  # Instructions for AI
├── history.jsonl    # Log of all iterations
├── output.txt       # Last gh copilot output
└── tasks/           # Individual task files (batch mode)
    ├── 01-task-001.md
    └── 02-task-002.md
```

---

## ✅ Completion Promise

The completion promise is how the AI signals it's done:

```bash
python3 ralph_mode.py enable "Fix tests" --completion-promise "ALL TESTS PASS"
```

When the task is complete, the AI outputs:

```
<promise>ALL TESTS PASS</promise>
```

⚠️ **Rules:**
- Only output when GENUINELY complete
- Don't lie to exit the loop
- The statement must be TRUE

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

🔄 Ralph iteration: 2

╔══════════════════════════════════════════════════════════╗
║          🔄 Ralph Iteration 2                            ║
╚══════════════════════════════════════════════════════════╝

🤖 Running gh copilot...
[AI creates tests]
[AI runs tests - they pass]

<promise>DONE</promise>

═══════════════════════════════════════════════════════════
✅ COMPLETION PROMISE DETECTED!
═══════════════════════════════════════════════════════════

🏁 Ralph loop finished
```

---

## 📦 Cross-Platform Support

| Platform | State Management | Loop Runner |
|----------|-----------------|-------------|
| **Linux/macOS** | `python3 ralph_mode.py` | `./ralph-loop.sh` |
| **Windows (WSL)** | `python3 ralph_mode.py` | `./ralph-loop.sh` |
| **Windows (PowerShell)** | `python ralph_mode.py` | Use WSL or Git Bash |

### Requirements

- Python 3.7+
- GitHub CLI (`gh`) with Copilot access
- Bash shell (for loop runner)
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

---

## 🔗 Credits

- Original technique: [ghuntley.com/ralph](https://ghuntley.com/ralph/)
- Inspiration: Geoffrey Huntley's Ralph Wiggum approach
- GitHub Copilot: [github.com/features/copilot](https://github.com/features/copilot)

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.
