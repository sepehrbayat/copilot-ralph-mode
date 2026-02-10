#!/usr/bin/env python3
"""Backward-compatible entry point for ``python ralph_mode.py``.

If the packaged CLI is not available (e.g. when this file is copied into a
standalone temp workspace for tests), fall back to a minimal built-in CLI.
"""

import sys

try:
    from ralph_mode.cli import main as _main
except ModuleNotFoundError as exc:  # pragma: no cover - fallback for standalone execution
    if exc.name not in ("ralph_mode", "ralph_mode.cli"):
        raise
    import argparse
    import json
    import os
    import re
    from datetime import datetime, timezone
    from pathlib import Path

    VERSION = "1.1.0"

    class _FallbackRalphMode:
        """Minimal standalone implementation used when package is unavailable."""

        RALPH_DIR = ".ralph-mode"
        STATE_FILE = "state.json"
        PROMPT_FILE = "prompt.md"
        TASKS_DIR = "tasks"
        TASKS_INDEX = "tasks.json"

        def __init__(self, base_path: Path | None = None) -> None:
            self.base_path = base_path if base_path else Path.cwd()
            self.ralph_dir = self.base_path / self.RALPH_DIR
            self.state_file = self.ralph_dir / self.STATE_FILE
            self.prompt_file = self.ralph_dir / self.PROMPT_FILE
            self.tasks_dir = self.ralph_dir / self.TASKS_DIR
            self.tasks_index = self.ralph_dir / self.TASKS_INDEX

        def is_active(self) -> bool:
            return self.state_file.exists()

        def get_state(self) -> dict | None:
            if not self.is_active():
                return None
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None

        def save_state(self, state: dict) -> None:
            self.ralph_dir.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

        def save_prompt(self, prompt: str) -> None:
            self.ralph_dir.mkdir(parents=True, exist_ok=True)
            self.prompt_file.write_text(prompt, encoding="utf-8")

        def _slugify(self, text: str) -> str:
            text = re.sub(r"[^a-zA-Z0-9\-_.]+", "-", text.strip())
            text = re.sub(r"-{2,}", "-", text).strip("-")
            return text.lower() or "task"

        def _task_filename(self, index: int, task_id: str, title: str) -> str:
            base = task_id or title
            slug = self._slugify(base)
            return f"{index + 1:02d}-{slug}.md"

        def _write_task_files(self, tasks: list) -> list:
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
                task_path.write_text(f"# {task_id} — {title}\n\n{prompt}\n", encoding="utf-8")
                normalized.append({"id": task_id, "title": title, "prompt": prompt, "file": str(task_path)})
            return normalized

        def _set_current_task(self, state: dict, tasks: list) -> None:
            index = state.get("current_task_index", 0)
            current = tasks[index]
            state["current_task_id"] = current.get("id")
            state["current_task_title"] = current.get("title")
            state["current_task_file"] = current.get("file")
            self.save_prompt(current.get("prompt") or current.get("title") or "")

        def enable(self, prompt: str, max_iterations: int = 0, completion_promise: str | None = None) -> dict:
            if self.is_active():
                raise ValueError("Ralph mode is already active.")
            state = {
                "active": True,
                "iteration": 1,
                "max_iterations": max_iterations,
                "completion_promise": completion_promise,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "mode": "single",
            }
            self.save_state(state)
            self.save_prompt(prompt)
            return state

        def init_batch(self, tasks: list, max_iterations: int, completion_promise: str | None) -> dict:
            if self.is_active():
                raise ValueError("Ralph mode is already active.")
            normalized = self._write_task_files(tasks)
            self.tasks_index.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
            state = {
                "active": True,
                "iteration": 1,
                "max_iterations": max_iterations,
                "completion_promise": completion_promise,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "mode": "batch",
                "current_task_index": 0,
                "tasks_total": len(normalized),
            }
            self._set_current_task(state, normalized)
            self.save_state(state)
            return state

        def iterate(self) -> dict:
            state = self.get_state()
            if not state:
                raise ValueError("No active Ralph mode.")
            state["iteration"] = int(state.get("iteration", 1)) + 1
            self.save_state(state)
            return state

        def complete(self, output_text: str) -> bool:
            state = self.get_state() or {}
            promise = state.get("completion_promise")
            if not promise:
                return False
            if f"<promise>{promise}</promise>" in output_text:
                if state.get("mode") == "batch":
                    self.next_task()
                else:
                    self.disable()
                return True
            return False

        def next_task(self) -> dict:
            state = self.get_state() or {}
            tasks = json.loads(self.tasks_index.read_text(encoding="utf-8"))
            idx = int(state.get("current_task_index", 0)) + 1
            if idx >= len(tasks):
                self.disable()
                raise ValueError("All tasks completed. Ralph mode disabled.")
            state["current_task_index"] = idx
            state["iteration"] = 1
            self._set_current_task(state, tasks)
            self.save_state(state)
            return state

        def disable(self) -> None:
            if self.ralph_dir.exists():
                for root, dirs, files in os.walk(self.ralph_dir, topdown=False):
                    for name in files:
                        Path(root, name).unlink(missing_ok=True)
                    for name in dirs:
                        Path(root, name).rmdir()
                self.ralph_dir.rmdir()

        def status(self) -> dict | None:
            state = self.get_state()
            if state:
                prompt = self.prompt_file.read_text(encoding="utf-8") if self.prompt_file.exists() else ""
                state["prompt"] = prompt
            return state

    def _fallback_main() -> int:
        parser = argparse.ArgumentParser(prog="ralph-mode", description="Ralph Mode CLI (fallback)")
        parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
        subparsers = parser.add_subparsers(dest="command")

        enable_parser = subparsers.add_parser("enable")
        enable_parser.add_argument("prompt", nargs="*")
        enable_parser.add_argument("--max-iterations", type=int, default=0)
        enable_parser.add_argument("--completion-promise", type=str, default=None)

        batch_parser = subparsers.add_parser("batch-init")
        batch_parser.add_argument("--tasks-file", required=True)
        batch_parser.add_argument("--max-iterations", type=int, default=20)
        batch_parser.add_argument("--completion-promise", type=str, default=None)

        subparsers.add_parser("status")
        subparsers.add_parser("iterate")
        subparsers.add_parser("disable")
        complete_parser = subparsers.add_parser("complete")
        complete_parser.add_argument("output", nargs="*")

        args = parser.parse_args()
        if not args.command:
            parser.print_help()
            return 0

        rm = _FallbackRalphMode()

        if args.command == "enable":
            prompt = " ".join(args.prompt) if args.prompt else ""
            rm.enable(prompt, max_iterations=args.max_iterations, completion_promise=args.completion_promise)
            print("Ralph Mode enabled")
            return 0
        if args.command == "batch-init":
            tasks = json.loads(Path(args.tasks_file).read_text(encoding="utf-8"))
            rm.init_batch(tasks, max_iterations=args.max_iterations, completion_promise=args.completion_promise)
            print("Ralph Mode batch enabled")
            return 0
        if args.command == "status":
            status = rm.status()
            if not status:
                print("INACTIVE")
                return 0
            print("ACTIVE")
            print(f"Iteration: {status.get('iteration', '?')}")
            return 0
        if args.command == "iterate":
            rm.iterate()
            print("Iteration advanced")
            return 0
        if args.command == "complete":
            output = " ".join(args.output) if args.output else sys.stdin.read()
            if rm.complete(output):
                print("Completion promise detected")
                return 0
            print("No completion promise found")
            return 1
        if args.command == "disable":
            rm.disable()
            print("Ralph Mode disabled")
            return 0
        return 1

    _main = _fallback_main


if __name__ == "__main__":
    sys.exit(_main())
