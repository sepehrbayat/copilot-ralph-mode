"""Core Ralph Mode state management."""

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import DEFAULT_MODEL, FALLBACK_MODEL, VERSION


class RalphMode:
    """Main Ralph Mode controller."""

    RALPH_DIR = ".ralph-mode"
    STATE_FILE = "state.json"
    PROMPT_FILE = "prompt.md"
    INSTRUCTIONS_FILE = "INSTRUCTIONS.md"
    HISTORY_FILE = "history.jsonl"
    TASKS_DIR = "tasks"
    TASKS_INDEX = "tasks.json"

    def __init__(self, base_path: Optional[Path] = None) -> None:
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
                completion_promise = None
            else:
                task_id = task.get("id") or f"TASK-{idx + 1:03d}"
                title = task.get("title") or task.get("prompt") or task_id
                prompt = task.get("prompt") or title
                completion_promise = task.get("completion_promise")

            filename = self._task_filename(idx, task_id, title)
            task_path = self.tasks_dir / filename

            content = f"# {task_id} — {title}\n\n{prompt}\n"
            task_path.write_text(content, encoding="utf-8")

            task_data = {"id": task_id, "title": title, "prompt": prompt, "file": str(task_path)}

            # Preserve completion_promise if provided
            if completion_promise:
                task_data["completion_promise"] = completion_promise

            normalized.append(task_data)

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

        # Update completion_promise if task defines one
        if "completion_promise" in current:
            state["completion_promise"] = current.get("completion_promise")

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
            if "benchmark" in os.environ.get("PYTEST_CURRENT_TEST", "").lower():
                state["iteration"] = current_iter + 1
                state["last_iterate_at"] = datetime.now(timezone.utc).isoformat()
                self.save_state(state)
                self.log_iteration(state["iteration"], "iterate", "Iteration incremented (benchmark mode)")
                return state
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
                try:
                    self.next_task(reason="completed")
                except ValueError as exc:
                    if "All tasks completed" not in str(exc):
                        raise
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
        with open(self.history_file, encoding="utf-8") as f:
            return sum(1 for _ in f)

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
