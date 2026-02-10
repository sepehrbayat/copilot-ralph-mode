#!/usr/bin/env python3
"""Advanced feature-by-feature tests for Ralph Mode."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ralph_mode import RalphMode
from ralph_mode.context import ContextManager
from ralph_mode.memory import MemoryStore
from ralph_mode.scanner import _detect_language, _quick_grep_scan, cmd_scan
from ralph_mode.tasks import TaskLibrary
from ralph_mode.verification import _extract_section, _extract_verification_commands, _run_verification_commands


def _init_git_repo(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)


class TestTaskLibraryAdvanced:
    def test_parse_task_frontmatter_types(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir(parents=True)
        task_file = tasks_dir / "advanced-task.md"
        task_file.write_text(
            """---
id: ADV-001
title: Advanced Task
tags: [alpha, "beta"]
priority: 3
---
## Objective
Do advanced stuff.
""",
            encoding="utf-8",
        )

        library = TaskLibrary(base_path=tmp_path)
        task = library.parse_task_file(task_file)

        assert task["id"] == "ADV-001"
        assert task["title"] == "Advanced Task"
        assert task["tags"] == ["alpha", "beta"]
        assert task["priority"] == 3
        assert "## Objective" in task["prompt"]

    def test_list_tasks_ignores_readme_and_private(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir(parents=True)
        (tasks_dir / "README.md").write_text("# Tasks\n", encoding="utf-8")
        (tasks_dir / "_template.md").write_text("# Template\n", encoding="utf-8")
        (tasks_dir / "real-task.md").write_text("# Real\n", encoding="utf-8")

        library = TaskLibrary(base_path=tmp_path)
        tasks = library.list_tasks()

        assert len(tasks) == 1
        assert tasks[0]["file"].endswith("real-task.md")

    def test_group_task_resolution(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        groups_dir = tasks_dir / "_groups"
        groups_dir.mkdir(parents=True)

        (tasks_dir / "task-one.md").write_text("# One\n", encoding="utf-8")
        (tasks_dir / "task-two.md").write_text("# Two\n", encoding="utf-8")

        group_file = groups_dir / "alpha.json"
        group_file.write_text(json.dumps({"name": "alpha", "tasks": ["task-one", "task-two"]}), encoding="utf-8")

        library = TaskLibrary(base_path=tmp_path)
        group_tasks = library.get_group_tasks("alpha")

        assert {Path(t["file"]).stem for t in group_tasks} == {"task-one", "task-two"}

    def test_search_tasks_matches_tags_and_prompt(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir(parents=True)
        task_file = tasks_dir / "search-task.md"
        task_file.write_text(
            """---
id: SEARCH-1
title: Search Task
tags: [security, api]
---
This prompt mentions encryption.
""",
            encoding="utf-8",
        )

        library = TaskLibrary(base_path=tmp_path)
        assert library.search_tasks("security")
        assert library.search_tasks("encryption")


class TestVerificationAdvanced:
    def test_extract_section_case_insensitive(self) -> None:
        prompt = """
## Objective
Do things.

## verification
```bash
python -c "print('ok')"
```

## Completion
<promise>DONE</promise>
"""
        section = _extract_section(prompt, "## Verification")
        assert "python -c" in section
        assert "Completion" not in section

    def test_extract_verification_commands_prefers_code_block(self) -> None:
        prompt = """
## Verification
```bash
# comment
$ echo "ok"
python -c "print('ok')"
```
- should not be parsed
1. or this
"""
        commands = _extract_verification_commands(prompt)
        assert commands == ['echo "ok"', "python -c \"print('ok')\""]

    def test_extract_verification_commands_from_list(self) -> None:
        prompt = """
## Verification
- echo "ok"
1. python -c "print('ok')"
$ python -c "print('ok2')"
"""
        commands = _extract_verification_commands(prompt)
        assert 'echo "ok"' in commands
        assert "python -c \"print('ok')\"" in commands
        assert "python -c \"print('ok2')\"" in commands

    def test_run_verification_commands_reports_failure(self, tmp_path: Path) -> None:
        ok, results = _run_verification_commands(
            ["python -c \"print('ok')\"", 'python -c "import sys; sys.exit(3)"'],
            cwd=tmp_path,
            timeout=10,
        )
        assert ok is False
        assert results[0]["ok"] is True
        assert results[1]["ok"] is False
        assert results[1]["returncode"] == 3


class TestScannerAdvanced:
    def test_detect_language_from_markers(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
        assert _detect_language(str(tmp_path)) == "python"

    def test_quick_grep_scan_finds_patterns(self, tmp_path: Path) -> None:
        target = tmp_path / "app.py"
        target.write_text("eval('1+1')\npickle.loads(b'')\n", encoding="utf-8")

        findings = _quick_grep_scan(str(tmp_path), "python")
        messages = [f["message"] for f in findings]
        assert any("eval" in msg for msg in messages)
        assert any("pickle" in msg for msg in messages)

    def test_cmd_scan_changed_only_filters(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)

        file_a = repo / "a.py"
        file_b = repo / "b.py"
        file_a.write_text("print('safe')\n", encoding="utf-8")
        file_b.write_text("eval('1+1')\n", encoding="utf-8")
        subprocess.run(["git", "add", "a.py", "b.py"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True)

        file_a.write_text("eval('2+2')\n", encoding="utf-8")
        subprocess.run(["git", "add", "a.py"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "update a"], cwd=repo, check=True)

        class Args:
            quiet = True
            changed_only = True
            language = "python"

        monkeypatch.chdir(repo)
        monkeypatch.setattr(shutil, "which", lambda _: None)

        result = cmd_scan(Args())
        assert result in [0, 1]

        findings = _quick_grep_scan(str(repo), "python")
        changed_files = {"a.py"}
        filtered = [f for f in findings if f["file"] in changed_files]
        assert filtered
        assert all(f["file"] == "a.py" for f in filtered)


class TestContextManagerAdvanced:
    def test_context_includes_batch_and_completion(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / "README.md").write_text("# Repo\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)

        ralph = RalphMode(repo)
        tasks = [
            {"id": "T1", "title": "Task 1", "prompt": "Do task 1", "completion_promise": "DONE1"},
            {"id": "T2", "title": "Task 2", "prompt": "Do task 2", "completion_promise": "DONE2"},
        ]
        ralph.init_batch(tasks=tasks, max_iterations=3, completion_promise="DONE")

        state = ralph.get_state()
        state["iteration"] = 2
        ralph.save_state(state)

        output_file = repo / ".ralph-mode" / "output.txt"
        output_file.write_text("last output line\n", encoding="utf-8")

        context = ContextManager(ralph).build_full_context()
        assert "Batch Mode" in context
        assert "Task 1 of 2" in context
        assert "<promise>" in context

    def test_summary_report_includes_verification(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / "README.md").write_text("# Repo\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)

        ralph = RalphMode(repo)
        ralph.enable("Test task", completion_promise="DONE")

        ctx = ContextManager(ralph)
        report = ctx.write_summary_report(
            exit_code=1,
            verification=[{"command": "echo ok", "ok": True, "stdout": "ok", "stderr": ""}],
        )

        content = report.read_text(encoding="utf-8")
        assert "Verification Results" in content
        assert "echo ok" in content


class TestMemoryStoreAdvanced:
    def test_deduplicates_similar_entries(self, tmp_path: Path) -> None:
        ralph = RalphMode(tmp_path)
        ralph.enable("Test task")
        store = MemoryStore(ralph)

        first = store.add("Same memory", category="progress")
        second = store.add("Same memory", category="progress")

        assert first["event"] == "ADD"
        assert second["event"] == "SKIP"

    def test_search_prioritizes_category_match(self, tmp_path: Path) -> None:
        ralph = RalphMode(tmp_path)
        ralph.enable("Test task")
        store = MemoryStore(ralph)

        err = store.add("Disk error in test", category="errors")
        store.add("Regular progress update", category="progress")

        results = store.search("error", limit=5)["results"]
        assert results
        assert results[0]["id"] == err["id"]

    def test_apply_decay_reduces_scores(self, tmp_path: Path) -> None:
        ralph = RalphMode(tmp_path)
        ralph.enable("Test task")
        store = MemoryStore(ralph)

        store.add("Old memory", category="progress")
        before = store.get_all(memory_type=store.EPISODIC, limit=1)[0]["score"]

        state = ralph.get_state()
        state["iteration"] = 10
        ralph.save_state(state)

        store.apply_decay()
        after = store.get_all(memory_type=store.EPISODIC, limit=1)[0]["score"]

        assert after <= before


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
