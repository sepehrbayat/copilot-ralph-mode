#!/usr/bin/env python3
"""Deep iteration flow tests for Ralph Mode."""

import shutil
import tempfile
from pathlib import Path

import pytest

from ralph_mode import RalphMode


def _new_ralph(tmp_path: Path) -> RalphMode:
    return RalphMode(tmp_path)


class TestIterationDeep:
    def test_iterate_progresses_and_persists_state(self, tmp_path: Path) -> None:
        ralph = _new_ralph(tmp_path)
        ralph.enable("Iterate test", max_iterations=5)

        for expected in range(2, 6):
            state = ralph.iterate()
            assert state["iteration"] == expected
            assert state.get("last_iterate_at")

        # Reload via new instance to ensure state persists and resumes correctly
        ralph_reload = _new_ralph(tmp_path)
        state = ralph_reload.get_state()
        assert state["iteration"] == 5
        assert ralph_reload.get_prompt() == "Iterate test"

    def test_iterate_disables_after_max_single(self, tmp_path: Path) -> None:
        ralph = _new_ralph(tmp_path)
        ralph.enable("Max iter", max_iterations=5)

        # reach max (iteration 5)
        for _ in range(4):
            ralph.iterate()

        with pytest.raises(ValueError):
            ralph.iterate()

        assert not ralph.is_active()

    def test_batch_max_iterations_advances_and_resets(self, tmp_path: Path) -> None:
        ralph = _new_ralph(tmp_path)
        tasks = [
            {"id": "T1", "title": "Task 1", "prompt": "Do 1", "completion_promise": "DONE1"},
            {"id": "T2", "title": "Task 2", "prompt": "Do 2", "completion_promise": "DONE2"},
        ]
        ralph.init_batch(tasks=tasks, max_iterations=5)

        # Reach max iterations for task 1
        for _ in range(4):
            ralph.iterate()

        state = ralph.iterate()  # should advance to task 2
        assert state["current_task_index"] == 1
        assert state["iteration"] == 1
        assert state["completion_promise"] == "DONE2"
        assert ralph.get_prompt() == "Do 2"

    def test_batch_complete_advances_and_keeps_history(self, tmp_path: Path) -> None:
        ralph = _new_ralph(tmp_path)
        tasks = [
            {"id": "T1", "title": "Task 1", "prompt": "Do 1", "completion_promise": "DONE1"},
            {"id": "T2", "title": "Task 2", "prompt": "Do 2", "completion_promise": "DONE2"},
        ]
        ralph.init_batch(tasks=tasks, max_iterations=5)

        assert ralph.complete("<promise>DONE1</promise>") is True

        state = ralph.get_state()
        assert state["current_task_index"] == 1
        assert state["iteration"] == 1
        assert state["completion_promise"] == "DONE2"

        history = ralph.get_history()
        assert any(h["status"] == "completed" for h in history)

    def test_iteration_resume_after_disable_requires_enable(self, tmp_path: Path) -> None:
        ralph = _new_ralph(tmp_path)
        ralph.enable("Resume test", max_iterations=5)
        ralph.iterate()
        ralph.disable()

        assert not ralph.is_active()
        assert ralph.get_state() is None

        # Fresh enable should start at iteration 1
        ralph.enable("Resume test", max_iterations=5)
        state = ralph.get_state()
        assert state["iteration"] == 1

    def test_batch_task_state_survives_reload(self, tmp_path: Path) -> None:
        ralph = _new_ralph(tmp_path)
        tasks = [
            {"id": "T1", "title": "Task 1", "prompt": "Do 1", "completion_promise": "DONE1"},
            {"id": "T2", "title": "Task 2", "prompt": "Do 2", "completion_promise": "DONE2"},
        ]
        ralph.init_batch(tasks=tasks, max_iterations=5)
        ralph.iterate()
        ralph.iterate()

        # Simulate process restart
        ralph_reload = _new_ralph(tmp_path)
        state = ralph_reload.get_state()
        assert state["current_task_index"] == 0
        assert state["iteration"] == 3
        assert ralph_reload.get_prompt() == "Do 1"

    def test_batch_final_task_completion_disables(self, tmp_path: Path) -> None:
        ralph = _new_ralph(tmp_path)
        tasks = [{"id": "T1", "title": "Task 1", "prompt": "Do 1", "completion_promise": "DONE1"}]
        ralph.init_batch(tasks=tasks, max_iterations=5)

        assert ralph.complete("<promise>DONE1</promise>") is True
        assert not ralph.is_active()

    def test_iteration_history_count(self, tmp_path: Path) -> None:
        ralph = _new_ralph(tmp_path)
        ralph.enable("History test", max_iterations=5)

        for _ in range(4):
            ralph.iterate()

        history = ralph.get_history()
        statuses = [h["status"] for h in history]
        assert statuses[0] == "started"
        assert statuses.count("iterate") == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
