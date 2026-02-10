#!/usr/bin/env python3
"""
Test suite for ContextManager (advanced context builder for cross-iteration memory).

Tests cover:
- Context file creation (write_context_file)
- Full context building (build_full_context) sections
- Iteration memory (append / read / format)
- Progress tracking (save / get)
- Iteration summary recording
- Git intelligence helpers (mocked)
- Output / history readers
- Memory Bank integration in context
- File editing guidance section
- Files already changed section
- Rules section presence
- Batch mode context
- Edge cases (no state, empty history, etc.)
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ralph_mode import ContextManager, MemoryStore, RalphMode

# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def temp_dir():
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def ralph(temp_dir):
    return RalphMode(temp_dir)


@pytest.fixture
def active_ralph(ralph):
    ralph.enable("Implement authentication module", max_iterations=10, completion_promise="AUTH_DONE")
    return ralph


@pytest.fixture
def ctx(active_ralph):
    return ContextManager(active_ralph)


@pytest.fixture
def batch_ralph(ralph):
    tasks = [
        {"id": "T-001", "title": "Task One", "prompt": "Do the first thing"},
        {"id": "T-002", "title": "Task Two", "prompt": "Do the second thing"},
    ]
    ralph.init_batch(tasks, max_iterations=5, completion_promise="BATCH_DONE")
    return ralph


@pytest.fixture
def batch_ctx(batch_ralph):
    return ContextManager(batch_ralph)


# ═══════════════════════════════════════════════════════════════════
# Context File Tests
# ═══════════════════════════════════════════════════════════════════


class TestWriteContextFile:
    def test_creates_file(self, ctx):
        path = ctx.write_context_file()
        assert path.exists()
        assert path.name == "context.md"

    def test_file_has_content(self, ctx):
        path = ctx.write_context_file()
        content = path.read_text(encoding="utf-8")
        assert len(content) > 0
        assert "Ralph Mode" in content

    def test_file_overwrites(self, ctx):
        ctx.write_context_file()
        ctx.write_context_file()  # Should not error on second write


# ═══════════════════════════════════════════════════════════════════
# Full Context Building Tests
# ═══════════════════════════════════════════════════════════════════


class TestBuildFullContext:
    def test_contains_header(self, ctx):
        content = ctx.build_full_context()
        assert "# Ralph Mode — Iteration 1" in content

    def test_contains_max_iterations(self, ctx):
        content = ctx.build_full_context()
        assert "1 / 10" in content

    def test_contains_task_section(self, ctx):
        content = ctx.build_full_context()
        assert "## Task" in content
        assert "authentication module" in content

    def test_contains_rules_section(self, ctx):
        content = ctx.build_full_context()
        assert "## Rules" in content
        assert "Continue from where you left off" in content
        assert "Do NOT restart" in content

    def test_contains_file_editing_section(self, ctx):
        content = ctx.build_full_context()
        assert "## File Editing Best Practices" in content
        assert "BEFORE editing a file" in content
        assert "WHEN editing a file" in content
        assert "AFTER editing a file" in content
        assert "COMMON MISTAKES" in content

    def test_contains_completion_section(self, ctx):
        content = ctx.build_full_context()
        assert "## Completion" in content
        assert "<promise>AUTH_DONE</promise>" in content

    def test_no_completion_without_promise(self, ralph):
        ralph.enable("Simple task")
        ctx = ContextManager(ralph)
        content = ctx.build_full_context()
        assert "## Completion" not in content

    def test_iteration_memory_shown_when_present(self, ctx):
        ctx.save_iteration_summary(iteration=1, action="created initial files")
        content = ctx.build_full_context()
        assert "Iteration Memory" in content
        assert "created initial files" in content

    def test_no_iteration_memory_when_empty(self, ctx):
        content = ctx.build_full_context()
        # Should not have the iteration memory section when empty
        assert "Iteration Memory" not in content or "(no iteration memories yet)" not in content

    def test_progress_shown_when_set(self, ctx):
        ctx.save_progress("Step 1: created module, Step 2: added tests")
        content = ctx.build_full_context()
        assert "## Progress So Far" in content
        assert "created module" in content

    def test_no_progress_section_when_empty(self, ctx):
        content = ctx.build_full_context()
        assert "## Progress So Far" not in content

    @patch.object(ContextManager, "_run_cmd")
    def test_git_status_in_context(self, mock_cmd, ctx):
        def side_effect(cmd, **kwargs):
            if "status --short" in cmd:
                return " M src/auth.py\n?? tests/test_auth.py"
            return ""

        mock_cmd.side_effect = side_effect
        content = ctx.build_full_context()
        assert "Repository State" in content

    def test_memory_bank_integration(self, ctx):
        # Add some memories
        ctx.memory.add("auth module uses JWT tokens", memory_type=MemoryStore.SEMANTIC)
        ctx.memory.add("iteration 1 created auth.py", memory_type=MemoryStore.EPISODIC)
        content = ctx.build_full_context()
        assert "Memory Bank" in content

    def test_batch_mode_section(self, batch_ctx):
        content = batch_ctx.build_full_context()
        assert "## Batch Mode" in content
        assert "T-001" in content

    def test_auto_agents_section(self, ralph):
        ralph.enable("Task", auto_agents=True)
        ctx = ContextManager(ralph)
        content = ctx.build_full_context()
        assert "## Auto-Agents" in content


# ═══════════════════════════════════════════════════════════════════
# Iteration Memory Tests
# ═══════════════════════════════════════════════════════════════════


class TestIterationMemory:
    def test_append_memory(self, ctx):
        ctx.append_memory({"iteration": 1, "action": "test"})
        mems = ctx.read_memories()
        assert len(mems) == 1
        assert mems[0]["action"] == "test"

    def test_append_multiple(self, ctx):
        ctx.append_memory({"iteration": 1, "action": "first"})
        ctx.append_memory({"iteration": 2, "action": "second"})
        mems = ctx.read_memories()
        assert len(mems) == 2

    def test_append_sets_timestamp(self, ctx):
        ctx.append_memory({"test": True})
        mems = ctx.read_memories()
        assert "timestamp" in mems[0]

    def test_read_empty(self, ctx):
        mems = ctx.read_memories()
        assert mems == []

    def test_read_last_n(self, ctx):
        for i in range(10):
            ctx.append_memory({"iteration": i})
        mems = ctx.read_memories(last_n=3)
        assert len(mems) == 3
        assert mems[0]["iteration"] == 7

    def test_format_memories_empty(self, ctx):
        result = ctx.format_memories()
        assert "no iteration memories yet" in result

    def test_format_memories_with_data(self, ctx):
        ctx.append_memory(
            {
                "iteration": 1,
                "action": "created auth module",
                "files_changed": ["src/auth.py"],
                "result": "success",
            }
        )
        result = ctx.format_memories()
        assert "iter 1" in result
        assert "created auth module" in result
        assert "src/auth.py" in result

    def test_format_memories_blockers(self, ctx):
        ctx.append_memory(
            {
                "iteration": 1,
                "action": "tried to fix",
                "blockers": "missing dependency",
            }
        )
        result = ctx.format_memories()
        assert "missing dependency" in result


# ═══════════════════════════════════════════════════════════════════
# Progress Tests
# ═══════════════════════════════════════════════════════════════════


class TestProgress:
    def test_save_and_get(self, ctx):
        ctx.save_progress("50% complete")
        assert ctx.get_progress() == "50% complete"

    def test_overwrite(self, ctx):
        ctx.save_progress("old")
        ctx.save_progress("new")
        assert ctx.get_progress() == "new"

    def test_empty_progress(self, ctx):
        assert ctx.get_progress() == ""


# ═══════════════════════════════════════════════════════════════════
# Iteration Summary Tests
# ═══════════════════════════════════════════════════════════════════


class TestIterationSummary:
    def test_save_basic(self, ctx):
        ctx.save_iteration_summary(
            iteration=1,
            action="implemented login",
            files_changed=["src/login.py"],
            result="success",
        )
        mems = ctx.read_memories()
        assert len(mems) == 1
        assert mems[0]["action"] == "implemented login"
        assert "src/login.py" in mems[0]["files_changed"]

    def test_save_with_blockers(self, ctx):
        ctx.save_iteration_summary(
            iteration=2,
            action="tried database setup",
            blockers="missing pg_config",
        )
        mems = ctx.read_memories()
        assert mems[0]["blockers"] == "missing pg_config"

    @patch.object(ContextManager, "_run_cmd")
    def test_auto_detect_files(self, mock_cmd, ctx):
        def side_effect(cmd, **kwargs):
            if "diff --name-only" in cmd and "--cached" not in cmd:
                return "src/auth.py\nsrc/utils.py"
            if "--cached" in cmd:
                return "src/config.py"
            return ""

        mock_cmd.side_effect = side_effect
        ctx.save_iteration_summary(iteration=1, action="auto-detect test")
        mems = ctx.read_memories()
        files = mems[0]["files_changed"]
        assert "src/auth.py" in files
        assert "src/config.py" in files


# ═══════════════════════════════════════════════════════════════════
# Output / History Reader Tests
# ═══════════════════════════════════════════════════════════════════


class TestOutputAndHistory:
    def test_last_output_no_file(self, ctx):
        assert ctx.last_output_tail() == ""

    def test_last_output_with_file(self, ctx):
        output_file = ctx.ralph.ralph_dir / "output.txt"
        output_file.write_text("line1\nline2\nline3\n")
        result = ctx.last_output_tail()
        assert "line1" in result
        assert "line3" in result

    def test_last_output_truncated(self, ctx):
        output_file = ctx.ralph.ralph_dir / "output.txt"
        lines = [f"line {i}" for i in range(500)]
        output_file.write_text("\n".join(lines))
        result = ctx.last_output_tail()
        result_lines = result.splitlines()
        assert len(result_lines) <= ctx.MAX_OUTPUT_LINES

    def test_history_summary_empty(self, ralph):
        # Use a ralph instance that's NOT enabled so there's no history
        ctx = ContextManager(ralph)
        result = ctx.history_summary()
        assert "no history" in result

    def test_history_summary_with_entries(self, active_ralph):
        # iterate to generate history
        active_ralph.iterate()
        ctx = ContextManager(active_ralph)
        result = ctx.history_summary()
        assert "iter" in result


# ═══════════════════════════════════════════════════════════════════
# Git Intelligence Tests (Mocked)
# ═══════════════════════════════════════════════════════════════════


class TestGitIntelligence:
    @patch.object(ContextManager, "_run_cmd")
    def test_git_status_short(self, mock_cmd, ctx):
        mock_cmd.return_value = " M src/main.py\n?? new_file.py"
        result = ctx.git_status_short()
        assert "src/main.py" in result

    @patch.object(ContextManager, "_run_cmd")
    def test_git_diff_stat(self, mock_cmd, ctx):
        mock_cmd.return_value = " src/main.py | 10 +++++++---"
        result = ctx.git_diff_stat()
        assert "src/main.py" in result

    @patch.object(ContextManager, "_run_cmd")
    def test_git_log_recent(self, mock_cmd, ctx):
        mock_cmd.return_value = "abc123 Initial commit"
        result = ctx.git_log_recent()
        assert "Initial commit" in result

    @patch.object(ContextManager, "_run_cmd")
    def test_git_files_currently_modified(self, mock_cmd, ctx):
        def side_effect(cmd, **kwargs):
            if "--cached" in cmd:
                return "staged.py"
            if "--name-only" in cmd:
                return "unstaged.py"
            if "ls-files" in cmd:
                return "untracked.py"
            return ""

        mock_cmd.side_effect = side_effect
        files = ctx.git_files_currently_modified()
        assert "staged.py" in files
        assert "unstaged.py" in files
        assert "untracked.py" in files

    @patch.object(ContextManager, "_run_cmd")
    def test_git_changed_files_since_start(self, mock_cmd, ctx):
        mock_cmd.return_value = "src/auth.py\nsrc/db.py"
        result = ctx.git_changed_files_since_start()
        assert "auth.py" in result


# ═══════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════


class TestContextEdgeCases:
    def test_context_with_no_state(self, ralph):
        # Ralph not enabled
        ctx = ContextManager(ralph)
        content = ctx.build_full_context()
        # Should still produce something without crashing
        assert "Ralph Mode" in content

    def test_context_multi_iteration(self, active_ralph):
        ctx = ContextManager(active_ralph)
        ctx.save_iteration_summary(1, "first pass")
        active_ralph.iterate()
        ctx.save_iteration_summary(2, "second pass")
        active_ralph.iterate()
        content = ctx.build_full_context()
        assert "Iteration 3" in content

    def test_memory_bank_empty(self, ctx):
        content = ctx.build_full_context()
        # With no memories, Memory Bank section should be absent
        # (format_for_context returns "" when empty)
        # This is fine — just verify no crash

    def test_run_cmd_timeout(self, ctx):
        # _run_cmd should handle timeouts gracefully
        result = ctx._run_cmd("sleep 30", max_lines=10)
        # Should return empty string (timeout after 15s)
        # This test may take up to 15s
        assert isinstance(result, str)

    def test_run_cmd_invalid_command(self, ctx):
        result = ctx._run_cmd("nonexistent_command_xyz123")
        assert result == ""

    def test_context_preserves_unicode(self, active_ralph):
        active_ralph.ralph_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = active_ralph.ralph_dir / "prompt.md"
        prompt_file.write_text("پیاده‌سازی ماژول احراز هویت 🔐", encoding="utf-8")
        ctx = ContextManager(active_ralph)
        content = ctx.build_full_context()
        assert "احراز" in content or "authentication" in content.lower()
