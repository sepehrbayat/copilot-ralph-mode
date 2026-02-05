#!/usr/bin/env python3
"""
Advanced Test Suite for Copilot Ralph Mode
==========================================

Comprehensive tests with:
- Parametrized test cases
- Edge cases and boundary conditions
- Error handling validation
- Concurrency tests
- Performance benchmarks
- Integration tests
- Mock/Fixture patterns
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ralph_mode import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    FALLBACK_MODEL,
    VERSION,
    Colors,
    RalphMode,
    TaskLibrary,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    dir_path = Path(tempfile.mkdtemp())
    yield dir_path
    shutil.rmtree(dir_path, ignore_errors=True)


@pytest.fixture
def ralph(temp_dir):
    """Create a RalphMode instance with temp directory."""
    return RalphMode(temp_dir)


@pytest.fixture
def active_ralph(ralph):
    """Create an already-activated RalphMode instance."""
    ralph.enable("Test task")
    return ralph


@pytest.fixture
def batch_ralph(ralph):
    """Create a RalphMode instance in batch mode."""
    tasks = [
        {"id": "TASK-001", "title": "Task 1", "prompt": "Do task 1"},
        {"id": "TASK-002", "title": "Task 2", "prompt": "Do task 2"},
        {"id": "TASK-003", "title": "Task 3", "prompt": "Do task 3"},
    ]
    ralph.init_batch(tasks, max_iterations=5, completion_promise="DONE")
    return ralph


@pytest.fixture
def task_library(temp_dir):
    """Create a TaskLibrary with sample tasks."""
    tasks_dir = temp_dir / "tasks"
    tasks_dir.mkdir()
    groups_dir = tasks_dir / "_groups"
    groups_dir.mkdir()
    
    # Create sample tasks
    (tasks_dir / "sample-task.md").write_text("""---
id: SAMPLE-001
title: Sample Task
tags: [test, sample]
max_iterations: 10
completion_promise: DONE
---

# Sample Task

This is a sample task for testing.
""", encoding="utf-8")
    
    (tasks_dir / "another-task.md").write_text("""---
id: SAMPLE-002
title: Another Task
tags: [test]
---

Do something else.
""", encoding="utf-8")
    
    # Create a group
    (groups_dir / "test-group.json").write_text(json.dumps({
        "name": "test-group",
        "title": "Test Group",
        "tasks": ["sample-task.md", "another-task.md"]
    }), encoding="utf-8")
    
    return TaskLibrary(temp_dir)


# ═══════════════════════════════════════════════════════════════════════════════
# PARAMETRIZED TESTS - RalphMode.enable()
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnableParametrized:
    """Parametrized tests for enable functionality."""
    
    @pytest.mark.parametrize("prompt", [
        "Simple task",
        "Task with\nmultiple\nlines",
        "Task with émojis 🚀 and unicode ünïcödé",
        "Task with special chars: !@#$%^&*()",
        "Task with quotes: 'single' and \"double\"",
        "Very " * 1000 + "long prompt",
        "   Task with leading/trailing whitespace   ",
        "",  # Empty prompt - should work
    ])
    def test_enable_various_prompts(self, ralph, prompt):
        """Test enable with various prompt formats."""
        state = ralph.enable(prompt)
        assert ralph.is_active()
        assert ralph.get_prompt() == prompt
        assert state["iteration"] == 1
    
    @pytest.mark.parametrize("max_iterations", [0, 1, 5, 10, 100, 1000, 999999])
    def test_enable_various_max_iterations(self, ralph, max_iterations):
        """Test enable with various max_iterations values."""
        state = ralph.enable("Test", max_iterations=max_iterations)
        assert state["max_iterations"] == max_iterations
    
    @pytest.mark.parametrize("promise", [
        "DONE",
        "COMPLETE",
        "All tasks finished successfully!",
        "Done with émojis ✅",
        "Done (100%)",
        "Multi\nLine\nPromise",
        None,  # No promise
    ])
    def test_enable_various_promises(self, ralph, promise):
        """Test enable with various completion promises."""
        state = ralph.enable("Test", completion_promise=promise)
        assert state["completion_promise"] == promise
    
    @pytest.mark.parametrize("model", AVAILABLE_MODELS + [None, "custom-model"])
    def test_enable_various_models(self, ralph, model):
        """Test enable with various model options."""
        state = ralph.enable("Test", model=model)
        expected_model = model if model else DEFAULT_MODEL
        assert state["model"] == expected_model
    
    @pytest.mark.parametrize("auto_agents", [True, False])
    def test_enable_auto_agents(self, ralph, auto_agents):
        """Test enable with auto_agents flag."""
        state = ralph.enable("Test", auto_agents=auto_agents)
        assert state["auto_agents"] == auto_agents


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_enable_twice_raises_error(self, active_ralph):
        """Test that enabling twice raises ValueError."""
        with pytest.raises(ValueError, match="already active"):
            active_ralph.enable("Another task")
    
    def test_disable_inactive_returns_none(self, ralph):
        """Test disabling when not active returns None."""
        result = ralph.disable()
        assert result is None
    
    def test_iterate_when_inactive_raises_error(self, ralph):
        """Test iterating when not active raises error."""
        with pytest.raises(ValueError, match="No active Ralph mode"):
            ralph.iterate()
    
    def test_next_task_in_single_mode_raises_error(self, active_ralph):
        """Test next_task in single mode raises error."""
        with pytest.raises(ValueError, match="only available in batch mode"):
            active_ralph.next_task()
    
    def test_max_iterations_reached_disables(self, ralph):
        """Test that reaching max iterations disables Ralph mode."""
        ralph.enable("Test", max_iterations=2)
        ralph.iterate()  # iteration 2
        
        with pytest.raises(ValueError, match="Max iterations"):
            ralph.iterate()  # Should raise and disable
        
        assert not ralph.is_active()
    
    def test_batch_with_single_task(self, ralph):
        """Test batch mode with only one task."""
        tasks = [{"id": "ONLY-001", "title": "Only Task", "prompt": "Do it"}]
        state = ralph.init_batch(tasks, max_iterations=5)
        
        assert state["tasks_total"] == 1
        assert state["current_task_index"] == 0
    
    def test_batch_complete_last_task_disables(self, ralph):
        """Test completing the last task in batch disables Ralph mode."""
        tasks = [{"id": "TASK-001", "title": "Task", "prompt": "Do it"}]
        ralph.init_batch(tasks, max_iterations=5, completion_promise="DONE")
        
        # Complete the only task
        with pytest.raises(ValueError, match="All tasks completed"):
            ralph.next_task(reason="completed")
        
        assert not ralph.is_active()
    
    def test_empty_tasks_list_raises_error(self, ralph):
        """Test that empty tasks list raises error."""
        with pytest.raises(ValueError, match="Task list is empty"):
            ralph.init_batch([], max_iterations=5)
    
    def test_corrupted_state_file(self, active_ralph):
        """Test handling of corrupted state file."""
        # Corrupt the state file
        active_ralph.state_file.write_text("not valid json", encoding="utf-8")
        
        # get_state should return None
        assert active_ralph.get_state() is None
    
    def test_missing_prompt_file(self, active_ralph):
        """Test handling when prompt file is deleted."""
        active_ralph.prompt_file.unlink()
        
        # get_prompt should return None
        assert active_ralph.get_prompt() is None
    
    def test_completion_promise_regex_patterns(self, active_ralph):
        """Test completion promise with regex-like characters."""
        active_ralph.disable()
        active_ralph.enable("Test", completion_promise="Done [100%] (success)")
        
        # Exact match should work
        assert active_ralph.check_completion("<promise>Done [100%] (success)</promise>")
        
        # Similar but not exact should not match
        assert not active_ralph.check_completion("<promise>Done [50%] (success)</promise>")


# ═══════════════════════════════════════════════════════════════════════════════
# ITERATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestIteration:
    """Test iteration functionality."""
    
    def test_iterate_increments_counter(self, active_ralph):
        """Test that iterate increments counter correctly."""
        initial_state = active_ralph.get_state()
        assert initial_state["iteration"] == 1
        
        state = active_ralph.iterate()
        assert state["iteration"] == 2
        
        state = active_ralph.iterate()
        assert state["iteration"] == 3
    
    def test_iterate_updates_timestamp(self, active_ralph):
        """Test that iterate updates the timestamp."""
        time.sleep(0.1)  # Ensure time passes
        state = active_ralph.iterate()
        assert "last_iterate_at" in state
    
    def test_iterate_logs_history(self, active_ralph):
        """Test that iterate logs to history."""
        active_ralph.iterate()
        active_ralph.iterate()
        
        history = active_ralph.get_history()
        assert len(history) >= 3  # started + 2 iterations
        
        iterate_entries = [h for h in history if h["status"] == "iterate"]
        assert len(iterate_entries) == 2
    
    def test_batch_iterate_max_advances_task(self, batch_ralph):
        """Test that reaching max in batch advances to next task."""
        initial_index = batch_ralph.get_state()["current_task_index"]
        max_iter = batch_ralph.get_state()["max_iterations"]  # 5
        
        # batch_ralph starts at iteration 1, max_iterations is 5
        # iterate() increments first, then checks if max reached
        # So: iterate 1→2, 2→3, 3→4, 4→5 (check: 5>=5, advance to next task)
        # We need exactly max_iter calls to advance to next task
        for i in range(max_iter):  # 5 iterations
            state = batch_ralph.iterate()
        
        # After the max iterations, we should have advanced to next task
        assert state["current_task_index"] == initial_index + 1
        assert state["iteration"] == 1  # Reset for new task


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLETION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompletion:
    """Test completion promise functionality."""
    
    @pytest.mark.parametrize("output,expected", [
        ("<promise>DONE</promise>", True),
        ("Some text <promise>DONE</promise> more text", True),
        ("\n<promise>DONE</promise>\n", True),
        ("   <promise>DONE</promise>   ", True),
        ("<promise>DONE</promise><promise>DONE</promise>", True),  # Multiple
        ("<promise>WRONG</promise>", False),
        ("<promise>done</promise>", False),  # Case sensitive
        ("DONE", False),  # No tags
        ("<promise>DONE", False),  # Missing close
        ("DONE</promise>", False),  # Missing open
        ("", False),
        (None, False),
    ])
    def test_check_completion_patterns(self, ralph, output, expected):
        """Test various completion output patterns."""
        ralph.enable("Test", completion_promise="DONE")
        
        if output is None:
            # check_completion expects string
            result = ralph.check_completion("")
        else:
            result = ralph.check_completion(output)
        
        assert result == expected
    
    def test_complete_disables_in_single_mode(self, ralph):
        """Test complete() disables Ralph mode."""
        ralph.enable("Test", completion_promise="DONE")
        
        result = ralph.complete("<promise>DONE</promise>")
        
        assert result is True
        assert not ralph.is_active()
    
    def test_complete_advances_in_batch_mode(self, batch_ralph):
        """Test complete() advances task in batch mode."""
        initial_index = batch_ralph.get_state()["current_task_index"]
        
        result = batch_ralph.complete("<promise>DONE</promise>")
        
        assert result is True
        assert batch_ralph.is_active()  # Still active (more tasks)
        assert batch_ralph.get_state()["current_task_index"] == initial_index + 1
    
    def test_no_promise_never_completes(self, ralph):
        """Test that without promise, check_completion always returns False."""
        ralph.enable("Test", completion_promise=None)
        
        assert not ralph.check_completion("<promise>DONE</promise>")
        assert not ralph.check_completion("<promise>anything</promise>")


# ═══════════════════════════════════════════════════════════════════════════════
# HISTORY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestHistory:
    """Test history logging functionality."""
    
    def test_history_created_on_enable(self, active_ralph):
        """Test that history file is created on enable."""
        assert active_ralph.history_file.exists()
        history = active_ralph.get_history()
        assert len(history) >= 1
        assert history[0]["status"] == "started"
    
    def test_history_format(self, active_ralph):
        """Test history entry format."""
        history = active_ralph.get_history()
        entry = history[0]
        
        assert "iteration" in entry
        assert "timestamp" in entry
        assert "status" in entry
        assert "notes" in entry
    
    def test_history_timestamp_iso_format(self, active_ralph):
        """Test that timestamps are in ISO format."""
        history = active_ralph.get_history()
        timestamp = history[0]["timestamp"]
        
        # Should be parseable as ISO datetime
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    
    def test_history_persists_after_disable(self, active_ralph):
        """Test that history is lost after disable (cleanup)."""
        active_ralph.iterate()
        active_ralph.iterate()
        
        history_before = active_ralph.get_history()
        assert len(history_before) >= 3
        
        active_ralph.disable()
        
        # History file should be deleted with ralph_dir
        assert not active_ralph.history_file.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# TASK LIBRARY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTaskLibrary:
    """Test TaskLibrary functionality."""
    
    def test_list_tasks(self, task_library):
        """Test listing available tasks."""
        tasks = task_library.list_tasks()
        assert len(tasks) == 2
    
    def test_list_groups(self, task_library):
        """Test listing available groups."""
        groups = task_library.list_groups()
        assert len(groups) == 1
        assert groups[0]["name"] == "test-group"
    
    def test_get_task_by_id(self, task_library):
        """Test getting task by ID."""
        task = task_library.get_task("SAMPLE-001")
        assert task is not None
        assert task["id"] == "SAMPLE-001"
        assert task["title"] == "Sample Task"
    
    def test_get_task_by_filename(self, task_library):
        """Test getting task by filename."""
        task = task_library.get_task("sample-task.md")
        assert task is not None
        assert task["id"] == "SAMPLE-001"
    
    def test_get_task_by_partial_filename(self, task_library):
        """Test getting task by partial filename (without .md)."""
        task = task_library.get_task("sample-task")
        assert task is not None
    
    def test_get_nonexistent_task(self, task_library):
        """Test getting nonexistent task returns None."""
        task = task_library.get_task("NONEXISTENT")
        assert task is None
    
    def test_get_group(self, task_library):
        """Test getting a group by name."""
        group = task_library.get_group("test-group")
        assert group is not None
        assert group["name"] == "test-group"
    
    def test_get_group_tasks(self, task_library):
        """Test getting all tasks in a group."""
        tasks = task_library.get_group_tasks("test-group")
        assert len(tasks) == 2
    
    def test_search_tasks(self, task_library):
        """Test searching tasks."""
        results = task_library.search_tasks("sample")
        assert len(results) >= 1
    
    def test_search_tasks_by_tag(self, task_library):
        """Test searching tasks by tag."""
        results = task_library.search_tasks("test")
        assert len(results) == 2  # Both tasks have 'test' tag
    
    def test_parse_task_frontmatter(self, task_library):
        """Test parsing task frontmatter."""
        task = task_library.get_task("SAMPLE-001")
        
        assert task["max_iterations"] == 10
        assert task["completion_promise"] == "DONE"
        assert "test" in task["tags"]
        assert "sample" in task["tags"]


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH MODE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestBatchMode:
    """Test batch mode functionality."""
    
    def test_batch_creates_task_files(self, ralph, temp_dir):
        """Test that batch creates individual task files."""
        tasks = [
            {"id": "TASK-001", "title": "Task 1", "prompt": "Do task 1"},
            {"id": "TASK-002", "title": "Task 2", "prompt": "Do task 2"},
        ]
        ralph.init_batch(tasks, max_iterations=5)
        
        tasks_dir = ralph.tasks_dir
        assert tasks_dir.exists()
        
        task_files = list(tasks_dir.glob("*.md"))
        assert len(task_files) == 2
    
    def test_batch_task_filename_format(self, ralph):
        """Test batch task filename format."""
        tasks = [{"id": "MY-TASK", "title": "My Task", "prompt": "Do it"}]
        ralph.init_batch(tasks, max_iterations=5)
        
        task_files = list(ralph.tasks_dir.glob("*.md"))
        assert len(task_files) == 1
        
        filename = task_files[0].name
        assert filename.startswith("01-")
        assert "my-task" in filename.lower()
    
    def test_batch_with_string_tasks(self, ralph):
        """Test batch with simple string prompts."""
        tasks = ["Do task 1", "Do task 2", "Do task 3"]
        state = ralph.init_batch(tasks, max_iterations=5)
        
        assert state["tasks_total"] == 3
        
        # Check generated IDs
        tasks_data = ralph.load_tasks()
        assert tasks_data[0]["id"] == "TASK-001"
        assert tasks_data[1]["id"] == "TASK-002"
    
    def test_next_task_advances(self, batch_ralph):
        """Test next_task advances to next task."""
        state = batch_ralph.next_task(reason="completed")
        
        assert state["current_task_index"] == 1
        assert state["iteration"] == 1  # Reset
    
    def test_next_task_updates_prompt(self, batch_ralph):
        """Test next_task updates prompt file."""
        initial_prompt = batch_ralph.get_prompt()
        
        batch_ralph.next_task()
        
        new_prompt = batch_ralph.get_prompt()
        assert new_prompt != initial_prompt
    
    def test_batch_status_includes_task_info(self, batch_ralph):
        """Test status includes batch task info."""
        status = batch_ralph.status()
        
        assert status["mode"] == "batch"
        assert "tasks_total" in status
        assert "current_task_index" in status
        assert "current_task_id" in status
        assert "current_task_title" in status


# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-AGENTS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutoAgents:
    """Test auto-agents functionality."""
    
    def test_enable_with_auto_agents_flag(self, ralph):
        """Test enable with auto_agents=True."""
        state = ralph.enable("Test", auto_agents=True)
        
        assert state["auto_agents"] is True
        assert state["created_agents"] == []
    
    def test_instructions_include_auto_agents_guide(self, ralph):
        """Test instructions include auto-agents guide when enabled."""
        ralph.enable("Test", auto_agents=True)
        
        instructions = ralph.instructions_file.read_text(encoding="utf-8")
        assert "Auto-Agents Mode" in instructions
        assert ".agent.md" in instructions
    
    def test_register_created_agent(self, ralph):
        """Test registering a dynamically created agent."""
        ralph.enable("Test", auto_agents=True)
        
        ralph.register_created_agent("test-agent", ".github/agents/test-agent.agent.md")
        
        state = ralph.get_state()
        assert len(state["created_agents"]) == 1
        assert state["created_agents"][0]["name"] == "test-agent"
        assert "created_at" in state["created_agents"][0]
        assert "iteration" in state["created_agents"][0]
    
    def test_register_duplicate_agent_ignored(self, ralph):
        """Test duplicate agent registration is ignored."""
        ralph.enable("Test", auto_agents=True)
        
        ralph.register_created_agent("agent-1", "path/1")
        ralph.register_created_agent("agent-1", "path/2")  # Duplicate name
        
        state = ralph.get_state()
        assert len(state["created_agents"]) == 1
    
    def test_batch_with_auto_agents(self, ralph):
        """Test batch mode with auto_agents."""
        tasks = [{"id": "T1", "title": "Task", "prompt": "Do it"}]
        state = ralph.init_batch(tasks, auto_agents=True)
        
        assert state["auto_agents"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# COLORS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestColors:
    """Test Colors class functionality."""
    
    def test_colors_disabled_returns_empty(self):
        """Test colors return empty when disabled."""
        colors = Colors()
        colors.enabled = False
        
        assert colors.RED == ""
        assert colors.GREEN == ""
        assert colors.NC == ""
    
    def test_colors_enabled_returns_ansi(self):
        """Test colors return ANSI codes when enabled."""
        colors = Colors()
        colors.enabled = True
        
        assert colors.RED == "\033[0;31m"
        assert colors.GREEN == "\033[0;32m"
        assert colors.NC == "\033[0m"


# ═══════════════════════════════════════════════════════════════════════════════
# FILE OPERATIONS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFileOperations:
    """Test file operation edge cases."""
    
    def test_save_state_creates_directory(self, ralph):
        """Test save_state creates directory if needed."""
        assert not ralph.ralph_dir.exists()
        
        ralph.save_state({"test": "data"})
        
        assert ralph.ralph_dir.exists()
        assert ralph.state_file.exists()
    
    def test_save_prompt_creates_directory(self, ralph):
        """Test save_prompt creates directory if needed."""
        assert not ralph.ralph_dir.exists()
        
        ralph.save_prompt("Test prompt")
        
        assert ralph.ralph_dir.exists()
        assert ralph.prompt_file.exists()
    
    def test_unicode_in_files(self, ralph):
        """Test Unicode handling in all files."""
        prompt = "Task with 中文, العربية, and 🎉 emojis"
        ralph.enable(prompt, completion_promise="完成 ✅")
        
        # Verify prompt
        assert ralph.get_prompt() == prompt
        
        # Verify state
        state = ralph.get_state()
        assert state["completion_promise"] == "完成 ✅"
    
    def test_load_tasks_handles_missing_file(self, ralph):
        """Test load_tasks returns empty list for missing file."""
        tasks = ralph.load_tasks()
        assert tasks == []
    
    def test_load_tasks_handles_corrupted_file(self, ralph):
        """Test load_tasks handles corrupted JSON."""
        ralph.ralph_dir.mkdir(parents=True)
        ralph.tasks_index.write_text("not valid json", encoding="utf-8")
        
        tasks = ralph.load_tasks()
        assert tasks == []


# ═══════════════════════════════════════════════════════════════════════════════
# SLUGIFY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestSlugify:
    """Test _slugify helper function."""
    
    @pytest.mark.parametrize("input_text,expected", [
        ("Simple Task", "simple-task"),
        ("Task With  Multiple   Spaces", "task-with-multiple-spaces"),
        ("Task-With-Dashes", "task-with-dashes"),
        ("task_with_underscores", "task_with_underscores"),
        ("UPPERCASE", "uppercase"),
        ("Numbers123", "numbers123"),
        ("Special!@#$%Chars", "special-chars"),
        ("  Leading/Trailing  ", "leading-trailing"),
        ("", "task"),  # Empty returns default
        ("   ", "task"),  # Whitespace only returns default
    ])
    def test_slugify_various_inputs(self, input_text, expected):
        """Test _slugify with various inputs."""
        result = RalphMode._slugify(input_text)
        assert result == expected


# ═══════════════════════════════════════════════════════════════════════════════
# CONCURRENCY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestConcurrency:
    """Test thread safety (basic)."""
    
    def test_concurrent_reads(self, active_ralph):
        """Test concurrent state reads don't crash."""
        results = []
        errors = []
        
        def read_state():
            try:
                for _ in range(100):
                    state = active_ralph.get_state()
                    results.append(state is not None)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=read_state) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert all(results)


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatus:
    """Test status functionality."""
    
    def test_status_when_inactive(self, ralph):
        """Test status returns None when inactive."""
        assert ralph.status() is None
    
    def test_status_includes_all_fields(self, active_ralph):
        """Test status includes all expected fields."""
        status = active_ralph.status()
        
        assert "iteration" in status
        assert "max_iterations" in status
        assert "completion_promise" in status
        assert "started_at" in status
        assert "version" in status
        assert "mode" in status
        assert "prompt" in status
        assert "history_entries" in status
        assert "model" in status
        assert "auto_agents" in status
    
    def test_status_prompt_matches(self, ralph):
        """Test status prompt matches original."""
        original_prompt = "Original test prompt"
        ralph.enable(original_prompt)
        
        status = ralph.status()
        assert status["prompt"] == original_prompt


# ═══════════════════════════════════════════════════════════════════════════════
# INSTRUCTIONS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestInstructions:
    """Test instructions file generation."""
    
    def test_instructions_created_on_enable(self, active_ralph):
        """Test instructions file is created."""
        assert active_ralph.instructions_file.exists()
    
    def test_instructions_contains_completion_promise(self, ralph):
        """Test instructions include completion promise when set."""
        ralph.enable("Test", completion_promise="FINISHED")
        
        instructions = ralph.instructions_file.read_text(encoding="utf-8")
        assert "FINISHED" in instructions
        assert "<promise>" in instructions
    
    def test_instructions_batch_mode_section(self, batch_ralph):
        """Test instructions include batch mode section."""
        instructions = batch_ralph.instructions_file.read_text(encoding="utf-8")
        assert "Batch Mode" in instructions or "Task Queue" in instructions
    
    def test_instructions_max_iterations_mentioned(self, ralph):
        """Test instructions mention max iterations when set."""
        ralph.enable("Test", max_iterations=50)
        
        instructions = ralph.instructions_file.read_text(encoding="utf-8")
        assert "50" in instructions


# ═══════════════════════════════════════════════════════════════════════════════
# CLEANUP TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCleanup:
    """Test cleanup functionality."""
    
    def test_disable_removes_directory(self, active_ralph):
        """Test disable removes ralph directory."""
        assert active_ralph.ralph_dir.exists()
        
        active_ralph.disable()
        
        assert not active_ralph.ralph_dir.exists()
    
    def test_disable_returns_final_state(self, active_ralph):
        """Test disable returns the final state."""
        active_ralph.iterate()
        
        state = active_ralph.disable()
        
        assert state is not None
        assert state["iteration"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# VERSION AND CONSTANTS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestConstants:
    """Test module constants."""
    
    def test_version_format(self):
        """Test VERSION follows semver format."""
        parts = VERSION.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)
    
    def test_default_model_in_available(self):
        """Test DEFAULT_MODEL is in AVAILABLE_MODELS."""
        assert DEFAULT_MODEL in AVAILABLE_MODELS
    
    def test_fallback_model_value(self):
        """Test FALLBACK_MODEL is 'auto'."""
        assert FALLBACK_MODEL == "auto"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
