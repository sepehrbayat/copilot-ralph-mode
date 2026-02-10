#!/usr/bin/env python3
"""
CLI Tests for Copilot Ralph Mode
================================

Tests for command-line interface functionality.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ralph_mode import (
    cmd_batch_init,
    cmd_complete,
    cmd_disable,
    cmd_enable,
    cmd_help,
    cmd_history,
    cmd_iterate,
    cmd_next_task,
    cmd_prompt,
    cmd_run,
    cmd_status,
    cmd_tasks,
    cmd_verification,
    main,
)

# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def temp_cwd(tmp_path):
    """Create and change to a temporary directory."""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_cwd)


@pytest.fixture
def mock_args():
    """Create a mock args object."""

    class Args:
        def __init__(self, **kwargs):
            self.prompt = ["Test task"]
            self.max_iterations = 0
            self.completion_promise = None
            self.model = None
            self.auto_agents = False
            self.tasks_file = None
            self.output = None
            self.action = "list"
            self.identifier = None
            self.task = None
            self.group = None
            for k, v in kwargs.items():
                setattr(self, k, v)

    return Args


# ═══════════════════════════════════════════════════════════════════════════════
# CMD_ENABLE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdEnable:
    """Tests for cmd_enable function."""

    def test_enable_basic(self, temp_cwd, mock_args, capsys):
        """Test basic enable command."""
        args = mock_args(prompt=["Build", "a", "REST", "API"])

        result = cmd_enable(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "RALPH MODE ENABLED" in captured.out
        assert "Build a REST API" in captured.out

    def test_enable_no_prompt_fails(self, temp_cwd, mock_args, capsys):
        """Test enable without prompt fails."""
        args = mock_args(prompt=[])

        result = cmd_enable(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out or "error" in captured.out.lower()

    def test_enable_with_options(self, temp_cwd, mock_args, capsys):
        """Test enable with all options."""
        args = mock_args(
            prompt=["Test task"],
            max_iterations=20,
            completion_promise="DONE",
            model="claude-sonnet-4",
            auto_agents=True,
        )

        result = cmd_enable(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "20" in captured.out
        assert "DONE" in captured.out

    def test_enable_twice_fails(self, temp_cwd, mock_args, capsys):
        """Test enabling twice fails."""
        args = mock_args(prompt=["First task"])
        cmd_enable(args)

        result = cmd_enable(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "already active" in captured.out.lower()

    def test_enable_with_unknown_model_warns(self, temp_cwd, mock_args, capsys):
        """Test enable with unknown model shows warning."""
        args = mock_args(prompt=["Test"], model="unknown-model-xyz")

        result = cmd_enable(args)

        assert result == 0  # Should still succeed
        captured = capsys.readouterr()
        assert "Warning" in captured.out or "warning" in captured.out.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# CMD_DISABLE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdDisable:
    """Tests for cmd_disable function."""

    def test_disable_active(self, temp_cwd, mock_args, capsys):
        """Test disabling active Ralph mode."""
        # Enable first
        cmd_enable(mock_args(prompt=["Test"]))

        result = cmd_disable(mock_args())

        assert result == 0
        captured = capsys.readouterr()
        assert "disabled" in captured.out.lower()

    def test_disable_inactive(self, temp_cwd, mock_args, capsys):
        """Test disabling when not active."""
        result = cmd_disable(mock_args())

        assert result == 0
        captured = capsys.readouterr()
        assert "No active" in captured.out or "not found" in captured.out.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# CMD_STATUS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdStatus:
    """Tests for cmd_status function."""

    def test_status_inactive(self, temp_cwd, mock_args, capsys):
        """Test status when inactive."""
        result = cmd_status(mock_args())

        assert result == 0
        captured = capsys.readouterr()
        assert "INACTIVE" in captured.out

    def test_status_active(self, temp_cwd, mock_args, capsys):
        """Test status when active."""
        cmd_enable(mock_args(prompt=["Test task"]))

        result = cmd_status(mock_args())

        assert result == 0
        captured = capsys.readouterr()
        assert "ACTIVE" in captured.out
        assert "Test task" in captured.out


# ═══════════════════════════════════════════════════════════════════════════════
# CMD_ITERATE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdIterate:
    """Tests for cmd_iterate function."""

    def test_iterate_active(self, temp_cwd, mock_args, capsys):
        """Test iterate when active."""
        cmd_enable(mock_args(prompt=["Test"]))

        result = cmd_iterate(mock_args())

        assert result == 0
        captured = capsys.readouterr()
        assert "iteration" in captured.out.lower()

    def test_iterate_inactive(self, temp_cwd, mock_args, capsys):
        """Test iterate when not active."""
        result = cmd_iterate(mock_args())

        assert result == 1


# ═══════════════════════════════════════════════════════════════════════════════
# CMD_PROMPT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdPrompt:
    """Tests for cmd_prompt function."""

    def test_prompt_active(self, temp_cwd, mock_args, capsys):
        """Test getting prompt when active."""
        cmd_enable(mock_args(prompt=["My specific task"]))

        result = cmd_prompt(mock_args())

        assert result == 0
        captured = capsys.readouterr()
        assert "My specific task" in captured.out

    def test_prompt_inactive(self, temp_cwd, mock_args, capsys):
        """Test getting prompt when not active."""
        result = cmd_prompt(mock_args())

        assert result == 1


# ═══════════════════════════════════════════════════════════════════════════════
# CMD_COMPLETE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdComplete:
    """Tests for cmd_complete function."""

    def test_complete_with_promise(self, temp_cwd, mock_args, capsys):
        """Test complete with valid promise."""
        cmd_enable(mock_args(prompt=["Test"], completion_promise="DONE"))

        args = mock_args(output=["<promise>DONE</promise>"])
        result = cmd_complete(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "detected" in captured.out.lower() or "disabled" in captured.out.lower()

    def test_complete_without_promise(self, temp_cwd, mock_args, capsys):
        """Test complete without valid promise."""
        cmd_enable(mock_args(prompt=["Test"], completion_promise="DONE"))

        args = mock_args(output=["Some random output"])
        result = cmd_complete(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "Continue" in captured.out or "not found" in captured.out.lower()

    def test_complete_from_stdin(self, temp_cwd, mock_args, capsys):
        """Test complete reading from stdin."""
        cmd_enable(mock_args(prompt=["Test"], completion_promise="DONE"))

        args = mock_args(output=None)

        with patch("sys.stdin", StringIO("<promise>DONE</promise>")):
            result = cmd_complete(args)

        assert result == 0


# ═══════════════════════════════════════════════════════════════════════════════
# CMD_HISTORY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdHistory:
    """Tests for cmd_history function."""

    def test_history_with_entries(self, temp_cwd, mock_args, capsys):
        """Test history with entries."""
        cmd_enable(mock_args(prompt=["Test"]))
        cmd_iterate(mock_args())

        result = cmd_history(mock_args())

        assert result == 0
        captured = capsys.readouterr()
        assert "started" in captured.out.lower()
        assert "iterate" in captured.out.lower()

    def test_history_empty(self, temp_cwd, mock_args, capsys):
        """Test history when empty."""
        result = cmd_history(mock_args())

        assert result == 0
        captured = capsys.readouterr()
        assert "No history" in captured.out


# ═══════════════════════════════════════════════════════════════════════════════
# CMD_VERIFICATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdVerification:
    """Tests for cmd_verification function."""

    def test_verify_show_no_commands(self, temp_cwd, mock_args, capsys):
        """Test verify show with no commands returns 0."""
        cmd_enable(mock_args(prompt=["Test"]))

        class Args:
            action = "show"
            timeout = 1

        result = cmd_verification(Args())

        assert result == 0
        captured = capsys.readouterr()
        assert "No verification" in captured.out or "no verification" in captured.out.lower()

    def test_verify_run_executes_commands(self, temp_cwd, mock_args):
        """Test verify run executes commands from verification section."""
        prompt = """
## Objective
Do a thing.

## Scope
- ONLY modify: none
- DO NOT read: none
- DO NOT touch: none

## Pre-work
- N/A

## Changes Required
- N/A

## Acceptance Criteria
- N/A

## Verification
```bash
python -c "print('ok')"
```

## Completion
<promise>DONE</promise>
"""
        cmd_enable(mock_args(prompt=[prompt], completion_promise="DONE"))

        class Args:
            action = "run"
            timeout = 30

        result = cmd_verification(Args())

        assert result == 0
        summary = temp_cwd / ".ralph-mode" / "summary.md"
        assert summary.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# CMD_BATCH_INIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdBatchInit:
    """Tests for cmd_batch_init function."""

    def test_batch_init_valid_file(self, temp_cwd, mock_args, capsys):
        """Test batch init with valid tasks file."""
        # Create tasks file
        tasks = [
            {"id": "T1", "title": "Task 1", "prompt": "Do 1"},
            {"id": "T2", "title": "Task 2", "prompt": "Do 2"},
        ]
        tasks_file = temp_cwd / "tasks.json"
        tasks_file.write_text(json.dumps(tasks), encoding="utf-8")

        args = mock_args(tasks_file=str(tasks_file), max_iterations=10)
        result = cmd_batch_init(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "BATCH" in captured.out
        assert "2" in captured.out  # 2 tasks

    def test_batch_init_missing_file(self, temp_cwd, mock_args, capsys):
        """Test batch init with missing file."""
        args = mock_args(tasks_file="nonexistent.json", max_iterations=10)
        result = cmd_batch_init(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out or "not found" in captured.out.lower()

    def test_batch_init_invalid_json(self, temp_cwd, mock_args, capsys):
        """Test batch init with invalid JSON."""
        tasks_file = temp_cwd / "invalid.json"
        tasks_file.write_text("not valid json", encoding="utf-8")

        args = mock_args(tasks_file=str(tasks_file), max_iterations=10)
        result = cmd_batch_init(args)

        assert result == 1


# ═══════════════════════════════════════════════════════════════════════════════
# CMD_NEXT_TASK TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdNextTask:
    """Tests for cmd_next_task function."""

    def test_next_task_in_batch(self, temp_cwd, mock_args, capsys):
        """Test next_task in batch mode."""
        # Create tasks file
        tasks = [
            {"id": "T1", "title": "Task 1", "prompt": "Do 1"},
            {"id": "T2", "title": "Task 2", "prompt": "Do 2"},
        ]
        tasks_file = temp_cwd / "tasks.json"
        tasks_file.write_text(json.dumps(tasks), encoding="utf-8")

        cmd_batch_init(mock_args(tasks_file=str(tasks_file), max_iterations=10))

        result = cmd_next_task(mock_args())

        assert result == 0
        captured = capsys.readouterr()
        assert "Task 2" in captured.out or "2/" in captured.out

    def test_next_task_not_in_batch(self, temp_cwd, mock_args, capsys):
        """Test next_task when not in batch mode."""
        cmd_enable(mock_args(prompt=["Test"]))

        result = cmd_next_task(mock_args())

        assert result == 1


# ═══════════════════════════════════════════════════════════════════════════════
# CMD_TASKS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdTasks:
    """Tests for cmd_tasks function."""

    def test_tasks_list_empty(self, temp_cwd, mock_args, capsys, monkeypatch):
        """Test tasks list when no tasks."""
        # Mock TaskLibrary to use temp directory
        from unittest.mock import MagicMock

        mock_library = MagicMock()
        mock_library.list_tasks.return_value = []
        mock_library.list_groups.return_value = []

        import ralph_mode

        monkeypatch.setattr(ralph_mode, "TaskLibrary", lambda: mock_library)

        args = mock_args(action="list")
        result = cmd_tasks(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "No tasks" in captured.out or "tasks/" in captured.out.lower()

    def test_tasks_list_with_tasks(self, temp_cwd, mock_args, capsys, monkeypatch):
        """Test tasks list with tasks."""
        # Mock TaskLibrary to return test tasks
        from unittest.mock import MagicMock

        mock_library = MagicMock()
        mock_library.list_tasks.return_value = [{"id": "TEST-001", "title": "Test Task", "tags": ["test"]}]
        mock_library.list_groups.return_value = []

        import ralph_mode

        monkeypatch.setattr(ralph_mode, "TaskLibrary", lambda: mock_library)

        args = mock_args(action="list")
        result = cmd_tasks(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "TEST-001" in captured.out

    def test_tasks_show_not_found(self, temp_cwd, mock_args, capsys, monkeypatch):
        """Test tasks show with nonexistent task."""
        # Mock TaskLibrary to return None for get_task
        from unittest.mock import MagicMock

        mock_library = MagicMock()
        mock_library.get_task.return_value = None

        import ralph_mode

        monkeypatch.setattr(ralph_mode, "TaskLibrary", lambda: mock_library)

        args = mock_args(action="show", identifier="NONEXISTENT")
        result = cmd_tasks(args)

        assert result == 1

    def test_tasks_search_no_query(self, temp_cwd, mock_args, capsys, monkeypatch):
        """Test tasks search without query."""
        # Mock TaskLibrary
        from unittest.mock import MagicMock

        mock_library = MagicMock()

        import ralph_mode

        monkeypatch.setattr(ralph_mode, "TaskLibrary", lambda: mock_library)

        args = mock_args(action="search", identifier=None)
        result = cmd_tasks(args)

        assert result == 1


# ═══════════════════════════════════════════════════════════════════════════════
# CMD_RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdRun:
    """Tests for cmd_run function."""

    def test_run_no_task_no_group(self, temp_cwd, mock_args, capsys):
        """Test run without task or group."""
        args = mock_args(task=None, group=None)
        result = cmd_run(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "--task" in captured.out or "--group" in captured.out

    def test_run_task_not_found(self, temp_cwd, mock_args, capsys):
        """Test run with nonexistent task."""
        args = mock_args(task="NONEXISTENT", group=None)
        result = cmd_run(args)

        assert result == 1

    def test_run_group_not_found(self, temp_cwd, mock_args, capsys):
        """Test run with nonexistent group."""
        args = mock_args(task=None, group="nonexistent")
        result = cmd_run(args)

        assert result == 1


# ═══════════════════════════════════════════════════════════════════════════════
# CMD_HELP TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdHelp:
    """Tests for cmd_help function."""

    def test_help_output(self, mock_args, capsys):
        """Test help output."""
        result = cmd_help(mock_args())

        assert result == 0
        captured = capsys.readouterr()
        assert "Ralph Mode" in captured.out
        assert "USAGE" in captured.out
        assert "COMMANDS" in captured.out


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN FUNCTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestMain:
    """Tests for main() function."""

    def test_main_no_args_shows_help(self, temp_cwd, capsys):
        """Test main with no args shows help."""
        with patch("sys.argv", ["ralph-mode"]):
            result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "Ralph Mode" in captured.out

    def test_main_version(self, capsys):
        """Test main --version."""
        with patch("sys.argv", ["ralph-mode", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_enable(self, temp_cwd, capsys):
        """Test main enable command."""
        with patch("sys.argv", ["ralph-mode", "enable", "Test task"]):
            result = main()

        assert result == 0

    def test_main_status(self, temp_cwd, capsys):
        """Test main status command."""
        with patch("sys.argv", ["ralph-mode", "status"]):
            result = main()

        assert result == 0

    def test_main_help_command(self, capsys):
        """Test main help command."""
        with patch("sys.argv", ["ralph-mode", "help"]):
            result = main()

        assert result == 0


# ═══════════════════════════════════════════════════════════════════════════════
# SUBPROCESS TESTS (if running as actual CLI)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not shutil.which("python"), reason="Python not in PATH")
class TestCLISubprocess:
    """Tests running CLI as subprocess."""

    def test_cli_help(self, temp_cwd):
        """Test CLI help via subprocess."""
        # ralph_mode.py is a standalone script, not a module
        script_path = Path(__file__).parent.parent / "ralph_mode.py"

        # Set UTF-8 encoding for subprocess to avoid Windows cp1252 issues with emoji
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            [sys.executable, str(script_path), "help"], capture_output=True, text=True, cwd=str(temp_cwd), env=env
        )

        # Check either stdout or stderr (help might go to either)
        output = result.stdout + result.stderr
        assert "Ralph Mode" in output or "Usage:" in output or "enable" in output.lower()

    def test_cli_version(self, temp_cwd):
        """Test CLI version via subprocess."""
        # ralph_mode.py is a standalone script, not a module
        script_path = Path(__file__).parent.parent / "ralph_mode.py"

        # Set UTF-8 encoding for subprocess to avoid Windows cp1252 issues
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            [sys.executable, str(script_path), "--version"], capture_output=True, text=True, cwd=str(temp_cwd), env=env
        )

        # Version might be in stdout or stderr depending on argparse
        output = result.stdout + result.stderr
        assert "." in output  # Version contains dots


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
