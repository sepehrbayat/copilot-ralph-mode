#!/usr/bin/env python3
"""
Pytest Configuration and Shared Fixtures
=========================================

Central configuration for all Ralph Mode tests.
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ralph_mode import RalphMode, TaskLibrary


# ═══════════════════════════════════════════════════════════════════════════════
# PYTEST HOOKS
# ═══════════════════════════════════════════════════════════════════════════════


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks integration tests")
    config.addinivalue_line("markers", "hypothesis: marks property-based tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers."""
    # Skip slow tests unless explicitly requested
    if not config.getoption("-m"):
        skip_slow = pytest.mark.skip(reason="Skipping slow tests (use -m slow to run)")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)


# ═══════════════════════════════════════════════════════════════════════════════
# BASIC FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Create a temporary directory that's cleaned up after the test.
    
    Yields:
        Path: Path to the temporary directory.
    """
    dir_path = Path(tempfile.mkdtemp())
    yield dir_path
    shutil.rmtree(dir_path, ignore_errors=True)


@pytest.fixture
def temp_cwd(tmp_path) -> Generator[Path, None, None]:
    """
    Create and change to a temporary directory.
    
    Yields:
        Path: Path to the temporary directory (also current working directory).
    """
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_cwd)


# ═══════════════════════════════════════════════════════════════════════════════
# RALPH MODE FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def ralph(temp_dir) -> RalphMode:
    """
    Create a fresh RalphMode instance.
    
    Args:
        temp_dir: Temporary directory fixture.
        
    Returns:
        RalphMode: Fresh RalphMode instance.
    """
    return RalphMode(temp_dir)


@pytest.fixture
def active_ralph(ralph) -> RalphMode:
    """
    Create an already-activated RalphMode instance.
    
    Args:
        ralph: RalphMode fixture.
        
    Returns:
        RalphMode: Active RalphMode instance.
    """
    ralph.enable("Test task for testing")
    return ralph


@pytest.fixture
def ralph_with_options(ralph) -> RalphMode:
    """
    Create a RalphMode with common options.
    
    Args:
        ralph: RalphMode fixture.
        
    Returns:
        RalphMode: Configured RalphMode instance.
    """
    ralph.enable(
        prompt="Build a comprehensive test suite",
        max_iterations=20,
        completion_promise="TESTS_COMPLETE",
        auto_agents=True
    )
    return ralph


@pytest.fixture
def batch_ralph(ralph) -> RalphMode:
    """
    Create a RalphMode in batch mode.
    
    Args:
        ralph: RalphMode fixture.
        
    Returns:
        RalphMode: RalphMode in batch mode.
    """
    tasks = [
        {"id": "BATCH-001", "title": "First Batch Task", "prompt": "Do the first thing"},
        {"id": "BATCH-002", "title": "Second Batch Task", "prompt": "Do the second thing"},
        {"id": "BATCH-003", "title": "Third Batch Task", "prompt": "Do the third thing"},
    ]
    ralph.init_batch(tasks, max_iterations=5, completion_promise="DONE")
    return ralph


@pytest.fixture
def batch_ralph_single_task(ralph) -> RalphMode:
    """
    Create a RalphMode in batch mode with single task.
    
    Args:
        ralph: RalphMode fixture.
        
    Returns:
        RalphMode: RalphMode in batch mode with one task.
    """
    tasks = [{"id": "SOLO-001", "title": "Solo Task", "prompt": "Do the solo thing"}]
    ralph.init_batch(tasks, max_iterations=10, completion_promise="SOLO_DONE")
    return ralph


# ═══════════════════════════════════════════════════════════════════════════════
# TASK LIBRARY FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def task_library(temp_dir) -> TaskLibrary:
    """
    Create a TaskLibrary with sample tasks and groups.
    
    Args:
        temp_dir: Temporary directory fixture.
        
    Returns:
        TaskLibrary: Configured task library.
    """
    tasks_dir = temp_dir / "tasks"
    tasks_dir.mkdir()
    groups_dir = tasks_dir / "_groups"
    groups_dir.mkdir()
    
    # Create sample tasks
    tasks_content = {
        "setup-project.md": """---
id: SETUP-001
title: Project Setup
tags: [setup, init, config]
max_iterations: 5
completion_promise: SETUP_DONE
model: gpt-5.2-codex
---

# Project Setup

Initialize the project with proper structure:
1. Create directory structure
2. Initialize git
3. Create configuration files
""",
        "implement-feature.md": """---
id: FEAT-001
title: Implement Main Feature
tags: [feature, core]
max_iterations: 20
completion_promise: FEATURE_DONE
---

# Implement Main Feature

Build the core functionality of the application.
""",
        "write-tests.md": """---
id: TEST-001
title: Write Test Suite
tags: [test, quality]
max_iterations: 15
---

Write comprehensive tests for all modules.
""",
        "documentation.md": """---
id: DOC-001
title: Write Documentation
tags: [docs]
---

Create documentation for the project.
""",
    }
    
    for filename, content in tasks_content.items():
        (tasks_dir / filename).write_text(content, encoding="utf-8")
    
    # Create groups
    groups_content = {
        "full-workflow.json": {
            "name": "full-workflow",
            "title": "Full Development Workflow",
            "description": "Complete workflow from setup to docs",
            "tasks": ["setup-project.md", "implement-feature.md", "write-tests.md", "documentation.md"]
        },
        "quick-start.json": {
            "name": "quick-start",
            "title": "Quick Start",
            "description": "Minimal setup",
            "tasks": ["setup-project.md"]
        },
        "testing.json": {
            "name": "testing",
            "title": "Testing Tasks",
            "tasks": ["write-tests.md"]
        }
    }
    
    for filename, content in groups_content.items():
        (groups_dir / filename).write_text(json.dumps(content, indent=2), encoding="utf-8")
    
    return TaskLibrary(temp_dir)


@pytest.fixture
def empty_task_library(temp_dir) -> TaskLibrary:
    """
    Create an empty TaskLibrary.
    
    Args:
        temp_dir: Temporary directory fixture.
        
    Returns:
        TaskLibrary: Empty task library.
    """
    return TaskLibrary(temp_dir)


# ═══════════════════════════════════════════════════════════════════════════════
# WORKSPACE FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def full_workspace(temp_dir) -> Path:
    """
    Create a complete workspace with all components.
    
    Args:
        temp_dir: Temporary directory fixture.
        
    Returns:
        Path: Path to the workspace.
    """
    # Create tasks directory
    tasks_dir = temp_dir / "tasks"
    tasks_dir.mkdir()
    groups_dir = tasks_dir / "_groups"
    groups_dir.mkdir()
    
    # Create tasks
    (tasks_dir / "task-001.md").write_text("""---
id: TASK-001
title: Task One
tags: [test]
---

Task one content.
""", encoding="utf-8")
    
    (tasks_dir / "task-002.md").write_text("""---
id: TASK-002
title: Task Two
tags: [test]
---

Task two content.
""", encoding="utf-8")
    
    # Create group
    (groups_dir / "test-group.json").write_text(json.dumps({
        "name": "test-group",
        "title": "Test Group",
        "tasks": ["task-001.md", "task-002.md"]
    }), encoding="utf-8")
    
    # Create .github structure
    github_dir = temp_dir / ".github"
    github_dir.mkdir()
    
    agents_dir = github_dir / "agents"
    agents_dir.mkdir()
    
    (agents_dir / "agent-creator.agent.md").write_text("""---
name: agent-creator
description: Creates new agents
tools:
  - read_file
  - write_file
---

# Agent Creator

Agent for creating other agents.
""", encoding="utf-8")
    
    hooks_dir = github_dir / "hooks"
    hooks_dir.mkdir()
    
    skills_dir = github_dir / "skills"
    skills_dir.mkdir()
    
    # Create MCP config
    config_dir = temp_dir / ".ralph-mode-config"
    config_dir.mkdir()
    
    (config_dir / "mcp-config.json").write_text(json.dumps({
        "mcpServers": {
            "test-server": {
                "type": "local",
                "command": "echo",
                "args": ["test"],
                "tools": ["*"]
            }
        }
    }, indent=2), encoding="utf-8")
    
    return temp_dir


# ═══════════════════════════════════════════════════════════════════════════════
# MOCK FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_args():
    """
    Create a factory for mock command-line arguments.
    
    Returns:
        Callable: Factory function for creating mock args.
    """
    class MockArgs:
        def __init__(self, **kwargs):
            # Default values
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
            
            # Override with provided values
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    return MockArgs


# ═══════════════════════════════════════════════════════════════════════════════
# SAMPLE DATA FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_tasks() -> list:
    """
    Provide a list of sample tasks.
    
    Returns:
        list: List of task dictionaries.
    """
    return [
        {"id": "SAMPLE-001", "title": "Sample Task 1", "prompt": "Do sample task 1"},
        {"id": "SAMPLE-002", "title": "Sample Task 2", "prompt": "Do sample task 2"},
        {"id": "SAMPLE-003", "title": "Sample Task 3", "prompt": "Do sample task 3"},
    ]


@pytest.fixture
def sample_prompts() -> list:
    """
    Provide a list of sample prompts.
    
    Returns:
        list: List of sample prompt strings.
    """
    return [
        "Simple task",
        "Task with multiple\nlines",
        "Task with émojis 🚀 and unicode",
        "Build a REST API with authentication",
        "Refactor the codebase to use async/await",
        "   Whitespace around the prompt   ",
    ]


@pytest.fixture
def sample_completion_outputs() -> dict:
    """
    Provide sample completion outputs for testing.
    
    Returns:
        dict: Dictionary of output text and expected match result.
    """
    return {
        "correct": ("<promise>DONE</promise>", True),
        "with_text": ("Output text <promise>DONE</promise> more text", True),
        "wrong_promise": ("<promise>WRONG</promise>", False),
        "no_tags": ("DONE", False),
        "incomplete": ("<promise>DONE", False),
        "empty": ("", False),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def capture_output(capsys):
    """
    Wrapper for capturing stdout/stderr.
    
    Args:
        capsys: Pytest capsys fixture.
        
    Returns:
        Callable: Function to get captured output.
    """
    def get_output():
        captured = capsys.readouterr()
        return captured.out, captured.err
    return get_output


@pytest.fixture(autouse=True)
def cleanup_ralph_dir(temp_dir):
    """
    Ensure Ralph directory is cleaned up after each test.
    
    Args:
        temp_dir: Temporary directory fixture.
    """
    yield
    # Cleanup
    ralph_dir = temp_dir / ".ralph-mode"
    if ralph_dir.exists():
        shutil.rmtree(ralph_dir, ignore_errors=True)
