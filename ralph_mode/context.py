"""Advanced context manager for cross-iteration memory.

Builds rich, structured context that persists between iterations so the AI
model knows exactly what was already done, what changed, what failed, and
what remains.  The context is written to `.ralph-mode/context.md` and
injected into every Copilot CLI prompt.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .memory import MemoryStore
from .state import RalphMode


class ContextManager:
    """Advanced context manager for cross-iteration memory."""

    CONTEXT_FILE = "context.md"
    MEMORY_FILE = "memory.jsonl"
    PROGRESS_FILE = "progress.md"
    SUMMARY_FILE = "summary.md"

    # Limits to keep context within token budgets
    MAX_OUTPUT_LINES = 150
    MAX_DIFF_LINES = 80
    MAX_DIFF_STAT_LINES = 60
    MAX_GIT_LOG_ENTRIES = 10
    MAX_HISTORY_ENTRIES = 10
    MAX_FILE_PREVIEW_LINES = 40
    MAX_BLOCKERS = 10

    def __init__(self, ralph: RalphMode) -> None:
        self.ralph = ralph
        self.context_file = ralph.ralph_dir / self.CONTEXT_FILE
        self.memory_file = ralph.ralph_dir / self.MEMORY_FILE
        self.progress_file = ralph.ralph_dir / self.PROGRESS_FILE
        self.memory = MemoryStore(ralph)

    # ── helpers ──────────────────────────────────────────────

    @staticmethod
    def _run_cmd(cmd: str, cwd: Optional[Path] = None, max_lines: int = 200) -> str:
        """Run a shell command and return its stdout (trimmed)."""
        import subprocess

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15,
                cwd=str(cwd) if cwd else None,
            )
            lines = result.stdout.strip().splitlines()
            if len(lines) > max_lines:
                lines = lines[:max_lines] + [f"... ({len(lines) - max_lines} more lines)"]
            return "\n".join(lines)
        except Exception:
            return ""

    # ── git intelligence ────────────────────────────────────

    def git_status_short(self) -> str:
        """Return `git status --short`."""
        return self._run_cmd("git status --short", cwd=self.ralph.base_path, max_lines=60)

    def git_diff_stat(self) -> str:
        """Return `git diff --stat` (unstaged)."""
        return self._run_cmd("git diff --stat", cwd=self.ralph.base_path, max_lines=self.MAX_DIFF_STAT_LINES)

    def git_diff_staged_stat(self) -> str:
        """Return `git diff --cached --stat` (staged)."""
        return self._run_cmd("git diff --cached --stat", cwd=self.ralph.base_path, max_lines=self.MAX_DIFF_STAT_LINES)

    def git_diff_content(self) -> str:
        """Return actual diff content (truncated)."""
        return self._run_cmd("git diff --no-color", cwd=self.ralph.base_path, max_lines=self.MAX_DIFF_LINES)

    def git_log_recent(self) -> str:
        """Return last N commit messages."""
        return self._run_cmd(
            f"git log --oneline -n {self.MAX_GIT_LOG_ENTRIES}",
            cwd=self.ralph.base_path,
        )

    def git_changed_files_since_start(self) -> str:
        """Files changed since Ralph Mode started."""
        state = self.ralph.get_state() or {}
        started = state.get("started_at", "")
        if not started:
            return ""
        return self._run_cmd(
            f'git log --since="{started}" --name-only --pretty=format: | sort -u | head -50',
            cwd=self.ralph.base_path,
        )

    def git_files_currently_modified(self) -> list:
        """Get list of currently modified files (staged + unstaged)."""
        raw = self._run_cmd("git diff --name-only", cwd=self.ralph.base_path)
        staged = self._run_cmd("git diff --cached --name-only", cwd=self.ralph.base_path)
        untracked = self._run_cmd("git ls-files --others --exclude-standard", cwd=self.ralph.base_path)
        all_files: set = set()
        for chunk in [raw, staged, untracked]:
            for f in chunk.strip().splitlines():
                f = f.strip()
                if f:
                    all_files.add(f)
        return sorted(all_files)

    # ── output / history readers ────────────────────────────

    def last_output_tail(self) -> str:
        """Return tail of last iteration output."""
        output_file = self.ralph.ralph_dir / "output.txt"
        if not output_file.exists():
            return ""
        try:
            lines = output_file.read_text(encoding="utf-8", errors="replace").splitlines()
            tail = lines[-self.MAX_OUTPUT_LINES :] if len(lines) > self.MAX_OUTPUT_LINES else lines
            return "\n".join(tail)
        except Exception:
            return ""

    def recent_history(self) -> list:
        """Return last N history entries as dicts."""
        entries = self.ralph.get_history()
        return entries[-self.MAX_HISTORY_ENTRIES :]

    def history_summary(self) -> str:
        """Build a human-readable history summary."""
        entries = self.recent_history()
        if not entries:
            return "(no history yet)"
        lines = []
        for e in entries:
            ts = e.get("timestamp", "?")[:19]
            lines.append(
                f"  iter {e.get('iteration','?'):>3}  {e.get('status','?'):<18} {ts}  {e.get('notes','')[:60]}"
            )
        return "\n".join(lines)

    # ── memory (structured per-iteration notes) ─────────────

    def append_memory(self, entry: Dict[str, Any]) -> None:
        """Append a structured memory entry (one JSON line)."""
        self.ralph.ralph_dir.mkdir(parents=True, exist_ok=True)
        entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        with open(self.memory_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_memories(self, last_n: int = 20) -> list:
        """Read last N memory entries."""
        if not self.memory_file.exists():
            return []
        entries = []
        with open(self.memory_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return entries[-last_n:]

    def format_memories(self) -> str:
        """Format memories as readable text."""
        mems = self.read_memories()
        if not mems:
            return "(no iteration memories yet)"
        lines = []
        for m in mems:
            it = m.get("iteration", "?")
            action = m.get("action", "")
            files = ", ".join(m.get("files_changed", []))
            result = m.get("result", "")
            blockers = m.get("blockers", "")
            line = f"  [iter {it}] {action}"
            if files:
                line += f"  files: {files}"
            if result:
                line += f"  → {result}"
            if blockers:
                line += f"  ⚠ {blockers}"
            lines.append(line)
        return "\n".join(lines)

    # ── progress tracker ────────────────────────────────────

    def save_progress(self, summary: str) -> None:
        """Overwrite progress summary (cumulative, written by AI or loop)."""
        self.ralph.ralph_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file.write_text(summary, encoding="utf-8")

    def get_progress(self) -> str:
        """Read current progress summary."""
        if not self.progress_file.exists():
            return ""
        return self.progress_file.read_text(encoding="utf-8")

    # ── iteration summary (called after each iteration) ─────

    def save_iteration_summary(
        self,
        iteration: int,
        action: str = "",
        files_changed: Optional[list] = None,
        result: str = "",
        blockers: str = "",
    ) -> None:
        """Record what happened in this iteration for future reference."""
        # Auto-detect changed files from git if not provided
        if files_changed is None:
            raw = self._run_cmd("git diff --name-only", cwd=self.ralph.base_path)
            staged = self._run_cmd("git diff --cached --name-only", cwd=self.ralph.base_path)
            all_files = set((raw + "\n" + staged).strip().splitlines())
            files_changed = [f for f in sorted(all_files) if f]

        self.append_memory(
            {
                "iteration": iteration,
                "action": action,
                "files_changed": files_changed,
                "result": result,
                "blockers": blockers,
            }
        )

    # ── main context builder ────────────────────────────────

    def build_full_context(self) -> str:
        """Build the complete advanced context for the AI.

        This is the core method — it assembles everything the AI needs to
        understand where it is, what happened before, and what to do next.
        """
        state = self.ralph.get_state() or {}
        iteration = state.get("iteration", 1)
        max_iter = state.get("max_iterations", 0)
        promise = state.get("completion_promise", "")
        mode = state.get("mode", "single")
        prompt = self.ralph.get_prompt() or "(no task loaded)"

        header = f"# Ralph Mode — Iteration {iteration}"
        if max_iter > 0:
            header += f" / {max_iter}"

        sections = [header, ""]

        # ── 1. Task ──
        sections.append("## Task")
        sections.append(prompt)
        sections.append("")

        # ── 2. Iteration Memory ──
        memories = self.format_memories()
        if memories and memories != "(no iteration memories yet)":
            sections.append("## Iteration Memory (what happened before)")
            sections.append("```")
            sections.append(memories)
            sections.append("```")
            sections.append("")

        # ── 3. Cumulative Progress ──
        progress = self.get_progress()
        if progress:
            sections.append("## Progress So Far")
            sections.append(progress)
            sections.append("")

        # ── 4. Git State ──
        git_status = self.git_status_short()
        git_diff = self.git_diff_stat()
        git_log = self.git_log_recent()
        changed_since = self.git_changed_files_since_start()

        if git_status or git_diff or git_log:
            sections.append("## Repository State")
            if git_status:
                sections.append("### Working tree (git status --short)")
                sections.append("```")
                sections.append(git_status)
                sections.append("```")
            if git_diff:
                sections.append("### Uncommitted changes (git diff --stat)")
                sections.append("```")
                sections.append(git_diff)
                sections.append("```")
            if git_log:
                sections.append("### Recent commits")
                sections.append("```")
                sections.append(git_log)
                sections.append("```")
            if changed_since:
                sections.append("### Files touched since Ralph started")
                sections.append("```")
                sections.append(changed_since)
                sections.append("```")
            sections.append("")

        # ── 5. Actual diff content (truncated) ──
        diff_content = self.git_diff_content()
        if diff_content:
            sections.append("## Current Diff (truncated)")
            sections.append("```diff")
            sections.append(diff_content)
            sections.append("```")
            sections.append("")

        # ── 6. Last Iteration Output ──
        last_output = self.last_output_tail()
        if last_output and iteration > 1:
            sections.append("## Last Iteration Output (tail)")
            sections.append("```")
            sections.append(last_output)
            sections.append("```")
            sections.append("")

        # ── 7. History ──
        hist = self.history_summary()
        if hist and hist != "(no history yet)":
            sections.append("## History Log")
            sections.append("```")
            sections.append(hist)
            sections.append("```")
            sections.append("")

        # ── 8. Batch mode info ──
        if mode == "batch":
            task_idx = state.get("current_task_index", 0)
            task_total = state.get("tasks_total", 0)
            task_id = state.get("current_task_id", "?")
            task_title = state.get("current_task_title", "")
            sections.append("## Batch Mode")
            sections.append(f"Task {task_idx + 1} of {task_total}: **{task_id}** — {task_title}")
            sections.append("")

        # ── 9. Memory Bank (mem0-inspired long-term memory) ──
        try:
            memory_block = self.memory.format_for_context(query=prompt)
            if memory_block and memory_block.strip():
                sections.append("## Memory Bank (from previous iterations)")
                sections.append(memory_block)
                sections.append("")
        except Exception:
            pass  # Memory is optional; never block context generation

        # ── 9b. Files Already Changed ──
        try:
            modified = self.git_files_currently_modified()
            if modified and iteration > 1:
                sections.append("## Files Already Changed (do NOT redo these)")
                sections.append(
                    "These files have been modified in previous iterations. "
                    "Read them before editing. Do not recreate existing changes."
                )
                sections.append("```")
                sections.append("\n".join(modified[:40]))
                sections.append("```")
                sections.append("")
        except Exception:
            pass

        # ── 10. Rules ──
        sections.append("## Rules")
        sections.append(
            """
1. **Continue from where you left off** — read the Iteration Memory, Progress, and Memory Bank sections above.
2. **Do NOT restart the task** — only work on what remains.
3. **Make real file changes** visible in `git diff`.
4. **Update progress** — after making changes, briefly note what you did.
5. If a required file does not exist, document it as a blocker.
6. If the task is already satisfied (changes exist), verify and complete — don't redo.
7. Focus ONLY on files listed in the task scope.
8. **Use the Memory Bank** — it contains insights, patterns, and decisions from all previous iterations.
"""
        )

        # ── 10b. File Editing Best Practices ──
        sections.append("## File Editing Best Practices")
        sections.append(
            """
**BEFORE editing a file:**
1. Read the file (or the relevant section) first — understand what exists.
2. Check `git diff` to see if a previous iteration already made changes.
3. Search the Memory Bank for prior edits to the same file.

**WHEN editing a file:**
1. Use precise, targeted edits — replace only the lines that need to change.
2. Always include enough context (3+ surrounding lines) to anchor the edit.
3. Preserve whitespace, indentation, and coding style of the existing file.
4. Never guess at file contents — always read before editing.
5. If creating a new file, check if it already exists first.

**AFTER editing a file:**
1. Verify the edit by reading the modified section back.
2. Run any relevant tests or linters if available.
3. Record what you changed in your progress notes.
4. If an edit fails, read the file again to get the current content and retry.

**COMMON MISTAKES to avoid:**
- Editing a file without reading it first (leads to stale content errors).
- Remaking changes that already exist from a previous iteration.
- Using placeholder text like `...existing code...` instead of actual content.
- Trying to edit too many lines at once — split into smaller edits.
"""
        )

        # ── 11. Completion ──
        if promise:
            sections.append("## Completion")
            sections.append(f"When ALL acceptance criteria are met, output exactly:")
            sections.append(f"```\n<promise>{promise}</promise>\n```")
            sections.append("⚠️ ONLY when genuinely complete. Never lie. Document blockers instead.")
            sections.append("")

        # ── 12. Auto-agents ──
        if state.get("auto_agents"):
            sections.append("## Auto-Agents (enabled)")
            sections.append("Create sub-agents in `.github/agents/` and invoke with `@agent-name <task>`.")
            sections.append("")

        return "\n".join(sections)

    def write_context_file(self) -> Path:
        """Write the full context to `.ralph-mode/context.md` for reference."""
        content = self.build_full_context()
        self.ralph.ralph_dir.mkdir(parents=True, exist_ok=True)
        self.context_file.write_text(content, encoding="utf-8")
        return self.context_file

    def write_summary_report(
        self,
        *,
        exit_code: int,
        verification: Optional[List[Dict[str, Any]]] = None,
    ) -> Path:
        """Write a structured summary report for the latest iteration."""
        state = self.ralph.get_state() or {}
        iteration = state.get("iteration", 1)
        prompt = self.ralph.get_prompt() or "(no task loaded)"
        git_status = self.git_status_short()
        diff_stat = self.git_diff_stat()
        last_output = self.last_output_tail()

        lines = [
            f"# Iteration Summary — {iteration}",
            "",
            f"**Timestamp:** {datetime.now(timezone.utc).isoformat()}",
            f"**Exit Code:** {exit_code}",
            "",
            "## Task",
            prompt,
            "",
        ]

        if git_status:
            lines.extend(["## Git Status", "```", git_status, "```", ""])

        if diff_stat:
            lines.extend(["## Diff Stat", "```", diff_stat, "```", ""])

        if verification:
            lines.append("## Verification Results")
            for result in verification:
                status = "✅" if result.get("ok") else "❌"
                lines.append(f"- {status} `{result.get('command')}`")
                if result.get("stdout"):
                    lines.extend(
                        [
                            "  <details>",
                            "  <summary>stdout</summary>",
                            "",
                            "  ```",
                            result["stdout"],
                            "  ```",
                            "  </details>",
                        ]
                    )
                if result.get("stderr"):
                    lines.extend(
                        [
                            "  <details>",
                            "  <summary>stderr</summary>",
                            "",
                            "  ```",
                            result["stderr"],
                            "  ```",
                            "  </details>",
                        ]
                    )
            lines.append("")

        if last_output:
            lines.extend(["## Last Output (tail)", "```", last_output, "```", ""])

        summary_path = self.ralph.ralph_dir / self.SUMMARY_FILE
        self.ralph.ralph_dir.mkdir(parents=True, exist_ok=True)
        summary_path.write_text("\n".join(lines), encoding="utf-8")
        return summary_path
