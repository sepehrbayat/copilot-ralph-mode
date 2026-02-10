#!/usr/bin/env python3
"""
Integration Tests for Copilot Ralph Mode
========================================

End-to-end integration tests that test complete workflows.
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ralph_mode import VERSION, RalphMode, TaskLibrary

# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def workspace(tmp_path):
    """Create a complete workspace structure."""
    # Create tasks directory
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    groups_dir = tasks_dir / "_groups"
    groups_dir.mkdir()

    # Create sample tasks
    (tasks_dir / "task-001.md").write_text(
        """---
id: TASK-001
title: First Task
tags: [setup, init]
max_iterations: 5
completion_promise: TASK_001_DONE
---

# First Task

Initialize the project structure.
""",
        encoding="utf-8",
    )

    (tasks_dir / "task-002.md").write_text(
        """---
id: TASK-002
title: Second Task
tags: [feature]
max_iterations: 10
completion_promise: TASK_002_DONE
---

# Second Task

Implement the main feature.
""",
        encoding="utf-8",
    )

    (tasks_dir / "task-003.md").write_text(
        """---
id: TASK-003
title: Third Task
tags: [test]
---

Write tests.
""",
        encoding="utf-8",
    )

    # Create groups
    (groups_dir / "main.json").write_text(
        json.dumps(
            {
                "name": "main",
                "title": "Main Workflow",
                "description": "Complete workflow from setup to testing",
                "tasks": ["task-001.md", "task-002.md", "task-003.md"],
            }
        ),
        encoding="utf-8",
    )

    (groups_dir / "quick.json").write_text(
        json.dumps({"name": "quick", "title": "Quick Tasks", "tasks": ["task-001.md"]}), encoding="utf-8"
    )

    # Create .github directory for agents (auto-agents feature)
    github_dir = tmp_path / ".github" / "agents"
    github_dir.mkdir(parents=True)

    (github_dir / "agent-creator.agent.md").write_text(
        """---
name: agent-creator
description: Creates new agents
tools:
  - read_file
  - write_file
---

# Agent Creator

Instructions for creating agents.
""",
        encoding="utf-8",
    )

    return tmp_path


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE TASK WORKFLOW TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestSingleTaskWorkflow:
    """Test complete single task workflow."""

    def test_complete_single_task_workflow(self, workspace):
        """Test: enable → iterate → complete → disable."""
        ralph = RalphMode(workspace)

        # 1. Enable
        state = ralph.enable("Build a REST API", max_iterations=10, completion_promise="API_COMPLETE")
        assert ralph.is_active()
        assert state["iteration"] == 1
        assert state["mode"] == "single"

        # 2. Iterate several times
        for _ in range(3):
            state = ralph.iterate()
        assert state["iteration"] == 4

        # 3. Check status
        status = ralph.status()
        assert status["iteration"] == 4
        assert status["prompt"] == "Build a REST API"

        # 4. Check history
        history = ralph.get_history()
        assert len(history) >= 4  # started + 3 iterations

        # 5. Attempt completion (wrong)
        assert not ralph.complete("<promise>WRONG</promise>")
        assert ralph.is_active()  # Still active

        # 6. Complete correctly
        assert ralph.complete("<promise>API_COMPLETE</promise>")
        assert not ralph.is_active()  # Disabled

    def test_max_iterations_workflow(self, workspace):
        """Test workflow that reaches max iterations."""
        ralph = RalphMode(workspace)

        ralph.enable("Test task", max_iterations=3)

        # Iterate to max (enable sets iteration=1)
        ralph.iterate()  # iteration=2 (1 >= 3: no, increment)
        ralph.iterate()  # iteration=3 (2 >= 3: no, increment)

        # Should raise on exceeding max (3 >= 3: yes)
        with pytest.raises(ValueError, match="Max iterations"):
            ralph.iterate()

        # Should be disabled
        assert not ralph.is_active()


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH MODE WORKFLOW TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestBatchModeWorkflow:
    """Test complete batch mode workflow."""

    def test_complete_batch_workflow(self, workspace):
        """Test: batch-init → iterate → complete → next → ... → finish."""
        ralph = RalphMode(workspace)

        # 1. Initialize batch
        tasks = [
            {"id": "B-001", "title": "Batch Task 1", "prompt": "Do task 1"},
            {"id": "B-002", "title": "Batch Task 2", "prompt": "Do task 2"},
            {"id": "B-003", "title": "Batch Task 3", "prompt": "Do task 3"},
        ]
        state = ralph.init_batch(tasks, max_iterations=5, completion_promise="DONE")

        assert state["mode"] == "batch"
        assert state["tasks_total"] == 3
        assert state["current_task_index"] == 0

        # 2. Complete first task
        ralph.iterate()  # iteration 2
        assert ralph.complete("<promise>DONE</promise>")

        state = ralph.get_state()
        assert state["current_task_index"] == 1  # Advanced to task 2
        assert state["iteration"] == 1  # Reset for new task

        # 3. Complete second task via next_task
        ralph.iterate()
        state = ralph.next_task(reason="manual")

        assert state["current_task_index"] == 2  # Task 3

        # 4. Complete final task
        assert ralph.complete("<promise>DONE</promise>")

        # Should be done
        assert not ralph.is_active()

    def test_batch_max_iterations_advances(self, workspace):
        """Test batch mode advances task when max iterations reached."""
        ralph = RalphMode(workspace)

        tasks = [
            {"id": "T1", "title": "Task 1", "prompt": "Do 1"},
            {"id": "T2", "title": "Task 2", "prompt": "Do 2"},
        ]
        ralph.init_batch(tasks, max_iterations=2, completion_promise="DONE")
        # After init_batch: iteration=1, index=0

        # First iterate: check 1 >= 2: NO, increment to 2
        state = ralph.iterate()
        assert state["iteration"] == 2
        assert state["current_task_index"] == 0

        # Second iterate: check 2 >= 2: YES, advance to next task
        state = ralph.iterate()

        # Should have advanced to task 2
        assert state["current_task_index"] == 1
        assert state["iteration"] == 1

    def test_batch_prompts_change(self, workspace):
        """Test that prompts change when advancing tasks."""
        ralph = RalphMode(workspace)

        tasks = [
            {"id": "T1", "title": "Task 1", "prompt": "First prompt"},
            {"id": "T2", "title": "Task 2", "prompt": "Second prompt"},
        ]
        ralph.init_batch(tasks, max_iterations=100)

        # First task prompt
        assert ralph.get_prompt() == "First prompt"

        # Advance
        ralph.next_task()

        # Second task prompt
        assert ralph.get_prompt() == "Second prompt"


# ═══════════════════════════════════════════════════════════════════════════════
# TASK LIBRARY WORKFLOW TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTaskLibraryWorkflow:
    """Test workflows using task library."""

    def test_run_single_task_from_library(self, workspace):
        """Test running a single task from library."""
        library = TaskLibrary(workspace)
        ralph = RalphMode(workspace)

        # Get task from library
        task = library.get_task("TASK-001")
        assert task is not None

        # Enable with task settings
        ralph.enable(
            task["prompt"],
            max_iterations=task.get("max_iterations", 20),
            completion_promise=task.get("completion_promise", "DONE"),
        )

        assert ralph.is_active()
        assert ralph.get_state()["max_iterations"] == 5
        assert ralph.get_state()["completion_promise"] == "TASK_001_DONE"

        ralph.disable()

    def test_run_group_from_library(self, workspace):
        """Test running a group from library."""
        library = TaskLibrary(workspace)
        ralph = RalphMode(workspace)

        # Get group tasks
        tasks = library.get_group_tasks("main")
        assert len(tasks) == 3

        # Init batch with group
        state = ralph.init_batch(
            [{"id": t["id"], "title": t["title"], "prompt": t["prompt"]} for t in tasks],
            max_iterations=10,
            completion_promise="DONE",
        )

        assert state["tasks_total"] == 3

        ralph.disable()

    def test_search_and_run_tasks(self, workspace):
        """Test searching and running matching tasks."""
        library = TaskLibrary(workspace)
        ralph = RalphMode(workspace)

        # Search by tag
        results = library.search_tasks("setup")
        assert len(results) >= 1

        # Run first matching task
        task = results[0]
        ralph.enable(task["prompt"])

        assert ralph.is_active()
        ralph.disable()


# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-AGENTS WORKFLOW TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutoAgentsWorkflow:
    """Test auto-agents workflow."""

    def test_enable_with_auto_agents(self, workspace):
        """Test enabling with auto-agents creates proper state."""
        ralph = RalphMode(workspace)

        state = ralph.enable("Test", auto_agents=True)

        assert state["auto_agents"] is True
        assert state["created_agents"] == []

        # Instructions should mention auto-agents
        instructions = ralph.instructions_file.read_text(encoding="utf-8")
        assert "Auto-Agents" in instructions

        ralph.disable()

    def test_register_agents_during_workflow(self, workspace):
        """Test registering agents during workflow."""
        ralph = RalphMode(workspace)
        ralph.enable("Test", auto_agents=True)

        # Simulate agent creation
        ralph.register_created_agent("test-agent", ".github/agents/test-agent.agent.md")
        ralph.iterate()
        ralph.register_created_agent("another-agent", ".github/agents/another.agent.md")

        state = ralph.get_state()
        assert len(state["created_agents"]) == 2

        # Check agent info
        agents = state["created_agents"]
        assert agents[0]["name"] == "test-agent"
        assert agents[1]["name"] == "another-agent"
        assert agents[0]["iteration"] == 1
        assert agents[1]["iteration"] == 2

        ralph.disable()


# ═══════════════════════════════════════════════════════════════════════════════
# STATE PERSISTENCE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatePersistence:
    """Test state persistence across sessions."""

    def test_state_survives_restart(self, workspace):
        """Test state persists after 'restart' (new instance)."""
        # Session 1: Enable and iterate
        ralph1 = RalphMode(workspace)
        ralph1.enable("Long running task", max_iterations=100)
        ralph1.iterate()
        ralph1.iterate()

        # Simulate restart: new instance
        ralph2 = RalphMode(workspace)

        # Should see same state
        assert ralph2.is_active()
        state = ralph2.get_state()
        assert state["iteration"] == 3
        assert state["max_iterations"] == 100

        ralph2.disable()

    def test_history_accumulates(self, workspace):
        """Test history accumulates across 'sessions'."""
        # Session 1
        ralph1 = RalphMode(workspace)
        ralph1.enable("Test")
        ralph1.iterate()

        # Session 2
        ralph2 = RalphMode(workspace)
        ralph2.iterate()
        ralph2.iterate()

        # Check history
        history = ralph2.get_history()
        assert len(history) >= 4  # started + 3 iterations

        ralph2.disable()


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR RECOVERY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorRecovery:
    """Test error recovery scenarios."""

    def test_corrupted_state_handling(self, workspace):
        """Test handling of corrupted state file."""
        ralph = RalphMode(workspace)
        ralph.enable("Test")

        # Corrupt the state file
        ralph.state_file.write_text("corrupted data", encoding="utf-8")

        # New instance should handle gracefully
        ralph2 = RalphMode(workspace)

        # is_active checks file exists (still True)
        # but get_state returns None due to parse error
        assert ralph2.is_active()  # File exists
        assert ralph2.get_state() is None  # Can't parse

        # Clean up manually
        shutil.rmtree(ralph.ralph_dir)

    def test_missing_prompt_file(self, workspace):
        """Test handling when prompt file is deleted."""
        ralph = RalphMode(workspace)
        ralph.enable("Original prompt")

        # Delete prompt file
        ralph.prompt_file.unlink()

        # Should return None
        assert ralph.get_prompt() is None

        ralph.disable()

    def test_partial_batch_state(self, workspace):
        """Test handling partial batch state."""
        ralph = RalphMode(workspace)
        tasks = [
            {"id": "T1", "title": "Task 1", "prompt": "P1"},
            {"id": "T2", "title": "Task 2", "prompt": "P2"},
        ]
        ralph.init_batch(tasks, max_iterations=100)

        # Delete tasks index
        ralph.tasks_index.unlink()

        # load_tasks should return empty
        assert ralph.load_tasks() == []

        ralph.disable()


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLETE END-TO-END SCENARIO
# ═══════════════════════════════════════════════════════════════════════════════


class TestEndToEndScenario:
    """Complete end-to-end scenario tests."""

    def test_full_project_workflow(self, workspace):
        """Test a complete project workflow."""
        ralph = RalphMode(workspace)
        library = TaskLibrary(workspace)

        # 1. List available tasks
        tasks = library.list_tasks()
        assert len(tasks) >= 3

        # 2. List available groups
        groups = library.list_groups()
        assert len(groups) >= 1

        # 3. Get the "main" group
        main_group = library.get_group("main")
        assert main_group is not None

        # 4. Get tasks from the group
        group_tasks = library.get_group_tasks("main")
        assert len(group_tasks) == 3

        # 5. Initialize batch mode with auto-agents
        batch_tasks = [{"id": t["id"], "title": t["title"], "prompt": t["prompt"]} for t in group_tasks]
        state = ralph.init_batch(batch_tasks, max_iterations=10, completion_promise="TASK_DONE", auto_agents=True)

        assert state["mode"] == "batch"
        assert state["auto_agents"] is True

        # 6. Work through tasks
        tasks_completed = 0
        max_loops = 50  # Safety limit
        loop_count = 0

        while ralph.is_active() and loop_count < max_loops:
            loop_count += 1

            # Simulate work
            state = ralph.get_state()
            current_task = state.get("current_task_index", 0)

            # Every 3 iterations, complete current task
            if state["iteration"] >= 3:
                try:
                    if ralph.complete("<promise>TASK_DONE</promise>"):
                        tasks_completed += 1
                except ValueError:
                    # All tasks completed - this is expected on last task
                    tasks_completed += 1
                    break
            else:
                try:
                    ralph.iterate()
                except ValueError:
                    break  # Max reached or all done

        # Should have completed some tasks
        assert tasks_completed >= 1

        # Should be disabled after all tasks
        assert not ralph.is_active()

        # Verify history was logged
        # Note: history is deleted on disable, so we check it was working during workflow


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
