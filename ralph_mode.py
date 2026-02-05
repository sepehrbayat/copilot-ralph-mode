#!/usr/bin/env python3
"""
Copilot Ralph Mode - Cross-platform implementation
Implementation of the Ralph Wiggum technique for GitHub Copilot

Usage:
    ralph-mode enable "Your task" --max-iterations 20 --completion-promise "DONE"
    ralph-mode batch-init --tasks-file tasks.json --max-iterations 20 --completion-promise "DONE"
    ralph-mode disable
    ralph-mode status
    ralph-mode iterate
    ralph-mode next-task
    ralph-mode prompt
    ralph-mode help
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

VERSION = "1.1.0"

# Default model configuration
DEFAULT_MODEL = "gpt-5.2-codex"
FALLBACK_MODEL = "auto"
AVAILABLE_MODELS = [
    "auto",
    "claude-sonnet-4.5",
    "claude-haiku-4.5",
    "claude-opus-4.5",
    "claude-sonnet-4",
    "gemini-3-pro-preview",
    "gpt-5.2-codex",
    "gpt-5.2",
    "gpt-5.1-codex-max",
    "gpt-5.1-codex",
    "gpt-5.1",
    "gpt-5",
    "gpt-5.1-codex-mini",
    "gpt-5-mini",
    "gpt-4.1",
]

REQUIRED_TASK_SECTIONS = [
    "## Objective",
    "## Scope",
    "## Pre-work",
    "## Changes Required",
    "## Acceptance Criteria",
    "## Verification",
    "## Completion",
]

REQUIRED_SCOPE_MARKERS = [
    "ONLY modify",
    "DO NOT read",
    "DO NOT touch",
]

STRICT_TASKS = os.environ.get("RALPH_STRICT_TASKS") == "1"
STRICT_ROOT = os.environ.get("RALPH_STRICT_ROOT") == "1"


# ANSI Colors (disabled on Windows without colorama)
class Colors:
    """ANSI color codes for terminal output."""

    def __init__(self):
        self.enabled = self._check_color_support()

    def _check_color_support(self) -> bool:
        """Check if terminal supports colors."""
        if os.name == "nt":  # Windows
            try:
                import colorama

                colorama.init()
                return True
            except ImportError:
                return os.environ.get("TERM") is not None
        return sys.stdout.isatty()

    @property
    def RED(self) -> str:
        return "\033[0;31m" if self.enabled else ""

    @property
    def GREEN(self) -> str:
        return "\033[0;32m" if self.enabled else ""

    @property
    def YELLOW(self) -> str:
        return "\033[1;33m" if self.enabled else ""

    @property
    def BLUE(self) -> str:
        return "\033[0;34m" if self.enabled else ""

    @property
    def CYAN(self) -> str:
        return "\033[0;36m" if self.enabled else ""

    @property
    def NC(self) -> str:
        return "\033[0m" if self.enabled else ""


colors = Colors()


class TaskLibrary:
    """Task library manager for loading tasks from files."""

    TASKS_DIR = "tasks"
    GROUPS_DIR = "_groups"

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize task library."""
        self.base_path = Path(base_path) if base_path else Path(__file__).parent
        self.tasks_dir = self.base_path / self.TASKS_DIR
        self.groups_dir = self.tasks_dir / self.GROUPS_DIR

    def parse_task_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse a task markdown file with YAML frontmatter."""
        content = file_path.read_text(encoding="utf-8")

        # Parse YAML frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    # Simple YAML parsing without external deps
                    frontmatter = {}
                    for line in parts[1].strip().split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            key = key.strip()
                            value = value.strip()
                            # Handle arrays
                            if value.startswith("[") and value.endswith("]"):
                                value = [v.strip().strip("\"'") for v in value[1:-1].split(",")]
                            # Handle numbers
                            elif value.isdigit():
                                value = int(value)
                            frontmatter[key] = value

                    return {**frontmatter, "prompt": parts[2].strip(), "file": str(file_path)}
                except Exception:
                    pass

        # Fallback: use filename as ID
        return {
            "id": file_path.stem.upper(),
            "title": file_path.stem.replace("-", " ").title(),
            "prompt": content,
            "file": str(file_path),
        }

    def list_tasks(self) -> list:
        """List all available tasks."""
        tasks = []
        if not self.tasks_dir.exists():
            return tasks

        for file_path in sorted(self.tasks_dir.glob("*.md")):
            if file_path.name.startswith("_") or file_path.name == "README.md":
                continue
            try:
                task = self.parse_task_file(file_path)
                tasks.append(task)
            except Exception:
                pass

        return tasks

    def list_groups(self) -> list:
        """List all task groups."""
        groups = []
        if not self.groups_dir.exists():
            return groups

        for file_path in sorted(self.groups_dir.glob("*.json")):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                data["file"] = str(file_path)
                groups.append(data)
            except Exception:
                pass

        return groups

    def get_task(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID, filename, or partial match."""
        identifier_lower = identifier.lower()

        # Try exact filename match first
        exact_path = self.tasks_dir / identifier
        if exact_path.exists():
            return self.parse_task_file(exact_path)

        # Try with .md extension
        if not identifier.endswith(".md"):
            exact_path = self.tasks_dir / f"{identifier}.md"
            if exact_path.exists():
                return self.parse_task_file(exact_path)

        # Search by ID or title
        for task in self.list_tasks():
            task_id = str(task.get("id", "")).lower()
            task_title = str(task.get("title", "")).lower()
            task_file = Path(task.get("file", "")).stem.lower()

            if identifier_lower in [task_id, task_file]:
                return task
            if identifier_lower in task_title:
                return task

        return None

    def get_group(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a task group by name."""
        name_lower = name.lower()

        # Try exact filename
        exact_path = self.groups_dir / f"{name}.json"
        if exact_path.exists():
            try:
                return json.loads(exact_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Search by name
        for group in self.list_groups():
            if group.get("name", "").lower() == name_lower:
                return group

        return None

    def get_group_tasks(self, group_name: str) -> list:
        """Get all tasks in a group."""
        group = self.get_group(group_name)
        if not group:
            return []

        tasks = []
        for task_ref in group.get("tasks", []):
            task = self.get_task(task_ref)
            if task:
                tasks.append(task)

        return tasks

    def search_tasks(self, query: str) -> list:
        """Search tasks by query string."""
        query_lower = query.lower()
        results = []

        for task in self.list_tasks():
            task_id = task.get("id", "").lower()
            task_title = task.get("title", "").lower()
            task_tags = task.get("tags", [])
            task_prompt = task.get("prompt", "").lower()

            if (
                query_lower in task_id
                or query_lower in task_title
                or query_lower in task_prompt
                or any(query_lower in str(tag).lower() for tag in task_tags)
            ):
                results.append(task)

        return results


class RalphMode:
    """Main Ralph Mode controller."""

    RALPH_DIR = ".ralph-mode"
    STATE_FILE = "state.json"
    PROMPT_FILE = "prompt.md"
    INSTRUCTIONS_FILE = "INSTRUCTIONS.md"
    HISTORY_FILE = "history.jsonl"
    TASKS_DIR = "tasks"
    TASKS_INDEX = "tasks.json"

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize Ralph Mode with optional base path."""
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.ralph_dir = self.base_path / self.RALPH_DIR
        self.state_file = self.ralph_dir / self.STATE_FILE
        self.prompt_file = self.ralph_dir / self.PROMPT_FILE
        self.instructions_file = self.ralph_dir / self.INSTRUCTIONS_FILE
        self.history_file = self.ralph_dir / self.HISTORY_FILE
        self.tasks_dir = self.ralph_dir / self.TASKS_DIR
        self.tasks_index = self.ralph_dir / self.TASKS_INDEX

    def is_active(self) -> bool:
        """Check if Ralph mode is currently active."""
        return self.state_file.exists()

    def get_state(self) -> Optional[Dict[str, Any]]:
        """Get current Ralph mode state."""
        if not self.is_active():
            return None
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def save_state(self, state: Dict[str, Any]) -> None:
        """Save Ralph mode state."""
        self.ralph_dir.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def get_prompt(self) -> Optional[str]:
        """Get current prompt."""
        if not self.prompt_file.exists():
            return None
        return self.prompt_file.read_text(encoding="utf-8")

    def save_prompt(self, prompt: str) -> None:
        """Save prompt to file."""
        self.ralph_dir.mkdir(parents=True, exist_ok=True)
        self.prompt_file.write_text(prompt, encoding="utf-8")

    def load_tasks(self) -> list:
        """Load tasks list from tasks.json."""
        if not self.tasks_index.exists():
            return []
        try:
            with open(self.tasks_index, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def save_tasks(self, tasks: list) -> None:
        """Save tasks list to tasks.json."""
        self.ralph_dir.mkdir(parents=True, exist_ok=True)
        with open(self.tasks_index, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _slugify(text: str) -> str:
        """Create a filesystem-safe slug from text."""
        text = re.sub(r"[^a-zA-Z0-9\-_.]+", "-", text.strip())
        text = re.sub(r"-{2,}", "-", text).strip("-")
        return text.lower() or "task"

    def _task_filename(self, index: int, task_id: str, title: str) -> str:
        """Generate a filename for a task."""
        base = task_id or title
        slug = self._slugify(base)
        return f"{index + 1:02d}-{slug}.md"

    def _write_task_files(self, tasks: list) -> list:
        """Write tasks to individual files and return normalized task list."""
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        normalized = []

        for idx, task in enumerate(tasks):
            if isinstance(task, str):
                task_id = f"TASK-{idx + 1:03d}"
                title = task
                prompt = task
            else:
                task_id = task.get("id") or f"TASK-{idx + 1:03d}"
                title = task.get("title") or task.get("prompt") or task_id
                prompt = task.get("prompt") or title

            filename = self._task_filename(idx, task_id, title)
            task_path = self.tasks_dir / filename

            content = f"# {task_id} — {title}\n\n{prompt}\n"
            task_path.write_text(content, encoding="utf-8")

            normalized.append({"id": task_id, "title": title, "prompt": prompt, "file": str(task_path)})

        return normalized

    def _set_current_task(self, state: Dict[str, Any], tasks: list) -> None:
        """Set current task info in state and update prompt.md."""
        index = state.get("current_task_index", 0)
        if index < 0 or index >= len(tasks):
            raise ValueError("Current task index is out of range.")

        current = tasks[index]
        state["current_task_id"] = current.get("id")
        state["current_task_title"] = current.get("title")
        state["current_task_file"] = current.get("file")
        self.save_prompt(current.get("prompt") or current.get("title") or "")

    def log_iteration(self, iteration: int, status: str, notes: str = "") -> None:
        """Log iteration to history file."""
        entry = {
            "iteration": iteration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "notes": notes,
        }
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def create_instructions(
        self, completion_promise: Optional[str], max_iterations: int, mode: str = "single", auto_agents: bool = False
    ) -> None:
        """Create instructions file for Copilot."""
        content = """# 🔄 Ralph Mode Active

## What is Ralph Mode?

Ralph Mode is an iterative development loop where you (Copilot) work on a task
repeatedly until completion. The same prompt is fed back to you each iteration,
but you see your previous work in files and git history.

## ⚠️ CRITICAL: Make Real Changes

**You MUST make actual file modifications each iteration.**

### Anti-Patterns (DO NOT)
- ❌ Only running `grep`, `cat`, `find` to scan files
- ❌ Reading many files without making changes
- ❌ Outputting DONE when no changes were made
- ❌ Verifying existing code instead of modifying it

### Required Behavior (DO)
- ✅ Make at least ONE real file change per iteration
- ✅ Changes must be visible in `git diff`
- ✅ Follow the exact scope defined in the task
- ✅ If task is already satisfied, report FAILURE not DONE

## Your Workflow

1. **Read the task** from `.ralph-mode/prompt.md`
2. **Check scope** - ONLY modify files listed in scope
3. **Make changes** - edit files as specified
4. **Verify with git diff** - ensure changes are visible
5. **Signal completion** ONLY when criteria met

## Scope Rules

- **ONLY modify** files explicitly listed in the task
- **DO NOT read** files outside the scope
- **DO NOT scan** the entire codebase
- Focus on the specific change, nothing else

## Task Template Requirements

The task file must include these sections and you must follow them:

- **Objective**: exact change required
- **Scope**: ONLY modify / DO NOT read / DO NOT touch
- **Pre-work**: verify target file and locations
- **Changes Required**: specific, measurable edits
- **Acceptance Criteria**: must include visible `git diff`
- **Verification**: command(s) to validate change
- **Completion**: exact promise string

If required sections are missing or the change is already satisfied, report a blocker and do NOT output the promise.

## Current State

Read `.ralph-mode/state.json` for:
- `iteration`: Current iteration number
- `max_iterations`: Maximum allowed (0 = unlimited)
- `completion_promise`: Text to output when done
- `started_at`: When the loop started

"""

        if mode == "batch":
            content += """## Task Queue (Batch Mode)

- Tasks are stored in `.ralph-mode/tasks/`
- Task list is stored in `.ralph-mode/tasks.json`
- Current task is tracked in `state.json` (`current_task_index`, `current_task_id`)

"""

        if auto_agents:
            content += """## 🤖 Auto-Agents Mode (ENABLED)

You have the ability to **dynamically create specialized sub-agents** during task execution.

### When to Create Sub-Agents

Create a sub-agent when you need specialized behavior for:
- Complex subtasks requiring focused context
- Repetitive operations benefiting from dedicated tooling
- Parallel workstreams needing isolation
- Code review, testing, or refactoring tasks

### How to Create Sub-Agents

1. Create a `.agent.md` file in `.github/agents/`:

```markdown
---
name: my-custom-agent
description: Brief description of what this agent does
tools:
  - read_file
  - edit_file
  - run_in_terminal
---

# Agent Instructions

Your specialized instructions here...
```

2. After creating, invoke with: `@my-custom-agent <task description>`

### Agent Design Guidelines

- **Single Responsibility**: Each agent should do one thing well
- **Minimal Tools**: Only include tools the agent needs
- **Clear Instructions**: Be explicit about capabilities and boundaries
- **Context Awareness**: Include what files/patterns the agent works with

### Tracking Created Agents

Created agents are tracked in `state.json` under `created_agents`.
Review `.github/agents/` for all available agents.

### Available Base Agent (agent-creator)

Use `@agent-creator` for guidance on creating new agents.

"""

        if completion_promise:
            content += f"""## Completion

**To signal completion, output this EXACT text:**

```
<promise>{completion_promise}</promise>
```

⚠️ **CRITICAL RULES:**
- ONLY output the promise when the task is GENUINELY COMPLETE
- Do NOT lie to exit the loop
- The statement must be completely and unequivocally TRUE
- If stuck, document blockers instead of false promises

"""

        if max_iterations > 0:
            content += f"""## Iteration Limit

**Maximum Iterations:** {max_iterations}
- Loop will automatically stop after {max_iterations} iterations
- Current iteration is tracked in state.json

"""

        content += """## How to Check Status

```bash
# Cross-platform
python ralph-mode.py status

# Or read directly
cat .ralph-mode/state.json
cat .ralph-mode/prompt.md
```

## Philosophy

- **Iteration > Perfection**: Don't aim for perfect on first try
- **Failures Are Data**: Use errors to improve
- **Persistence Wins**: Keep trying until success

## History

All iterations are logged in `.ralph-mode/history.jsonl` for review.
"""

        self.instructions_file.write_text(content, encoding="utf-8")

    def enable(
        self,
        prompt: str,
        max_iterations: int = 0,
        completion_promise: Optional[str] = None,
        model: Optional[str] = None,
        auto_agents: bool = False,
    ) -> Dict[str, Any]:
        """Enable Ralph mode with the given configuration."""

        if self.is_active():
            current = self.get_state()
            raise ValueError(
                f"Ralph mode is already active (iteration {current.get('iteration', '?')}). "
                "Use 'disable' first or 'iterate' to continue."
            )

        # Resolve model: user choice > default > fallback
        resolved_model = model if model else DEFAULT_MODEL

        state = {
            "active": True,
            "iteration": 1,
            "max_iterations": max_iterations,
            "completion_promise": completion_promise,
            "model": resolved_model,
            "fallback_model": FALLBACK_MODEL,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "version": VERSION,
            "mode": "single",
            "auto_agents": auto_agents,
            "created_agents": [],
        }

        self.ralph_dir.mkdir(parents=True, exist_ok=True)
        self.save_state(state)
        self.save_prompt(prompt)
        self.create_instructions(completion_promise, max_iterations, mode="single", auto_agents=auto_agents)
        self.log_iteration(1, "started", f"Prompt: {prompt[:100]}...")

        # If auto_agents enabled, ensure agent-creator exists
        if auto_agents:
            self._ensure_agent_creator()

        return state

    def _ensure_agent_creator(self) -> None:
        """Ensure the agent-creator agent exists."""
        agents_dir = self.base_path / ".github" / "agents"
        creator_file = agents_dir / "agent-creator.agent.md"
        if not creator_file.exists():
            self.log_iteration(0, "auto_agents", "agent-creator.agent.md not found, auto-agents may not work optimally")

    def register_created_agent(self, agent_name: str, agent_file: str) -> None:
        """Register a dynamically created agent in state."""
        state = self.get_state()
        if state:
            created = state.get("created_agents", [])
            if agent_name not in [a.get("name") for a in created]:
                created.append(
                    {
                        "name": agent_name,
                        "file": agent_file,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "iteration": state.get("iteration", 0),
                    }
                )
                state["created_agents"] = created
                self.save_state(state)
                self.log_iteration(state.get("iteration", 0), "agent_created", f"Created agent: {agent_name}")

    def init_batch(
        self,
        tasks: list,
        max_iterations: int = 20,
        completion_promise: Optional[str] = None,
        model: Optional[str] = None,
        auto_agents: bool = False,
    ) -> Dict[str, Any]:
        """Initialize batch mode with multiple tasks."""
        if self.is_active():
            current = self.get_state()
            raise ValueError(
                f"Ralph mode is already active (iteration {current.get('iteration', '?')}). "
                "Use 'disable' first or 'iterate' to continue."
            )

        if not tasks:
            raise ValueError("Task list is empty. Provide at least one task.")

        normalized = self._write_task_files(tasks)
        self.save_tasks(normalized)

        # Resolve model: user choice > default > fallback
        resolved_model = model if model else DEFAULT_MODEL

        state = {
            "active": True,
            "iteration": 1,
            "max_iterations": max_iterations,
            "completion_promise": completion_promise,
            "model": resolved_model,
            "fallback_model": FALLBACK_MODEL,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "version": VERSION,
            "mode": "batch",
            "current_task_index": 0,
            "tasks_total": len(normalized),
            "auto_agents": auto_agents,
            "created_agents": [],
        }

        self._set_current_task(state, normalized)
        self.save_state(state)
        self.create_instructions(completion_promise, max_iterations, mode="batch", auto_agents=auto_agents)
        self.log_iteration(1, "batch_started", f"Tasks: {len(normalized)}")

        # If auto_agents enabled, ensure agent-creator exists
        if auto_agents:
            self._ensure_agent_creator()

        return state

        return state

    def next_task(self, reason: str = "completed") -> Dict[str, Any]:
        """Advance to the next task in batch mode."""
        state = self.get_state()
        if not state:
            raise ValueError("State file corrupted. Please disable and re-enable.")

        if state.get("mode") != "batch":
            raise ValueError("next_task is only available in batch mode.")

        tasks = self.load_tasks()
        if not tasks:
            raise ValueError("Tasks list is missing or corrupted.")

        current_index = state.get("current_task_index", 0)
        self.log_iteration(state.get("iteration", 0), f"task_{reason}", f"Task {current_index + 1}/{len(tasks)}")

        next_index = current_index + 1
        if next_index >= len(tasks):
            self.disable()
            raise ValueError("All tasks completed. Ralph mode disabled.")

        state["current_task_index"] = next_index
        state["iteration"] = 1
        state["last_iterate_at"] = datetime.now(timezone.utc).isoformat()
        self._set_current_task(state, tasks)
        self.save_state(state)

        return state

    def disable(self) -> Optional[Dict[str, Any]]:
        """Disable Ralph mode and return final state."""
        if not self.is_active():
            return None

        state = self.get_state()
        if state:
            self.log_iteration(state.get("iteration", 0), "disabled", "Ralph mode disabled by user")

        # Remove all files
        import shutil

        if self.ralph_dir.exists():
            shutil.rmtree(self.ralph_dir)

        return state

    def iterate(self) -> Dict[str, Any]:
        """Increment iteration counter and return new state."""
        if not self.is_active():
            raise ValueError("No active Ralph mode. Use 'enable' first.")

        state = self.get_state()
        if not state:
            raise ValueError("State file corrupted. Please disable and re-enable.")

        max_iter = state.get("max_iterations", 0)
        current_iter = state.get("iteration", 1)

        # Check if max iterations reached
        if max_iter > 0 and current_iter >= max_iter:
            if state.get("mode") == "batch":
                self.log_iteration(current_iter, "max_reached", f"Max iterations ({max_iter}) reached for task")
                return self.next_task(reason="max_reached")

            self.log_iteration(current_iter, "max_reached", f"Max iterations ({max_iter}) reached")
            self.disable()
            raise ValueError(f"Max iterations ({max_iter}) reached. Ralph mode disabled.")

        # Increment
        state["iteration"] = current_iter + 1
        state["last_iterate_at"] = datetime.now(timezone.utc).isoformat()
        self.save_state(state)
        self.log_iteration(state["iteration"], "iterate", "Iteration incremented")

        return state

    def check_completion(self, output_text: str) -> bool:
        """Check if output contains completion promise."""
        state = self.get_state()
        if not state:
            return False

        promise = state.get("completion_promise")
        if not promise:
            return False

        # Look for <promise>TEXT</promise>
        pattern = r"<promise>(.*?)</promise>"
        matches = re.findall(pattern, output_text, re.DOTALL)

        for match in matches:
            if match.strip() == promise.strip():
                self.log_iteration(state.get("iteration", 0), "completed", f"Completion promise detected: {promise}")
                return True

        return False

    def complete(self, output_text: str) -> bool:
        """Check completion and disable if complete."""
        if self.check_completion(output_text):
            state = self.get_state() or {}
            if state.get("mode") == "batch":
                self.next_task(reason="completed")
                return True

            self.disable()
            return True
        return False

    def status(self) -> Optional[Dict[str, Any]]:
        """Get full status including prompt."""
        if not self.is_active():
            return None

        state = self.get_state()
        if state:
            state["prompt"] = self.get_prompt()
            state["history_entries"] = self._count_history_entries()
            if state.get("mode") == "batch":
                state["tasks_total"] = state.get("tasks_total", 0)
                state["current_task_index"] = state.get("current_task_index", 0)
                state["current_task_number"] = state.get("current_task_index", 0) + 1
                state["current_task_id"] = state.get("current_task_id")
                state["current_task_title"] = state.get("current_task_title")
                state["current_task_file"] = state.get("current_task_file")

        return state

    def _count_history_entries(self) -> int:
        """Count entries in history file."""
        if not self.history_file.exists():
            return 0
        return sum(1 for _ in open(self.history_file, encoding="utf-8"))

    def get_history(self) -> list:
        """Get all history entries."""
        if not self.history_file.exists():
            return []

        entries = []
        with open(self.history_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return entries


def print_banner(title: str) -> None:
    """Print a colored banner."""
    width = 60
    print()


def _find_git_root(path: Path) -> Optional[Path]:
    """Find the nearest git root from the given path."""
    current = path.resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            return parent
    return None


def _ensure_project_root(strict: bool = False) -> bool:
    """Warn or error if not running from project root."""
    cwd = Path.cwd()
    git_root = _find_git_root(cwd)
    if git_root and git_root != cwd:
        message = (
            "Run Ralph from the project root. "
            f"Detected git root at: {git_root}. Current: {cwd}."
        )
        if strict:
            print(f"{colors.RED}❌ Error: {message}{colors.NC}")
            return False
        print(f"{colors.YELLOW}⚠️ Warning: {message}{colors.NC}")
    return True


def _missing_task_requirements(prompt: str) -> list[str]:
    """Return a list of missing task sections or scope markers."""
    missing = []
    normalized = prompt.lower()

    for section in REQUIRED_TASK_SECTIONS:
        if section.lower() not in normalized:
            missing.append(section)

    for marker in REQUIRED_SCOPE_MARKERS:
        if marker.lower() not in normalized:
            missing.append(marker)

    return missing


def _validate_task_prompt(task_label: str, prompt: str, strict: bool = False) -> bool:
    """Validate task prompt against required sections and scope markers."""
    if not prompt.strip():
        missing = REQUIRED_TASK_SECTIONS + REQUIRED_SCOPE_MARKERS
    else:
        missing = _missing_task_requirements(prompt)

    if not missing:
        return True

    missing_list = ", ".join(missing)
    message = f"Task '{task_label}' is missing required sections or scope rules: {missing_list}"
    if strict:
        print(f"{colors.RED}❌ Error: {message}{colors.NC}")
        return False
    print(f"{colors.YELLOW}⚠️ Warning: {message}{colors.NC}")
    return True
    print(f"{colors.GREEN}╔{'═' * width}╗{colors.NC}")
    print(f"{colors.GREEN}║{title:^{width}}║{colors.NC}")
    print(f"{colors.GREEN}╚{'═' * width}╝{colors.NC}")
    print()


def cmd_enable(args) -> int:
    """Handle enable command."""
    if not _ensure_project_root(strict=STRICT_ROOT):
        return 1

    ralph = RalphMode()

    prompt = " ".join(args.prompt) if args.prompt else ""
    if not prompt:
        print(f"{colors.RED}❌ Error: No prompt provided{colors.NC}")
        print('\nUsage: ralph-mode enable "Your task description" [options]')
        return 1

    if not _validate_task_prompt("manual prompt", prompt, strict=STRICT_TASKS):
        return 1

    # Validate model if provided
    model = args.model
    if model and model != "auto" and model not in AVAILABLE_MODELS:
        print(f"{colors.YELLOW}⚠️ Warning: Model '{model}' may not be available. Using anyway...{colors.NC}")

    try:
        state = ralph.enable(
            prompt=prompt,
            max_iterations=args.max_iterations,
            completion_promise=args.completion_promise,
            model=model,
            auto_agents=args.auto_agents,
        )
    except ValueError as e:
        print(f"{colors.RED}❌ Error: {e}{colors.NC}")
        return 1

    print_banner("🔄 RALPH MODE ENABLED")

    print(f"{colors.CYAN}Iteration:{colors.NC}          1")
    print(
        f"{colors.CYAN}Max Iterations:{colors.NC}     {args.max_iterations if args.max_iterations > 0 else 'unlimited'}"
    )
    print(f"{colors.CYAN}Model:{colors.NC}              {state.get('model', DEFAULT_MODEL)}")
    print(f"{colors.CYAN}Fallback:{colors.NC}           {state.get('fallback_model', FALLBACK_MODEL)}")
    print(f"{colors.CYAN}Auto-Agents:{colors.NC}        {'enabled' if args.auto_agents else 'disabled'}")
    print(f"{colors.CYAN}Completion Promise:{colors.NC} {args.completion_promise or 'none'}")
    print()
    print(f"{colors.YELLOW}📝 Task:{colors.NC}")
    print(prompt)
    print()

    if args.completion_promise:
        print(f"{colors.YELLOW}{'═' * 60}{colors.NC}")
        print(f"{colors.YELLOW}COMPLETION PROMISE REQUIREMENTS{colors.NC}")
        print(f"{colors.YELLOW}{'═' * 60}{colors.NC}")
        print()
        print("To complete this loop, Copilot must output:")
        print(f"  {colors.GREEN}<promise>{args.completion_promise}</promise>{colors.NC}")
        print()
        print("⚠️  ONLY when the statement is GENUINELY TRUE")
        print(f"{colors.YELLOW}{'═' * 60}{colors.NC}")

    print()
    print(f"{colors.GREEN}✅ Ralph mode is now active!{colors.NC}")
    print(f"{colors.BLUE}ℹ Copilot will read .ralph-mode/INSTRUCTIONS.md for guidance{colors.NC}")

    return 0


def _load_tasks_from_file(tasks_file: str) -> list:
    """Load tasks from a JSON file."""
    path = Path(tasks_file)
    if not path.exists():
        raise ValueError(f"Tasks file not found: {tasks_file}")

    if path.suffix.lower() != ".json":
        raise ValueError("Tasks file must be a .json file")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in tasks file: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError("Tasks file must contain a JSON array")

    return data


def cmd_batch_init(args) -> int:
    """Handle batch-init command."""
    if not _ensure_project_root(strict=STRICT_ROOT):
        return 1

    ralph = RalphMode()

    # Validate model if provided
    model = args.model
    if model and model != "auto" and model not in AVAILABLE_MODELS:
        print(f"{colors.YELLOW}⚠️ Warning: Model '{model}' may not be available. Using anyway...{colors.NC}")

    try:
        tasks = _load_tasks_from_file(args.tasks_file)
    except ValueError as e:
        print(f"{colors.RED}❌ Error: {e}{colors.NC}")
        return 1

    for idx, task in enumerate(tasks, start=1):
        if isinstance(task, str):
            task_label = f"TASK-{idx:03d}"
            prompt = task
        else:
            task_label = task.get("id") or f"TASK-{idx:03d}"
            prompt = task.get("prompt", "")

        if not _validate_task_prompt(task_label, prompt, strict=STRICT_TASKS):
            return 1

    try:
        state = ralph.init_batch(
            tasks=tasks,
            max_iterations=args.max_iterations,
            completion_promise=args.completion_promise,
            model=model,
            auto_agents=args.auto_agents,
        )
    except ValueError as e:
        print(f"{colors.RED}❌ Error: {e}{colors.NC}")
        return 1

    print_banner("🔄 RALPH MODE BATCH STARTED")
    print(f"{colors.CYAN}Mode:{colors.NC}             batch")
    print(f"{colors.CYAN}Tasks Total:{colors.NC}      {state.get('tasks_total')}")
    print(f"{colors.CYAN}Current Task:{colors.NC}     1/{state.get('tasks_total')}")
    print(f"{colors.CYAN}Iteration:{colors.NC}        1")
    print(f"{colors.CYAN}Max Iterations:{colors.NC}   {args.max_iterations}")
    print(f"{colors.CYAN}Model:{colors.NC}            {state.get('model', DEFAULT_MODEL)}")
    print(f"{colors.CYAN}Fallback:{colors.NC}         {state.get('fallback_model', FALLBACK_MODEL)}")
    print(f"{colors.CYAN}Auto-Agents:{colors.NC}      {'enabled' if args.auto_agents else 'disabled'}")
    print(f"{colors.CYAN}Completion Promise:{colors.NC} {args.completion_promise or 'none'}")
    print()
    print(f"{colors.YELLOW}📝 Current Task:{colors.NC}")
    print(state.get("current_task_title") or "")
    print()
    print(f"{colors.GREEN}✅ Ralph batch mode is now active!{colors.NC}")
    print(f"{colors.BLUE}ℹ Copilot will read .ralph-mode/INSTRUCTIONS.md for guidance{colors.NC}")

    return 0


def cmd_next_task(args) -> int:
    """Handle next-task command."""
    ralph = RalphMode()

    try:
        state = ralph.next_task(reason="manual_next")
    except ValueError as e:
        print(f"{colors.YELLOW}⚠️ {e}{colors.NC}")
        return 1

    print(f"🔄 Moved to next task: {state.get('current_task_index', 0) + 1}/{state.get('tasks_total', 0)}")
    print(f"{colors.YELLOW}📝 Current Task:{colors.NC} {state.get('current_task_title') or ''}")
    return 0


def cmd_disable(args) -> int:
    """Handle disable command."""
    ralph = RalphMode()

    state = ralph.disable()
    if state:
        print()
        print(f"{colors.GREEN}✅ Ralph mode disabled (was at iteration {state.get('iteration', '?')}){colors.NC}")
    else:
        print(f"{colors.YELLOW}⚠️ No active Ralph mode found{colors.NC}")

    return 0


def cmd_status(args) -> int:
    """Handle status command."""
    ralph = RalphMode()

    status = ralph.status()
    if not status:
        print()
        print(f"{colors.YELLOW}Ralph Mode: {colors.RED}INACTIVE{colors.NC}")
        print()
        print('To enable: ralph-mode enable "Your task" --max-iterations 20')
        return 0

    print_banner("🔄 RALPH MODE STATUS")

    print(f"{colors.CYAN}Status:{colors.NC}             {colors.GREEN}ACTIVE{colors.NC}")
    print(f"{colors.CYAN}Mode:{colors.NC}               {status.get('mode', 'single')}")
    print(f"{colors.CYAN}Iteration:{colors.NC}          {status.get('iteration', '?')}")
    max_iter = status.get("max_iterations", 0)
    print(f"{colors.CYAN}Max Iterations:{colors.NC}     {max_iter if max_iter > 0 else 'unlimited'}")
    model = status.get("model", DEFAULT_MODEL)
    fallback = status.get("fallback_model", FALLBACK_MODEL)
    print(f"{colors.CYAN}Model:{colors.NC}              {model}")
    print(f"{colors.CYAN}Fallback:{colors.NC}           {fallback}")
    auto_agents = status.get("auto_agents", False)
    print(f"{colors.CYAN}Auto-Agents:{colors.NC}        {'enabled' if auto_agents else 'disabled'}")
    created_agents = status.get("created_agents", [])
    if created_agents:
        print(f"{colors.CYAN}Created Agents:{colors.NC}     {len(created_agents)}")
        for agent in created_agents:
            print(f"  - {agent.get('name', 'unknown')} (iter {agent.get('iteration', '?')})")
    promise = status.get("completion_promise")
    print(f"{colors.CYAN}Completion Promise:{colors.NC} {promise if promise else 'none'}")
    print(f"{colors.CYAN}Started At:{colors.NC}         {status.get('started_at', '?')}")
    print(f"{colors.CYAN}History Entries:{colors.NC}    {status.get('history_entries', 0)}")
    if status.get("mode") == "batch":
        print(f"{colors.CYAN}Tasks Total:{colors.NC}        {status.get('tasks_total', 0)}")
        current_task = status.get('current_task_number', 0)
        total_tasks = status.get('tasks_total', 0)
        print(f"{colors.CYAN}Current Task:{colors.NC}       {current_task}/{total_tasks}")
        print(f"{colors.CYAN}Current Task ID:{colors.NC}    {status.get('current_task_id') or 'n/a'}")
    print()
    print(f"{colors.YELLOW}📝 Current Task:{colors.NC}")
    print(status.get("prompt", "No prompt found"))
    print()

    return 0


def cmd_prompt(args) -> int:
    """Handle prompt command."""
    ralph = RalphMode()

    if not ralph.is_active():
        print(f"{colors.RED}❌ No active Ralph mode{colors.NC}")
        return 1

    prompt = ralph.get_prompt()
    if prompt:
        print(prompt)
    else:
        print(f"{colors.RED}❌ No prompt found{colors.NC}")
        return 1

    return 0


def cmd_iterate(args) -> int:
    """Handle iterate command."""
    ralph = RalphMode()

    try:
        state = ralph.iterate()
        print(f"🔄 Ralph iteration: {colors.GREEN}{state['iteration']}{colors.NC}")
    except ValueError as e:
        print(f"{colors.YELLOW}⚠️ {e}{colors.NC}")
        return 1

    return 0


def cmd_complete(args) -> int:
    """Handle complete command - check if output contains promise."""
    ralph = RalphMode()

    if not ralph.is_active():
        print(f"{colors.RED}❌ No active Ralph mode{colors.NC}")
        return 1

    # Read output from stdin or argument
    if args.output:
        output = " ".join(args.output)
    else:
        output = sys.stdin.read()

    if ralph.complete(output):
        state = ralph.get_state()
        if state and state.get("mode") == "batch":
            print(f"{colors.GREEN}✅ Completion promise detected! Moved to next task.{colors.NC}")
            return 0

        print(f"{colors.GREEN}✅ Completion promise detected! Ralph mode disabled.{colors.NC}")
        return 0
    else:
        print(f"{colors.YELLOW}⚠️ No completion promise found. Continue iterating.{colors.NC}")
        return 1


def cmd_history(args) -> int:
    """Handle history command."""
    ralph = RalphMode()

    history = ralph.get_history()
    if not history:
        print("No history found.")
        return 0

    print(f"\n{'Iteration':<12} {'Status':<15} {'Timestamp':<25} Notes")
    print("-" * 80)

    for entry in history:
        print(
            f"{entry.get('iteration', '?'):<12} "
            f"{entry.get('status', '?'):<15} "
            f"{entry.get('timestamp', '?')[:19]:<25} "
            f"{entry.get('notes', '')[:30]}"
        )

    print()
    return 0


def cmd_tasks(args) -> int:
    """Handle tasks command - list, search, show tasks."""
    library = TaskLibrary()

    action = args.action if hasattr(args, "action") else "list"

    if action == "list":
        tasks = library.list_tasks()
        groups = library.list_groups()

        if not tasks and not groups:
            print(f"{colors.YELLOW}No tasks found in tasks/ directory{colors.NC}")
            print("Create task files like: tasks/my-task.md")
            return 0

        print_banner("📋 TASK LIBRARY")

        if tasks:
            print(f"{colors.CYAN}Tasks:{colors.NC}")
            for task in tasks:
                task_id = task.get("id", "N/A")
                title = task.get("title", "Untitled")
                tags = task.get("tags", [])
                tags_str = f" [{', '.join(tags)}]" if tags else ""
                print(f"  {colors.GREEN}{task_id:<12}{colors.NC} {title}{colors.YELLOW}{tags_str}{colors.NC}")
            print()

        if groups:
            print(f"{colors.CYAN}Groups:{colors.NC}")
            for group in groups:
                name = group.get("name", "N/A")
                title = group.get("title", "Untitled")
                task_count = len(group.get("tasks", []))
                print(f"  {colors.GREEN}{name:<12}{colors.NC} {title} ({task_count} tasks)")
            print()

        return 0

    elif action == "show":
        identifier = args.identifier if hasattr(args, "identifier") else None
        if not identifier:
            print(f"{colors.RED}❌ Please specify a task ID or filename{colors.NC}")
            return 1

        task = library.get_task(identifier)
        if not task:
            print(f"{colors.RED}❌ Task not found: {identifier}{colors.NC}")
            return 1

        print_banner(f"📋 {task.get('id', 'TASK')}")
        print(f"{colors.CYAN}Title:{colors.NC}      {task.get('title', 'Untitled')}")
        print(f"{colors.CYAN}ID:{colors.NC}         {task.get('id', 'N/A')}")
        tags = task.get("tags", [])
        print(f"{colors.CYAN}Tags:{colors.NC}       {', '.join(tags) if tags else 'none'}")
        print(f"{colors.CYAN}Model:{colors.NC}      {task.get('model', DEFAULT_MODEL)}")
        print(f"{colors.CYAN}Max Iter:{colors.NC}   {task.get('max_iterations', 20)}")
        print(f"{colors.CYAN}Promise:{colors.NC}    {task.get('completion_promise', 'DONE')}")
        print(f"{colors.CYAN}File:{colors.NC}       {task.get('file', 'N/A')}")
        print()
        print(f"{colors.YELLOW}📝 Prompt:{colors.NC}")
        print(task.get("prompt", "No prompt"))
        print()

        return 0

    elif action == "search":
        query = args.identifier if hasattr(args, "identifier") and args.identifier else ""
        if not query:
            print(f"{colors.RED}❌ Please specify a search query{colors.NC}")
            return 1

        results = library.search_tasks(query)
        if not results:
            print(f"{colors.YELLOW}No tasks found matching: {query}{colors.NC}")
            return 0

        print(f"\n{colors.GREEN}Found {len(results)} task(s):{colors.NC}\n")
        for task in results:
            task_id = task.get("id", "N/A")
            title = task.get("title", "Untitled")
            print(f"  {colors.GREEN}{task_id:<12}{colors.NC} {title}")
        print()

        return 0

    else:
        print(f"{colors.RED}❌ Unknown action: {action}{colors.NC}")
        return 1


def cmd_run(args) -> int:
    """Handle run command - run a task from library."""
    if not _ensure_project_root(strict=STRICT_ROOT):
        return 1

    library = TaskLibrary()
    ralph = RalphMode()

    # Check if already active
    if ralph.is_active():
        print(f"{colors.RED}❌ Ralph mode is already active. Use 'disable' first.{colors.NC}")
        return 1

    # Get task or group
    task_id = args.task if hasattr(args, "task") and args.task else None
    group_name = args.group if hasattr(args, "group") and args.group else None

    if not task_id and not group_name:
        print(f"{colors.RED}❌ Please specify --task or --group{colors.NC}")
        print("\nUsage:")
        print("  ralph-mode run --task RTL-001")
        print("  ralph-mode run --task rtl-text-direction.md")
        print("  ralph-mode run --group rtl")
        return 1

    # Handle single task
    if task_id:
        task = library.get_task(task_id)
        if not task:
            print(f"{colors.RED}❌ Task not found: {task_id}{colors.NC}")
            print("\nAvailable tasks:")
            for t in library.list_tasks()[:5]:
                print(f"  - {t.get('id', 'N/A')}")
            return 1

        if not _validate_task_prompt(task.get("id", "TASK"), task.get("prompt", ""), strict=STRICT_TASKS):
            return 1

        # Get options from task file or args
        model = args.model if hasattr(args, "model") and args.model else task.get("model")
        max_iter = (
            args.max_iterations
            if hasattr(args, "max_iterations") and args.max_iterations
            else task.get("max_iterations", 20)
        )
        promise = (
            args.completion_promise
            if hasattr(args, "completion_promise") and args.completion_promise
            else task.get("completion_promise", "DONE")
        )

        try:
            state = ralph.enable(
                prompt=task.get("prompt", ""), max_iterations=max_iter, completion_promise=promise, model=model
            )
        except ValueError as e:
            print(f"{colors.RED}❌ Error: {e}{colors.NC}")
            return 1

        print_banner(f"🔄 RUNNING: {task.get('id', 'TASK')}")
        print(f"{colors.CYAN}Title:{colors.NC}       {task.get('title', 'Untitled')}")
        print(f"{colors.CYAN}Model:{colors.NC}       {state.get('model', DEFAULT_MODEL)}")
        print(f"{colors.CYAN}Max Iter:{colors.NC}    {max_iter}")
        print(f"{colors.CYAN}Promise:{colors.NC}     {promise}")
        print()
        print(f"{colors.GREEN}✅ Task loaded! Run ./ralph-loop.sh run to start.{colors.NC}")

        return 0

    # Handle group
    if group_name:
        tasks = library.get_group_tasks(group_name)
        if not tasks:
            print(f"{colors.RED}❌ Group not found or empty: {group_name}{colors.NC}")
            print("\nAvailable groups:")
            for g in library.list_groups():
                print(f"  - {g.get('name', 'N/A')}")
            return 1

        for task in tasks:
            if not _validate_task_prompt(task.get("id", "TASK"), task.get("prompt", ""), strict=STRICT_TASKS):
                return 1

        # Get options from args
        model = args.model if hasattr(args, "model") and args.model else None
        max_iter = args.max_iterations if hasattr(args, "max_iterations") and args.max_iterations else 20
        promise = args.completion_promise if hasattr(args, "completion_promise") and args.completion_promise else "DONE"

        # Prepare batch tasks
        batch_tasks = []
        for task in tasks:
            batch_tasks.append(
                {
                    "id": task.get("id"),
                    "title": task.get("title"),
                    "prompt": task.get("prompt"),
                    "model": task.get("model", model),
                    "max_iterations": task.get("max_iterations", max_iter),
                    "completion_promise": task.get("completion_promise", promise),
                }
            )

        try:
            state = ralph.init_batch(
                tasks=batch_tasks, max_iterations=max_iter, completion_promise=promise, model=model
            )
        except ValueError as e:
            print(f"{colors.RED}❌ Error: {e}{colors.NC}")
            return 1

        print_banner(f"🔄 RUNNING GROUP: {group_name}")
        print(f"{colors.CYAN}Tasks:{colors.NC}       {len(batch_tasks)}")
        print(f"{colors.CYAN}Model:{colors.NC}       {state.get('model', DEFAULT_MODEL)}")
        print(f"{colors.CYAN}Max Iter:{colors.NC}    {max_iter} per task")
        print()
        print(f"{colors.YELLOW}Tasks in queue:{colors.NC}")
        for i, t in enumerate(batch_tasks, 1):
            print(f"  {i}. {t.get('id', 'N/A')} - {t.get('title', 'Untitled')}")
        print()
        print(f"{colors.GREEN}✅ Group loaded! Run ./ralph-loop.sh run to start.{colors.NC}")

        return 0

    return 1


def cmd_help(args) -> int:
    """Handle help command."""
    models_str = ", ".join(AVAILABLE_MODELS[:5]) + "..."
    print(f"""
{colors.GREEN}🔄 Copilot Ralph Mode v{VERSION}{colors.NC}

Implementation of the Ralph Wiggum technique for iterative,
self-referential AI development loops with GitHub Copilot.

{colors.YELLOW}USAGE:{colors.NC}
    ralph-mode <command> [options]

{colors.YELLOW}COMMANDS:{colors.NC}
    enable      Enable Ralph mode with a prompt
    run         Run a task from the task library
    tasks       List, search, or show tasks
    batch-init  Initialize batch mode with multiple tasks
    disable     Disable Ralph mode
    status      Show current status
    prompt      Show current prompt
    iterate     Increment iteration counter
    next-task   Move to next task in batch mode
    complete    Check if output contains completion promise
    history     Show iteration history
    help        Show this help message

{colors.YELLOW}TASK LIBRARY:{colors.NC}
    tasks list              List all available tasks
    tasks show <id>         Show task details
    tasks search <query>    Search tasks
    run --task <id>         Run a single task
    run --group <name>      Run a group of tasks

{colors.YELLOW}ENABLE OPTIONS:{colors.NC}
    --max-iterations <n>        Maximum iterations (default: 0 = unlimited)
    --completion-promise <text> Phrase that signals completion
    --model <model>             AI model to use (default: {DEFAULT_MODEL})

{colors.YELLOW}BATCH OPTIONS:{colors.NC}
    --tasks-file <path>          JSON file with tasks list
    --max-iterations <n>         Maximum iterations per task (default: 20)
    --completion-promise <text>  Phrase that signals completion
    --model <model>              AI model to use (default: {DEFAULT_MODEL})

{colors.YELLOW}MODEL OPTIONS:{colors.NC}
    auto                         Automatic model selection
    {DEFAULT_MODEL}                    Default model (recommended for coding)
    Available: {models_str}

{colors.YELLOW}EXAMPLES:{colors.NC}
    ralph-mode enable "Build a REST API" --max-iterations 20
    ralph-mode run --task RTL-001
    ralph-mode run --group rtl
    ralph-mode tasks list
    ralph-mode tasks show RTL-001
    ralph-mode enable "Fix tests" --model claude-sonnet-4.5
    ralph-mode batch-init --tasks-file tasks.json --max-iterations 20
    ralph-mode status
    ralph-mode disable

{colors.YELLOW}PHILOSOPHY:{colors.NC}
    • Iteration > Perfection
    • Failures Are Data
    • Persistence Wins

{colors.YELLOW}LEARN MORE:{colors.NC}
    • Original technique: https://ghuntley.com/ralph/
    • Claude Code plugin: https://github.com/anthropics/claude-code
""")
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="ralph-mode", description="Copilot Ralph Mode - Iterative AI development loops"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Enable command
    enable_parser = subparsers.add_parser("enable", help="Enable Ralph mode")
    enable_parser.add_argument("prompt", nargs="*", help="Task prompt")
    enable_parser.add_argument("--max-iterations", type=int, default=0, help="Maximum iterations (0 = unlimited)")
    enable_parser.add_argument("--completion-promise", type=str, default=None, help="Phrase that signals completion")
    enable_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"AI model to use (default: {DEFAULT_MODEL}, fallback: {FALLBACK_MODEL}). "
        f'Use "auto" for automatic selection.',
    )
    enable_parser.add_argument(
        "--auto-agents", action="store_true", default=False, help="Enable dynamic sub-agent creation during iterations"
    )
    enable_parser.set_defaults(func=cmd_enable)

    # Batch init command
    batch_parser = subparsers.add_parser("batch-init", help="Initialize batch mode")
    batch_parser.add_argument("--tasks-file", required=True, help="Path to tasks JSON file")
    batch_parser.add_argument(
        "--max-iterations", type=int, default=20, help="Maximum iterations per task (default: 20)"
    )
    batch_parser.add_argument("--completion-promise", type=str, default=None, help="Phrase that signals completion")
    batch_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"AI model to use (default: {DEFAULT_MODEL}, fallback: {FALLBACK_MODEL}). "
        f'Use "auto" for automatic selection.',
    )
    batch_parser.add_argument(
        "--auto-agents", action="store_true", default=False, help="Enable dynamic sub-agent creation during iterations"
    )
    batch_parser.set_defaults(func=cmd_batch_init)

    # Disable command
    disable_parser = subparsers.add_parser("disable", help="Disable Ralph mode")
    disable_parser.set_defaults(func=cmd_disable)

    # Status command
    status_parser = subparsers.add_parser("status", help="Show status")
    status_parser.set_defaults(func=cmd_status)

    # Prompt command
    prompt_parser = subparsers.add_parser("prompt", help="Show current prompt")
    prompt_parser.set_defaults(func=cmd_prompt)

    # Iterate command
    iterate_parser = subparsers.add_parser("iterate", help="Increment iteration")
    iterate_parser.set_defaults(func=cmd_iterate)

    # Next task command
    next_parser = subparsers.add_parser("next-task", help="Move to next task in batch mode")
    next_parser.set_defaults(func=cmd_next_task)

    # Complete command
    complete_parser = subparsers.add_parser("complete", help="Check completion")
    complete_parser.add_argument("output", nargs="*", help="Output to check")
    complete_parser.set_defaults(func=cmd_complete)

    # History command
    history_parser = subparsers.add_parser("history", help="Show history")
    history_parser.set_defaults(func=cmd_history)

    # Tasks command (task library)
    tasks_parser = subparsers.add_parser("tasks", help="Manage task library")
    tasks_parser.add_argument("action", choices=["list", "show", "search"], help="Action to perform")
    tasks_parser.add_argument("identifier", nargs="?", default=None, help="Task ID, filename, or search query")
    tasks_parser.set_defaults(func=cmd_tasks)

    # Run command (run from task library)
    run_parser = subparsers.add_parser("run", help="Run task from library")
    run_parser.add_argument("--task", type=str, default=None, help="Task ID or filename to run")
    run_parser.add_argument("--group", type=str, default=None, help="Task group name to run")
    run_parser.add_argument(
        "--model", type=str, default=None, help=f"Override model (default from task file or {DEFAULT_MODEL})"
    )
    run_parser.add_argument("--max-iterations", type=int, default=None, help="Override max iterations")
    run_parser.set_defaults(func=cmd_run)

    # Help command
    help_parser = subparsers.add_parser("help", help="Show help")
    help_parser.set_defaults(func=cmd_help)

    args = parser.parse_args()

    if not args.command:
        return cmd_help(args)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
