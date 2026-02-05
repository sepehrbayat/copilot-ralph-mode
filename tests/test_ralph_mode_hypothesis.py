#!/usr/bin/env python3
"""
Property-Based Tests for Copilot Ralph Mode
=============================================

Using Hypothesis for property-based testing to discover edge cases
and ensure invariants hold across a wide range of inputs.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, assume, example
from hypothesis import strategies as st

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ralph_mode import RalphMode, TaskLibrary, VERSION


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════════

# Strategy for valid prompts
prompts = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Z"),
        whitelist_characters=" \n\t!@#$%^&*()[]{}|;:',.<>?/`~"
    ),
    min_size=0,
    max_size=10000
)

# Strategy for task IDs
task_ids = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=50
).filter(lambda x: x.strip() != "")

# Strategy for completion promises
completion_promises = st.one_of(
    st.none(),
    st.text(min_size=1, max_size=200).filter(lambda x: "<" not in x and ">" not in x)
)

# Strategy for max iterations
max_iterations = st.integers(min_value=0, max_value=10000)

# Strategy for task lists
task_dicts = st.fixed_dictionaries({
    "id": task_ids,
    "title": st.text(min_size=1, max_size=100),
    "prompt": prompts,
})

task_lists = st.lists(task_dicts, min_size=1, max_size=20)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTY-BASED TESTS - STATE INVARIANTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestStateInvariants:
    """Test that state invariants hold across all inputs."""
    
    @given(prompt=prompts, max_iter=max_iterations, promise=completion_promises)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_enable_creates_valid_state(self, temp_workspace, prompt, max_iter, promise):
        """Test that enable always creates a valid state."""
        ralph = RalphMode(temp_workspace)
        
        state = ralph.enable(prompt, max_iterations=max_iter, completion_promise=promise)
        
        # Invariants that must always hold
        assert state["active"] is True
        assert state["iteration"] == 1
        assert state["max_iterations"] == max_iter
        assert state["completion_promise"] == promise
        assert state["mode"] == "single"
        assert "started_at" in state
        assert "version" in state
        assert ralph.is_active()
        
        # Cleanup
        ralph.disable()
    
    @given(prompt=prompts)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_prompt_roundtrip(self, temp_workspace, prompt):
        """Test that prompts are stored and retrieved exactly."""
        ralph = RalphMode(temp_workspace)
        
        ralph.enable(prompt)
        retrieved = ralph.get_prompt()
        
        assert retrieved == prompt
        
        ralph.disable()
    
    @given(n=st.integers(min_value=1, max_value=100))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_iterate_always_increments(self, temp_workspace, n):
        """Test that iterate always increments the counter."""
        ralph = RalphMode(temp_workspace)
        ralph.enable("Test", max_iterations=n + 10)  # Ensure we have room
        
        for expected_iter in range(2, min(n + 2, 12)):  # Limit iterations for speed
            state = ralph.iterate()
            assert state["iteration"] == expected_iter
        
        ralph.disable()
    
    @given(max_iter=st.integers(min_value=1, max_value=10))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_max_iterations_enforced(self, temp_workspace, max_iter):
        """Test that max iterations is always enforced."""
        ralph = RalphMode(temp_workspace)
        ralph.enable("Test", max_iterations=max_iter)
        
        # Iterate until max
        for _ in range(max_iter - 1):
            ralph.iterate()
        
        # Next iterate should fail
        with pytest.raises(ValueError):
            ralph.iterate()
        
        # Should be disabled
        assert not ralph.is_active()


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTY-BASED TESTS - COMPLETION PROMISE
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompletionPromiseProperties:
    """Property-based tests for completion promise."""
    
    @given(promise=st.text(min_size=1, max_size=100).filter(lambda x: "<" not in x and ">" not in x))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_exact_promise_always_matches(self, temp_workspace, promise):
        """Test that exact promise always matches."""
        ralph = RalphMode(temp_workspace)
        ralph.enable("Test", completion_promise=promise)
        
        output = f"<promise>{promise}</promise>"
        assert ralph.check_completion(output)
        
        ralph.disable()
    
    @given(
        promise=st.text(min_size=1, max_size=50).filter(lambda x: "<" not in x and ">" not in x),
        wrong=st.text(min_size=1, max_size=50).filter(lambda x: "<" not in x and ">" not in x)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_wrong_promise_never_matches(self, temp_workspace, promise, wrong):
        """Test that wrong promise never matches."""
        assume(promise != wrong)
        
        ralph = RalphMode(temp_workspace)
        ralph.enable("Test", completion_promise=promise)
        
        output = f"<promise>{wrong}</promise>"
        assert not ralph.check_completion(output)
        
        ralph.disable()
    
    @given(
        promise=st.text(min_size=1, max_size=50).filter(lambda x: "<" not in x and ">" not in x),
        prefix=st.text(max_size=200),
        suffix=st.text(max_size=200)
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_promise_surrounded_by_text(self, temp_workspace, promise, prefix, suffix):
        """Test promise detection works with surrounding text."""
        ralph = RalphMode(temp_workspace)
        ralph.enable("Test", completion_promise=promise)
        
        output = f"{prefix}<promise>{promise}</promise>{suffix}"
        assert ralph.check_completion(output)
        
        ralph.disable()


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTY-BASED TESTS - BATCH MODE
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchModeProperties:
    """Property-based tests for batch mode."""
    
    @given(tasks=task_lists)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_batch_creates_correct_number_of_tasks(self, temp_workspace, tasks):
        """Test batch creates correct number of task files."""
        ralph = RalphMode(temp_workspace)
        
        state = ralph.init_batch(tasks, max_iterations=5)
        
        assert state["tasks_total"] == len(tasks)
        assert state["current_task_index"] == 0
        
        # Check task files created
        task_files = list(ralph.tasks_dir.glob("*.md"))
        assert len(task_files) == len(tasks)
        
        ralph.disable()
    
    @given(num_tasks=st.integers(min_value=1, max_value=10))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_next_task_advances_correctly(self, temp_workspace, num_tasks):
        """Test next_task advances through all tasks."""
        ralph = RalphMode(temp_workspace)
        
        tasks = [{"id": f"T{i}", "title": f"Task {i}", "prompt": f"Do {i}"} 
                 for i in range(num_tasks)]
        ralph.init_batch(tasks, max_iterations=100)
        
        for expected_index in range(1, num_tasks):
            state = ralph.next_task()
            assert state["current_task_index"] == expected_index
        
        # Next should fail (no more tasks)
        with pytest.raises(ValueError, match="All tasks completed"):
            ralph.next_task()
        
        assert not ralph.is_active()


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTY-BASED TESTS - SLUGIFY
# ═══════════════════════════════════════════════════════════════════════════════

class TestSlugifyProperties:
    """Property-based tests for slug generation."""
    
    @given(text=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_slugify_always_produces_valid_filename(self, text):
        """Test _slugify always produces filesystem-safe string."""
        slug = RalphMode._slugify(text)
        
        # Should only contain safe characters
        assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789-_." for c in slug)
        
        # Should not be empty
        assert len(slug) > 0
        
        # Should not start or end with dash
        assert not slug.startswith("-")
        assert not slug.endswith("-")
    
    @given(text=st.text(min_size=1, max_size=100, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")))
    @settings(max_examples=50)
    def test_slugify_preserves_alphanumeric(self, text):
        """Test _slugify preserves ASCII alphanumeric characters."""
        slug = RalphMode._slugify(text)
        
        # All original ASCII alphanumeric chars should be present (lowercase)
        for c in text:
            if c.isalnum() and c.isascii():
                assert c.lower() in slug


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTY-BASED TESTS - HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

class TestHistoryProperties:
    """Property-based tests for history logging."""
    
    @given(n_iterations=st.integers(min_value=0, max_value=20))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_history_grows_with_iterations(self, temp_workspace, n_iterations):
        """Test history grows correctly with iterations."""
        ralph = RalphMode(temp_workspace)
        ralph.enable("Test", max_iterations=n_iterations + 10)
        
        for _ in range(n_iterations):
            ralph.iterate()
        
        history = ralph.get_history()
        
        # Should have: 1 started + n iterations
        assert len(history) >= n_iterations + 1
        
        ralph.disable()
    
    @given(prompt=prompts)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_history_first_entry_is_started(self, temp_workspace, prompt):
        """Test first history entry is always 'started'."""
        ralph = RalphMode(temp_workspace)
        ralph.enable(prompt)
        
        history = ralph.get_history()
        
        assert len(history) >= 1
        assert history[0]["status"] == "started"
        
        ralph.disable()


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTY-BASED TESTS - TASK LIBRARY
# ═══════════════════════════════════════════════════════════════════════════════

# Strategy for task IDs that are safe for YAML (no leading zeros that collapse)
safe_task_ids = st.text(
    alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ-_"),
    min_size=1,
    max_size=20
).filter(lambda x: x.strip() != "" and not x.startswith("-") and not x.startswith("_"))


class TestTaskLibraryProperties:
    """Property-based tests for TaskLibrary."""
    
    @given(task_id=safe_task_ids, title=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "P"))), prompt=prompts)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_task_file_roundtrip(self, temp_workspace, task_id, title, prompt):
        """Test task file can be written and read back."""
        # Create tasks directory (use exist_ok for Hypothesis multiple examples)
        tasks_dir = temp_workspace / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        
        # Write task file with quoted ID to preserve string type
        content = f'''---
id: "{task_id}"
title: "{title}"
---

{prompt}
'''
        task_file = tasks_dir / f"{task_id.lower()}.md"
        task_file.write_text(content, encoding="utf-8")
        
        # Read it back
        library = TaskLibrary(temp_workspace)
        task = library.get_task(task_id)
        
        assert task is not None
        # Note: The simple YAML parser may convert numeric strings to integers
        # so we compare string representations
        assert str(task["id"]).strip('"') == str(task_id)


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTY-BASED TESTS - STATE PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════════

class TestStatePersistenceProperties:
    """Property-based tests for state persistence."""
    
    @given(
        prompt=prompts,
        max_iter=max_iterations,
        promise=completion_promises
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_state_survives_reload(self, temp_workspace, prompt, max_iter, promise):
        """Test state persists across RalphMode instances."""
        # Create and enable
        ralph1 = RalphMode(temp_workspace)
        ralph1.enable(prompt, max_iterations=max_iter, completion_promise=promise)
        
        # Create new instance pointing to same directory
        ralph2 = RalphMode(temp_workspace)
        
        # Should see same state
        assert ralph2.is_active()
        state = ralph2.get_state()
        assert state["max_iterations"] == max_iter
        assert state["completion_promise"] == promise
        
        # Cleanup
        ralph2.disable()
    
    @given(n=st.integers(min_value=1, max_value=10))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_iteration_persists_across_instances(self, temp_workspace, n):
        """Test iteration count persists across instances."""
        # Create and iterate
        ralph1 = RalphMode(temp_workspace)
        ralph1.enable("Test", max_iterations=100)
        
        for _ in range(n):
            ralph1.iterate()
        
        # New instance should see same iteration
        ralph2 = RalphMode(temp_workspace)
        state = ralph2.get_state()
        
        assert state["iteration"] == n + 1
        
        ralph2.disable()


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTY-BASED TESTS - JSON SERIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestJSONSerializationProperties:
    """Property-based tests for JSON serialization."""
    
    @given(
        prompt=st.text(min_size=0, max_size=1000),
        notes=st.text(min_size=0, max_size=500)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_json_roundtrip_for_state(self, temp_workspace, prompt, notes):
        """Test state can be serialized and deserialized."""
        ralph = RalphMode(temp_workspace)
        ralph.enable(prompt)
        
        # Log something with notes
        ralph.log_iteration(1, "test", notes)
        
        # Read state back
        state = ralph.get_state()
        
        # Should be valid JSON
        json_str = json.dumps(state)
        parsed = json.loads(json_str)
        
        assert parsed == state
        
        ralph.disable()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
