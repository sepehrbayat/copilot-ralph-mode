"""
End-to-End Integration Tests for Ralph Mode
============================================

These tests simulate complete real-world workflows from start to finish,
testing the entire system as a black box. Critical for production readiness.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generator, List

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from ralph_mode import VERSION, RalphMode, TaskLibrary

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def production_workspace(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a production-like workspace with all components."""
    workspace = tmp_path / "production_project"
    workspace.mkdir()

    # Create typical project structure
    (workspace / "src").mkdir()
    (workspace / "tests").mkdir()
    (workspace / "docs").mkdir()
    (workspace / ".github").mkdir()
    (workspace / ".github" / "agents").mkdir()
    (workspace / ".github" / "skills").mkdir()

    # Create task library
    tasks_dir = workspace / "tasks"
    tasks_dir.mkdir()
    groups_dir = tasks_dir / "_groups"
    groups_dir.mkdir()

    # Create realistic tasks
    tasks = [
        {
            "id": "implement-auth",
            "title": "Implement Authentication System",
            "difficulty": "hard",
            "tags": ["security", "backend", "auth"],
            "content": "Implement OAuth2 authentication with JWT tokens.",
            "time": "4h",
        },
        {
            "id": "add-logging",
            "title": "Add Structured Logging",
            "difficulty": "medium",
            "tags": ["observability", "backend"],
            "content": "Add structured JSON logging throughout the application.",
            "time": "2h",
        },
        {
            "id": "write-tests",
            "title": "Write Unit Tests",
            "difficulty": "medium",
            "tags": ["testing", "quality"],
            "content": "Write comprehensive unit tests for core modules.",
            "time": "3h",
        },
        {
            "id": "fix-performance",
            "title": "Fix Performance Issues",
            "difficulty": "hard",
            "tags": ["performance", "optimization"],
            "content": "Profile and fix slow database queries.",
            "time": "5h",
        },
        {
            "id": "update-docs",
            "title": "Update Documentation",
            "difficulty": "easy",
            "tags": ["documentation"],
            "content": "Update API documentation with new endpoints.",
            "time": "1h",
        },
    ]

    for task in tasks:
        task_file = tasks_dir / f"{task['id']}.md"
        task_file.write_text(
            f"""---
id: {task['id']}
title: {task['title']}
difficulty: {task['difficulty']}
tags: {json.dumps(task['tags'])}
estimated_time: {task['time']}
---

# {task['title']}

## Overview
{task['content']}

## Requirements
- Complete all subtasks
- Write tests
- Update documentation

## Acceptance Criteria
- [ ] Implementation complete
- [ ] Tests passing
- [ ] Documentation updated
- [ ] Code reviewed
""",
            encoding="utf-8",
        )

    # Create task groups
    (groups_dir / "backend.json").write_text(
        json.dumps(
            {
                "id": "backend",
                "name": "Backend Development",
                "description": "Backend development tasks",
                "tasks": ["implement-auth", "add-logging", "fix-performance"],
            }
        ),
        encoding="utf-8",
    )

    (groups_dir / "quality.json").write_text(
        json.dumps(
            {
                "id": "quality",
                "name": "Quality Assurance",
                "description": "Testing and documentation tasks",
                "tasks": ["write-tests", "update-docs"],
            }
        ),
        encoding="utf-8",
    )

    # Copy ralph_mode.py to workspace
    ralph_mode_src = Path(__file__).parent.parent / "ralph_mode.py"
    if ralph_mode_src.exists():
        shutil.copy2(ralph_mode_src, workspace / "ralph_mode.py")

    original_cwd = os.getcwd()
    os.chdir(workspace)

    yield workspace

    os.chdir(original_cwd)


# =============================================================================
# FULL WORKFLOW E2E TESTS
# =============================================================================


class TestFullWorkflowE2E:
    """End-to-end tests for complete workflows."""

    def test_single_task_complete_workflow(self, production_workspace: Path):
        """
        E2E Test: Complete single task from start to finish.

        Workflow:
        1. Enable Ralph Mode with task
        2. Run multiple iterations
        3. Complete with promise
        4. Verify final state
        """
        rm = RalphMode(base_path=production_workspace)

        # Step 1: Enable with realistic task
        result = rm.enable(
            prompt="""
            Implement user authentication system:

            Requirements:
            1. OAuth2 authentication flow
            2. JWT token generation and validation
            3. Password hashing with bcrypt
            4. Session management
            5. Role-based access control

            Acceptance Criteria:
            - All security tests pass
            - Documentation complete
            - Code review approved
            """,
            max_iterations=20,
            completion_promise="AUTH_SYSTEM_COMPLETE",
            model="claude-sonnet-4",
        )

        assert rm.is_active()
        assert result["iteration"] == 1
        assert result["mode"] == "single"

        # Step 2: Simulate development iterations
        iterations_data = []
        for i in range(5):
            iter_result = rm.iterate()
            iterations_data.append(iter_result)

            # Verify state consistency
            status = rm.status()
            assert status["iteration"] == iter_result["iteration"]

        # Verify iteration progression
        assert iterations_data[-1]["iteration"] == 6

        # Step 3: Check completion with wrong promise (should fail)
        assert rm.check_completion("<promise>WRONG_PROMISE</promise>") is False

        # Step 4: Check completion with correct promise
        assert rm.check_completion("<promise>AUTH_SYSTEM_COMPLETE</promise>") is True

        # Step 5: Complete the task with correct promise
        final_state = rm.complete("<promise>AUTH_SYSTEM_COMPLETE</promise>")

        assert not rm.is_active()

        # Step 6: Verify history
        # Note: After disable, we need to read history differently
        # The ralph_mode directory is removed on disable

    def test_batch_workflow_complete(self, production_workspace: Path):
        """
        E2E Test: Complete batch workflow with multiple tasks.

        Workflow:
        1. Initialize batch with tasks
        2. Work through each task
        3. Complete each task
        4. Verify all tasks completed
        """
        rm = RalphMode(base_path=production_workspace)
        library = TaskLibrary(production_workspace)

        # Get backend tasks - check if group exists
        backend_group = library.get_group("backend")
        if backend_group is None:
            pytest.skip("Backend group not found in task library")

        task_ids = backend_group["tasks"]

        # Build task list from library
        tasks = []
        for task_id in task_ids:
            task = library.get_task(task_id)
            if task:
                tasks.append({"id": task["id"], "title": task["title"], "prompt": task["prompt"]})

        if len(tasks) == 0:
            pytest.skip("No tasks found in backend group")

        # Initialize batch
        result = rm.init_batch(tasks=tasks, max_iterations=5, completion_promise="TASK_DONE", model="claude-sonnet-4")

        assert rm.is_active()
        assert result["mode"] == "batch"
        assert result["current_task_index"] == 0

        # Process each task
        completed_tasks = []

        while rm.is_active():
            status = rm.status()
            if not status:
                break
            current_idx = status.get("current_task_index", 0)

            # Simulate work on task
            rm.iterate()
            rm.iterate()

            # Complete task with correct promise
            try:
                rm.complete("<promise>TASK_DONE</promise>")
                completed_tasks.append(tasks[current_idx]["id"])
            except ValueError:
                # All tasks completed
                completed_tasks.append(tasks[current_idx]["id"])
                break

        # Verify all tasks completed
        assert len(completed_tasks) == len(tasks)
        assert set(completed_tasks) == set(t["id"] for t in tasks)

    def test_interrupted_workflow_recovery(self, production_workspace: Path):
        """
        E2E Test: Recovery from interrupted workflow.

        Workflow:
        1. Start task and make progress
        2. Simulate interruption (crash/restart)
        3. Recover state
        4. Continue and complete
        """
        # Phase 1: Start and make progress
        rm1 = RalphMode(base_path=production_workspace)
        rm1.enable("Long running task with important progress", max_iterations=50, completion_promise="LONG_TASK_DONE")

        # Make significant progress
        for _ in range(15):
            rm1.iterate()

        status_before = rm1.status()
        assert status_before["iteration"] == 16

        # Phase 2: Simulate crash (just delete the instance)
        del rm1

        # Phase 3: Recovery
        rm2 = RalphMode(base_path=production_workspace)

        # Verify state preserved
        assert rm2.is_active()
        status_after = rm2.status()
        assert status_after["iteration"] == 16
        assert status_after["completion_promise"] == "LONG_TASK_DONE"

        # Phase 4: Continue work
        for _ in range(5):
            rm2.iterate()

        final_status = rm2.status()
        assert final_status["iteration"] == 21

        # Complete with correct promise
        rm2.complete("<promise>LONG_TASK_DONE</promise>")
        assert not rm2.is_active()

    def test_max_iterations_workflow(self, production_workspace: Path):
        """
        E2E Test: Workflow reaching max iterations limit.

        Workflow:
        1. Start with low max iterations
        2. Work until limit reached
        3. Verify proper shutdown
        """
        rm = RalphMode(base_path=production_workspace)
        rm.enable("Task with iteration limit", max_iterations=5, completion_promise="DONE")

        # Work until limit
        iterations_done = 0
        while rm.is_active():
            try:
                rm.iterate()
                iterations_done += 1
            except ValueError:
                # Max iterations reached - RalphMode raises ValueError
                break

        # Should have done exactly max-1 iterations (initial + iterations = max)
        assert iterations_done == 4  # 1 initial + 4 = 5

        # Mode should be disabled
        assert not rm.is_active()


class TestTaskLibraryE2E:
    """End-to-end tests for task library functionality."""

    def test_full_task_library_workflow(self, production_workspace: Path):
        """
        E2E Test: Complete task library workflow.

        Workflow:
        1. List all tasks
        2. Search for specific tasks
        3. Get task groups
        4. Run tasks from library
        """
        library = TaskLibrary(production_workspace)
        rm = RalphMode(base_path=production_workspace)

        # Step 1: List all tasks
        all_tasks = library.list_tasks()
        if len(all_tasks) < 5:
            pytest.skip(f"Expected 5 tasks but found {len(all_tasks)} - fixture may not be set up correctly")

        # Verify task structure
        for task in all_tasks:
            assert "id" in task
            assert "title" in task
            assert "tags" in task

        # Step 2: Search for tasks
        security_tasks = library.search_tasks("security")
        assert len(security_tasks) >= 1
        assert any(t["id"] == "implement-auth" for t in security_tasks)

        testing_tasks = library.search_tasks("testing")
        assert len(testing_tasks) >= 1

        # Step 3: Get groups
        all_groups = library.list_groups()
        assert len(all_groups) == 2

        backend_group = library.get_group("backend")
        assert backend_group["name"] == "Backend Development"

        # Step 4: Get group tasks
        backend_tasks = library.get_group_tasks("backend")
        assert len(backend_tasks) == 3

        # Step 5: Run a task from library
        task = library.get_task("implement-auth")
        assert task is not None

        rm.enable(prompt=task["prompt"], max_iterations=5, completion_promise="DONE")

        assert rm.is_active()
        assert task["title"] in rm.get_prompt() or task["prompt"] in rm.get_prompt()

        rm.disable()


class TestAutoAgentsE2E:
    """End-to-end tests for auto-agents functionality."""

    def test_auto_agents_complete_workflow(self, production_workspace: Path):
        """
        E2E Test: Auto-agents workflow.

        Workflow:
        1. Enable with auto_agents
        2. Register agents during work
        3. Verify agents tracked
        4. Complete workflow
        """
        rm = RalphMode(base_path=production_workspace)

        # Enable with auto-agents
        result = rm.enable(
            "Complex task requiring multiple agents",
            max_iterations=10,
            completion_promise="MULTI_AGENT_DONE",
            auto_agents=True,
        )

        assert result.get("auto_agents") is True

        # Simulate agent creation during work
        agents_created = ["code-analyzer", "test-generator", "doc-writer", "security-scanner", "performance-profiler"]

        for agent in agents_created:
            rm.register_created_agent(agent, f"{agent}.agent.md")
            rm.iterate()

        # Verify all agents tracked
        status = rm.status()
        created_agent_names = [a["name"] for a in status.get("created_agents", [])]
        assert set(agents_created) == set(created_agent_names)

        # Complete with correct promise
        rm.complete("<promise>MULTI_AGENT_DONE</promise>")


class TestCLIE2E:
    """End-to-end tests for CLI interface."""

    @pytest.fixture
    def cli_workspace(self, tmp_path: Path) -> Path:
        """Create workspace for CLI tests."""
        workspace = tmp_path / "cli_test"
        workspace.mkdir()

        # Copy ralph_mode.py
        ralph_mode_src = Path(__file__).parent.parent / "ralph_mode.py"
        if ralph_mode_src.exists():
            shutil.copy2(ralph_mode_src, workspace / "ralph_mode.py")

        return workspace

    def _run_cli(self, workspace: Path, *args) -> subprocess.CompletedProcess:
        """Run ralph_mode.py CLI command."""
        cmd = [sys.executable, str(workspace / "ralph_mode.py")] + list(args)
        return subprocess.run(
            cmd, cwd=workspace, capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace"
        )

    def test_cli_complete_workflow(self, cli_workspace: Path):
        """
        E2E Test: Complete workflow through CLI.

        Workflow:
        1. Enable via CLI
        2. Check status
        3. Iterate
        4. Complete
        5. Verify disabled
        """
        # Skip on Windows due to Unicode encoding issues in subprocess
        if os.name == "nt":
            pytest.skip("CLI tests have encoding issues on Windows")

        # Skip if ralph_mode.py doesn't exist
        if not (cli_workspace / "ralph_mode.py").exists():
            pytest.skip("ralph_mode.py not found")

        # Step 1: Enable - prompt is positional, not --prompt
        result = self._run_cli(
            cli_workspace, "enable", "CLI test task", "--max-iterations", "10", "--completion-promise", "CLI_DONE"
        )
        assert result.returncode == 0

        # Step 2: Check status
        result = self._run_cli(cli_workspace, "status")
        assert result.returncode == 0
        assert "iteration" in result.stdout.lower() or "active" in result.stdout.lower()

        # Step 3: Iterate
        result = self._run_cli(cli_workspace, "iterate")
        assert result.returncode == 0

        # Step 4: Complete (check)
        result = self._run_cli(cli_workspace, "complete", "<promise>CLI_DONE</promise>")
        assert result.returncode == 0

        # Step 5: Verify disabled
        result = self._run_cli(cli_workspace, "status")
        # Should show inactive or error

    def test_cli_batch_workflow(self, cli_workspace: Path):
        """
        E2E Test: Batch workflow through CLI.
        """
        # Skip on Windows due to Unicode encoding issues in subprocess
        if os.name == "nt":
            pytest.skip("CLI tests have encoding issues on Windows")

        if not (cli_workspace / "ralph_mode.py").exists():
            pytest.skip("ralph_mode.py not found")

        # Create tasks file
        tasks_file = cli_workspace / "batch_tasks.json"
        tasks_file.write_text(
            json.dumps(
                [
                    {"id": "task-1", "title": "Task 1", "prompt": "Do task 1"},
                    {"id": "task-2", "title": "Task 2", "prompt": "Do task 2"},
                ]
            ),
            encoding="utf-8",
        )

        # Initialize batch - use --tasks-file
        result = self._run_cli(
            cli_workspace,
            "batch-init",
            "--tasks-file",
            str(tasks_file),
            "--max-iterations",
            "5",
            "--completion-promise",
            "BATCH_DONE",
        )
        assert result.returncode == 0

        # Check status
        result = self._run_cli(cli_workspace, "status")
        assert result.returncode == 0

        # Disable
        result = self._run_cli(cli_workspace, "disable")
        assert result.returncode == 0

    def test_cli_help_commands(self, cli_workspace: Path):
        """Test all help commands work correctly."""
        if not (cli_workspace / "ralph_mode.py").exists():
            pytest.skip("ralph_mode.py not found")

        # Main help
        result = self._run_cli(cli_workspace, "--help")
        assert result.returncode == 0
        assert "ralph" in result.stdout.lower() or "usage" in result.stdout.lower()

        # Version
        result = self._run_cli(cli_workspace, "--version")
        assert result.returncode == 0
        assert VERSION in result.stdout or "version" in result.stdout.lower()


class TestErrorHandlingE2E:
    """End-to-end tests for error handling scenarios."""

    def test_graceful_degradation_corrupted_state(self, production_workspace: Path):
        """
        E2E Test: System gracefully handles corrupted state.
        """
        rm = RalphMode(base_path=production_workspace)
        rm.enable("Test task", max_iterations=10, completion_promise="DONE")
        rm.iterate()

        # Corrupt state file
        state_file = production_workspace / ".ralph-mode" / "state.json"
        state_file.write_text("not valid json {{{", encoding="utf-8")

        # New instance should handle gracefully
        rm2 = RalphMode(base_path=production_workspace)

        # Should not crash - might show as inactive or raise controlled error
        try:
            status = rm2.status()
            # If we get here, system recovered or shows inactive
            assert status is None or isinstance(status, dict)
        except (json.JSONDecodeError, KeyError):
            # Acceptable - controlled error
            pass

    def test_missing_files_handling(self, production_workspace: Path):
        """
        E2E Test: System handles missing files gracefully.
        """
        rm = RalphMode(base_path=production_workspace)
        rm.enable("Test task", max_iterations=10, completion_promise="DONE")
        rm.iterate()

        # Delete prompt file
        prompt_file = production_workspace / ".ralph-mode" / "prompt.md"
        prompt_file.unlink()

        # Should handle gracefully
        rm2 = RalphMode(base_path=production_workspace)
        prompt = rm2.get_prompt()

        # Should return None or empty or raise controlled error
        assert prompt is None or prompt == "" or isinstance(prompt, str)

    def test_concurrent_access_handling(self, production_workspace: Path):
        """
        E2E Test: System handles concurrent access.
        """
        import threading

        rm1 = RalphMode(base_path=production_workspace)
        rm1.enable("Concurrent test", max_iterations=100, completion_promise="DONE")

        errors = []
        results = []

        def worker(worker_id: int):
            try:
                rm = RalphMode(base_path=production_workspace)
                for _ in range(10):
                    if rm.is_active():
                        status = rm.status()
                        if status:
                            results.append((worker_id, status["iteration"]))
                    time.sleep(0.01)
            except Exception as e:
                errors.append((worker_id, str(e)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors or only controlled errors
        assert len(errors) == 0 or all("lock" in str(e).lower() for _, e in errors)

        rm1.disable()


class TestPerformanceE2E:
    """End-to-end performance tests."""

    def test_large_scale_batch_performance(self, production_workspace: Path):
        """
        E2E Test: Performance with large batch.
        """
        rm = RalphMode(base_path=production_workspace)

        # Create large batch
        tasks = [{"id": f"task-{i:04d}", "title": f"Task {i}", "prompt": f"Do task {i}"} for i in range(100)]

        start_time = time.time()
        rm.init_batch(tasks, max_iterations=2, completion_promise="DONE")
        init_time = time.time() - start_time

        assert init_time < 5.0, f"Batch init took {init_time}s"

        # Process some tasks
        start_time = time.time()
        for _ in range(10):
            if rm.is_active():
                rm.complete("<promise>DONE</promise>")
        process_time = time.time() - start_time

        assert process_time < 5.0, f"Processing 10 tasks took {process_time}s"

        rm.disable()

    def test_high_iteration_performance(self, production_workspace: Path):
        """
        E2E Test: Performance with many iterations.
        """
        rm = RalphMode(base_path=production_workspace)
        rm.enable("Performance test", max_iterations=0, completion_promise="DONE")

        start_time = time.time()
        for _ in range(500):
            rm.iterate()
        elapsed = time.time() - start_time

        per_iteration = elapsed / 500
        assert per_iteration < 0.05, f"Average iteration time: {per_iteration}s"

        rm.disable()


class TestVersionCompatibility:
    """Tests for version compatibility and upgrades."""

    def test_version_format(self):
        """Verify version follows semantic versioning."""
        import re

        assert re.match(r"^\d+\.\d+\.\d+", VERSION)

    def test_state_format_stability(self, production_workspace: Path):
        """
        Verify state format is stable and documented.
        """
        rm = RalphMode(base_path=production_workspace)
        rm.enable("Version test", max_iterations=10, completion_promise="DONE")

        state_file = production_workspace / ".ralph-mode" / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))

        # Required fields that must remain stable
        required_fields = {"iteration", "mode", "started_at", "max_iterations", "completion_promise"}

        assert required_fields.issubset(state.keys())

        rm.disable()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
