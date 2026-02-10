#!/usr/bin/env python3
"""
End-to-end tests that verify:
- Memory system is used across iterations
- Memory extraction works from output
- Context includes Memory Bank and file editing guidance
- File edits are detected and shown in context
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ralph_mode import ContextManager, MemoryStore, RalphMode


@pytest.fixture
def workspace() -> Path:
    tmp = Path(tempfile.mkdtemp())
    # Initialize a git repo for context features
    subprocess.run(["git", "init"], cwd=str(tmp), check=False, capture_output=True, text=True)
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def _run_cli(workspace: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(Path(__file__).parent.parent / "ralph_mode.py"), *args],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        env=env,
    )


def test_memory_extraction_and_context_integration(workspace: Path) -> None:
    ralph = RalphMode(workspace)
    ralph.enable("Implement feature X and update tests")

    # Simulate an iteration output that should produce memories
    output = (
        "Created file src/feature_x.py and modified tests/test_feature_x.py\n"
        "Error: ModuleNotFoundError: No module named 'requests'\n"
        "pytest: 12 passed, 1 failed\n"
        "We decided to use a lightweight parser instead of regex.\n"
    )
    ralph.ralph_dir.mkdir(parents=True, exist_ok=True)
    (ralph.ralph_dir / "output.txt").write_text(output, encoding="utf-8")

    # Extract memories and facts via CLI
    result_extract = _run_cli(workspace, "memory", "extract")
    assert result_extract.returncode == 0
    result_facts = _run_cli(workspace, "memory", "extract-facts")
    assert result_facts.returncode == 0

    # Validate memory bank has relevant info
    mem = MemoryStore(ralph)
    search = mem.search("requests error", limit=5)
    assert len(search.get("results", [])) > 0

    # Context should include Memory Bank and editing guidance
    ctx = ContextManager(ralph)
    content = ctx.build_full_context()
    assert "## Memory Bank" in content
    assert "## File Editing Best Practices" in content


def test_file_edits_are_detected_in_context(workspace: Path) -> None:
    ralph = RalphMode(workspace)
    ralph.enable("Edit files and verify context")

    # Move to iteration 2 so Files Already Changed section appears
    ralph.iterate()

    # Create actual file edits
    src_dir = workspace / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "edited_file.py").write_text("print('edited')\n", encoding="utf-8")

    ctx = ContextManager(ralph)
    content = ctx.build_full_context()
    assert "Files Already Changed" in content
    assert "src/edited_file.py" in content


def test_memory_persistence_across_iterations(workspace: Path) -> None:
    ralph = RalphMode(workspace)
    ralph.enable("Ensure memory persists across iterations")

    mem = MemoryStore(ralph)
    mem.add("Persistent fact: project uses SQLite", memory_type=mem.SEMANTIC, category="dependencies")

    # New MemoryStore instance should read same memory from disk
    mem2 = MemoryStore(ralph)
    results = mem2.search("SQLite", limit=5)
    assert len(results.get("results", [])) > 0

    # Apply decay and promotion should not crash and should return values
    count = mem2.apply_decay()
    assert isinstance(count, int)
    promoted = mem2.promote_memories(min_access=2)
    assert isinstance(promoted, list)
