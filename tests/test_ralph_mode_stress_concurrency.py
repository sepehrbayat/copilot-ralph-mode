#!/usr/bin/env python3
"""Stress and concurrency-focused tests for Ralph Mode."""

import threading
import time
from pathlib import Path

import pytest

from ralph_mode import RalphMode


class TestStressConcurrency:
    def test_status_reads_during_iterations(self, tmp_path: Path) -> None:
        ralph = RalphMode(tmp_path)
        ralph.enable("Concurrent status reads", max_iterations=50)

        errors = []
        stop = threading.Event()

        def reader() -> None:
            while not stop.is_set():
                try:
                    status = ralph.status()
                    assert status is None or "iteration" in status
                except Exception as exc:  # pragma: no cover - explicit for robustness
                    errors.append(str(exc))
                time.sleep(0.01)

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()

        for _ in range(10):
            ralph.iterate()

        stop.set()
        for t in threads:
            t.join(timeout=2)

        assert not errors, f"Concurrent status reads failed: {errors}"

    def test_iteration_resume_after_restart_mid_task(self, tmp_path: Path) -> None:
        ralph = RalphMode(tmp_path)
        ralph.enable("Resume after restart", max_iterations=10)
        ralph.iterate()
        ralph.iterate()

        # Simulate restart
        ralph_reloaded = RalphMode(tmp_path)
        state = ralph_reloaded.get_state()
        assert state["iteration"] == 3

        # Continue iterating
        state = ralph_reloaded.iterate()
        assert state["iteration"] == 4

    def test_batch_resume_and_complete_after_restart(self, tmp_path: Path) -> None:
        ralph = RalphMode(tmp_path)
        tasks = [
            {"id": "R1", "title": "Task 1", "prompt": "Do 1", "completion_promise": "DONE1"},
            {"id": "R2", "title": "Task 2", "prompt": "Do 2", "completion_promise": "DONE2"},
        ]
        ralph.init_batch(tasks=tasks, max_iterations=5)
        ralph.iterate()

        # Simulate restart
        ralph_reloaded = RalphMode(tmp_path)
        state = ralph_reloaded.get_state()
        assert state["current_task_index"] == 0
        assert state["completion_promise"] == "DONE1"

        # Complete task 1 after restart
        assert ralph_reloaded.complete("<promise>DONE1</promise>") is True
        state = ralph_reloaded.get_state()
        assert state["current_task_index"] == 1
        assert state["completion_promise"] == "DONE2"

    def test_recover_after_state_corruption(self, tmp_path: Path) -> None:
        ralph = RalphMode(tmp_path)
        ralph.enable("Corruption recovery", max_iterations=3)
        ralph.iterate()

        # Corrupt state.json
        ralph.state_file.write_text("{ invalid json", encoding="utf-8")

        # New instance should fail gracefully
        ralph_reloaded = RalphMode(tmp_path)
        assert ralph_reloaded.get_state() is None
        with pytest.raises(ValueError):
            ralph_reloaded.iterate()

        # Clean up by disabling and re-enabling
        if ralph_reloaded.ralph_dir.exists():
            ralph_reloaded.disable()
        ralph_reloaded.enable("Corruption recovery", max_iterations=3)
        assert ralph_reloaded.get_state()["iteration"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
