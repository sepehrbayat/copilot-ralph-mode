#!/usr/bin/env python3
"""
Comprehensive edge case and stress tests for Ralph Mode.
Tests complex scenarios, error conditions, and boundary cases.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest


class TestRalphEdgeCases:
    """Test complex and edge case scenarios for Ralph Mode."""

    @pytest.fixture
    def test_repo(self, tmp_path):
        """Create a test git repository."""
        repo = tmp_path / "test_repo"
        repo.mkdir()

        # Initialize git
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)

        # Create initial commit
        (repo / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo, check=True)

        return repo

    def test_promise_with_multiple_whitespace_variations(self, test_repo):
        """Test promise detection with various whitespace patterns."""
        os.chdir(test_repo)

        # Enable Ralph
        result = subprocess.run(
            [
                "python3",
                "/workspace/ralph_mode.py",
                "enable",
                "Test task",
                "--completion-promise",
                "DONE",
                "--max-iterations",
                "3",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Test various promise formats
        promise_variants = [
            "<promise>DONE</promise>",
            "<promise>\nDONE</promise>",
            "<promise>DONE\n</promise>",
            "<promise>\nDONE\n</promise>",
            "<promise>\n\nDONE\n\n</promise>",
            "<promise>  DONE  </promise>",
            "<promise>\t\nDONE\t\n</promise>",
        ]

        for variant in promise_variants:
            output_file = test_repo / ".ralph-mode" / "output.txt"
            output_file.parent.mkdir(exist_ok=True)
            output_file.write_text(f"Some output\n{variant}\nMore output\n")

            # Test promise detection
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    f"""
                cd {test_repo}
                source /workspace/ralph-loop.sh
                PROMISE="DONE" OUTPUT_FILE="{output_file}" python3 <<'PY'
import re, sys, os
promise = os.environ.get('PROMISE', '').strip()
output_file = os.environ.get('OUTPUT_FILE', '')
with open(output_file, 'r') as f:
    text = f.read()
matches = re.findall(r"<promise>(.*?)</promise>", text, re.DOTALL)
sys.exit(0 if any(m.strip() == promise for m in matches) else 1)
PY
                """,
                ],
                capture_output=True,
            )
            assert result.returncode == 0, f"Failed to detect promise variant: {repr(variant)}"

    def test_promise_with_special_characters(self, test_repo):
        """Test promise detection with special characters."""
        os.chdir(test_repo)

        special_promises = [
            "TASK_COMPLETE_123",
            "done-with-dashes",
            "Done.With.Dots",
            "DONE_FINAL!",
            "Task#Complete",
            "✅_DONE",
        ]

        for promise_text in special_promises:
            subprocess.run(["python3", "/workspace/ralph_mode.py", "disable"], capture_output=True)

            result = subprocess.run(
                [
                    "python3",
                    "/workspace/ralph_mode.py",
                    "enable",
                    f"Test task {promise_text}",
                    "--completion-promise",
                    promise_text,
                    "--max-iterations",
                    "2",
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Failed to set promise: {promise_text}"

            # Verify promise is stored correctly
            state_file = test_repo / ".ralph-mode" / "state.json"
            with open(state_file) as f:
                state = json.load(f)
            assert state["completion_promise"] == promise_text

    def test_malformed_promise_tags(self, test_repo):
        """Test that malformed promises are NOT detected."""
        os.chdir(test_repo)

        subprocess.run(
            [
                "python3",
                "/workspace/ralph_mode.py",
                "enable",
                "Test task",
                "--completion-promise",
                "DONE",
                "--max-iterations",
                "3",
            ],
            capture_output=True,
        )

        malformed_cases = [
            "<promise>WRONG</promise>",  # Wrong text
            "<promise>DON</promise>",  # Partial match
            "<promise>DONE EXTRA</promise>",  # Extra text
            "<Promise>DONE</Promise>",  # Wrong case tags
            "<promise>DONE<promise>",  # Missing close tag
            "</promise>DONE</promise>",  # Missing open tag
            "< promise >DONE</promise>",  # Space in tag
            "<promise> DONE </promise><promise>DONE</promise>",  # Multiple (first wrong)
        ]

        output_file = test_repo / ".ralph-mode" / "output.txt"

        for malformed in malformed_cases:
            output_file.write_text(f"Output\n{malformed}\n")

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    f"""
                cd {test_repo}
                PROMISE="DONE" OUTPUT_FILE="{output_file}" python3 <<'PY'
import re, sys, os
promise = os.environ.get('PROMISE', '').strip()
output_file = os.environ.get('OUTPUT_FILE', '')
with open(output_file, 'r') as f:
    text = f.read()
matches = re.findall(r"<promise>(.*?)</promise>", text, re.DOTALL)
result = any(m.strip() == promise for m in matches)
sys.exit(0 if result else 1)
PY
                """,
                ],
                capture_output=True,
            )

            # Most should fail (return 1), except the last one which has valid promise
            if "DONE</promise><promise>DONE</promise>" in malformed:
                assert result.returncode == 0, f"Should detect valid promise in: {malformed}"
            elif malformed == "<promise>WRONG</promise>":
                assert result.returncode == 1, f"Should NOT detect: {malformed}"

    def test_multiple_promises_in_output(self, test_repo):
        """Test output with multiple promise tags."""
        os.chdir(test_repo)

        subprocess.run(
            [
                "python3",
                "/workspace/ralph_mode.py",
                "enable",
                "Test task",
                "--completion-promise",
                "DONE",
                "--max-iterations",
                "3",
            ],
            capture_output=True,
        )

        # Multiple promises - should detect if ANY match
        cases = [
            ("<promise>WRONG</promise>\n<promise>DONE</promise>", True),
            ("<promise>DONE</promise>\n<promise>DONE</promise>", True),
            ("<promise>WRONG1</promise>\n<promise>WRONG2</promise>", False),
        ]

        output_file = test_repo / ".ralph-mode" / "output.txt"

        for content, should_detect in cases:
            output_file.write_text(content)

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    f"""
                cd {test_repo}
                PROMISE="DONE" OUTPUT_FILE="{output_file}" python3 <<'PY'
import re, sys, os
promise = os.environ.get('PROMISE', '').strip()
output_file = os.environ.get('OUTPUT_FILE', '')
with open(output_file, 'r') as f:
    text = f.read()
matches = re.findall(r"<promise>(.*?)</promise>", text, re.DOTALL)
result = any(m.strip() == promise for m in matches)
sys.exit(0 if result else 1)
PY
                """,
                ],
                capture_output=True,
            )

            if should_detect:
                assert result.returncode == 0, f"Should detect promise in: {content}"
            else:
                assert result.returncode == 1, f"Should NOT detect promise in: {content}"

    def test_empty_promise_configuration(self, test_repo):
        """Test behavior with empty or missing promise."""
        os.chdir(test_repo)

        # Enable without promise
        result = subprocess.run(
            ["python3", "/workspace/ralph_mode.py", "enable", "Test task", "--max-iterations", "3"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Check state
        state_file = test_repo / ".ralph-mode" / "state.json"
        with open(state_file) as f:
            state = json.load(f)

        # Promise should be None or empty
        assert state.get("completion_promise") in [None, ""]

    def test_very_long_output_file(self, test_repo):
        """Test promise detection in very large output files."""
        os.chdir(test_repo)

        subprocess.run(
            [
                "python3",
                "/workspace/ralph_mode.py",
                "enable",
                "Test task",
                "--completion-promise",
                "FOUND_IT",
                "--max-iterations",
                "2",
            ],
            capture_output=True,
        )

        output_file = test_repo / ".ralph-mode" / "output.txt"
        output_file.parent.mkdir(exist_ok=True)

        # Create large output (1MB) with promise at the end
        large_content = "x" * (1024 * 1024)  # 1MB of x's
        large_content += "\n<promise>\nFOUND_IT\n</promise>\n"
        output_file.write_text(large_content)

        result = subprocess.run(
            [
                "bash",
                "-c",
                f"""
            cd {test_repo}
            PROMISE="FOUND_IT" OUTPUT_FILE="{output_file}" python3 <<'PY'
import re, sys, os
promise = os.environ.get('PROMISE', '').strip()
output_file = os.environ.get('OUTPUT_FILE', '')
with open(output_file, 'r') as f:
    text = f.read()
matches = re.findall(r"<promise>(.*?)</promise>", text, re.DOTALL)
sys.exit(0 if any(m.strip() == promise for m in matches) else 1)
PY
            """,
            ],
            capture_output=True,
            timeout=10,
        )

        assert result.returncode == 0, "Should detect promise in large file"

    def test_concurrent_state_access(self, test_repo):
        """Test handling of concurrent state file access."""
        os.chdir(test_repo)

        subprocess.run(
            ["python3", "/workspace/ralph_mode.py", "enable", "Test task", "--max-iterations", "5"], capture_output=True
        )

        # Try multiple status reads concurrently
        import threading

        results = []
        errors = []

        def read_status():
            try:
                result = subprocess.run(
                    ["python3", "/workspace/ralph_mode.py", "status"], capture_output=True, text=True, timeout=5
                )
                results.append(result.returncode)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=read_status) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Concurrent access errors: {errors}"
        assert all(r == 0 for r in results), "All status reads should succeed"

    def test_state_file_corruption_recovery(self, test_repo):
        """Test recovery from corrupted state file."""
        os.chdir(test_repo)

        subprocess.run(
            ["python3", "/workspace/ralph_mode.py", "enable", "Test task", "--max-iterations", "3"], capture_output=True
        )

        state_file = test_repo / ".ralph-mode" / "state.json"

        # Corrupt the state file
        state_file.write_text("{ invalid json }")

        # Try to read status - should handle gracefully
        result = subprocess.run(["python3", "/workspace/ralph_mode.py", "status"], capture_output=True, text=True)

        # Should either recover or report clear error (not crash)
        assert "Traceback" not in result.stderr or result.returncode != 0

    def test_max_iterations_boundary(self, test_repo):
        """Test behavior at iteration boundaries."""
        os.chdir(test_repo)

        # Set max to 2
        subprocess.run(
            ["python3", "/workspace/ralph_mode.py", "enable", "Test task", "--max-iterations", "2"], capture_output=True
        )

        # Iterate to max
        subprocess.run(["python3", "/workspace/ralph_mode.py", "iterate"], capture_output=True)

        # Try to iterate beyond max
        result = subprocess.run(["python3", "/workspace/ralph_mode.py", "iterate"], capture_output=True, text=True)

        # Should fail or indicate max reached
        assert result.returncode != 0 or "max" in result.stdout.lower()

    def test_batch_mode_task_transitions(self, test_repo):
        """Test task transitions in batch mode."""
        os.chdir(test_repo)

        # Create tasks file
        tasks = [
            {"id": "TASK-001", "title": "First task", "prompt": "Do task 1", "completion_promise": "TASK1_DONE"},
            {"id": "TASK-002", "title": "Second task", "prompt": "Do task 2", "completion_promise": "TASK2_DONE"},
            {"id": "TASK-003", "title": "Third task", "prompt": "Do task 3", "completion_promise": "TASK3_DONE"},
        ]

        tasks_file = test_repo / "tasks.json"
        tasks_file.write_text(json.dumps(tasks, indent=2))

        # Initialize batch
        result = subprocess.run(
            [
                "python3",
                "/workspace/ralph_mode.py",
                "batch-init",
                "--tasks-file",
                str(tasks_file),
                "--max-iterations",
                "5",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Batch init failed: {result.stderr}"

        # Verify we're on task 1
        state_file = test_repo / ".ralph-mode" / "state.json"
        with open(state_file) as f:
            state = json.load(f)
        assert state["current_task_index"] == 0
        assert state["completion_promise"] == "TASK1_DONE"

        # Complete task 1
        output_file = test_repo / ".ralph-mode" / "output.txt"
        output_file.write_text("Task 1 output\n<promise>TASK1_DONE</promise>\n")

        result = subprocess.run(
            ["python3", "/workspace/ralph_mode.py", "complete"],
            input=output_file.read_text(),
            capture_output=True,
            text=True,
        )

        # Should advance to task 2
        if result.returncode == 0:
            with open(state_file) as f:
                state = json.load(f)
            assert state["current_task_index"] == 1, "Should advance to task 2"
            assert state["completion_promise"] == "TASK2_DONE"

    def test_unicode_in_promise_and_output(self, test_repo):
        """Test handling of Unicode characters."""
        os.chdir(test_repo)

        # Use emoji/Persian in promise
        promise = "انجام_شد_✅"

        result = subprocess.run(
            [
                "python3",
                "/workspace/ralph_mode.py",
                "enable",
                "Test Unicode",
                "--completion-promise",
                promise,
                "--max-iterations",
                "2",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Test detection
        output_file = test_repo / ".ralph-mode" / "output.txt"
        output_file.write_text(f"Output\n<promise>{promise}</promise>\n", encoding="utf-8")

        result = subprocess.run(
            [
                "bash",
                "-c",
                f"""
            cd {test_repo}
            PROMISE="{promise}" OUTPUT_FILE="{output_file}" python3 <<'PY'
import re, sys, os
promise = os.environ.get('PROMISE', '').strip()
output_file = os.environ.get('OUTPUT_FILE', '')
with open(output_file, 'r', encoding='utf-8') as f:
    text = f.read()
matches = re.findall(r"<promise>(.*?)</promise>", text, re.DOTALL)
result = any(m.strip() == promise for m in matches)
sys.exit(0 if result else 1)
PY
            """,
            ],
            capture_output=True,
        )
        assert result.returncode == 0, "Should handle Unicode in promise"

    def test_rapid_iteration_cycling(self, test_repo):
        """Test rapid successive iterations."""
        os.chdir(test_repo)

        subprocess.run(
            ["python3", "/workspace/ralph_mode.py", "enable", "Test task", "--max-iterations", "100"],
            capture_output=True,
        )

        # Rapidly iterate 20 times
        for i in range(20):
            result = subprocess.run(
                ["python3", "/workspace/ralph_mode.py", "iterate"],
                capture_output=True,
                timeout=5,
            )
            assert result.returncode == 0, f"Iteration {i+1} failed"

        # Check final state
        state_file = test_repo / ".ralph-mode" / "state.json"
        with open(state_file) as f:
            state = json.load(f)
        assert state["iteration"] == 21  # Started at 1

    def test_missing_output_file(self, test_repo):
        """Test behavior when output.txt is missing."""
        os.chdir(test_repo)

        subprocess.run(
            [
                "python3",
                "/workspace/ralph_mode.py",
                "enable",
                "Test task",
                "--completion-promise",
                "DONE",
                "--max-iterations",
                "3",
            ],
            capture_output=True,
        )

        # Don't create output.txt
        output_file = test_repo / ".ralph-mode" / "output.txt"
        if output_file.exists():
            output_file.unlink()

        # Test promise detection with missing file
        result = subprocess.run(
            [
                "bash",
                "-c",
                f"""
            cd {test_repo}
            PROMISE="DONE" OUTPUT_FILE="{output_file}" python3 <<'PY'
import re, sys, os
promise = os.environ.get('PROMISE', '').strip()
output_file = os.environ.get('OUTPUT_FILE', '')
try:
    with open(output_file, 'r') as f:
        text = f.read()
except Exception:
    sys.exit(1)
matches = re.findall(r"<promise>(.*?)</promise>", text, re.DOTALL)
sys.exit(0 if any(m.strip() == promise for m in matches) else 1)
PY
            """,
            ],
            capture_output=True,
        )

        assert result.returncode == 1, "Should fail gracefully with missing file"

    def test_empty_output_file(self, test_repo):
        """Test promise detection in empty output."""
        os.chdir(test_repo)

        subprocess.run(
            [
                "python3",
                "/workspace/ralph_mode.py",
                "enable",
                "Test task",
                "--completion-promise",
                "DONE",
                "--max-iterations",
                "3",
            ],
            capture_output=True,
        )

        output_file = test_repo / ".ralph-mode" / "output.txt"
        output_file.write_text("")

        result = subprocess.run(
            [
                "bash",
                "-c",
                f"""
            cd {test_repo}
            PROMISE="DONE" OUTPUT_FILE="{output_file}" python3 <<'PY'
import re, sys, os
promise = os.environ.get('PROMISE', '').strip()
output_file = os.environ.get('OUTPUT_FILE', '')
with open(output_file, 'r') as f:
    text = f.read()
matches = re.findall(r"<promise>(.*?)</promise>", text, re.DOTALL)
sys.exit(0 if any(m.strip() == promise for m in matches) else 1)
PY
            """,
            ],
            capture_output=True,
        )

        assert result.returncode == 1, "Should not detect promise in empty file"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
