#!/usr/bin/env python3
"""
Performance Benchmark Tests for Copilot Ralph Mode
===================================================

Benchmark tests to measure performance characteristics.
Uses pytest-benchmark for accurate measurements.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ralph_mode import RalphMode, TaskLibrary


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def bench_workspace(tmp_path):
    """Create workspace for benchmarks."""
    return tmp_path


@pytest.fixture
def bench_ralph(bench_workspace):
    """Create RalphMode for benchmarks."""
    return RalphMode(bench_workspace)


# ═══════════════════════════════════════════════════════════════════════════════
# ENABLE/DISABLE BENCHMARKS
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnableBenchmarks:
    """Benchmark enable operation."""
    
    def test_enable_simple(self, benchmark, bench_workspace):
        """Benchmark simple enable."""
        def enable_disable():
            ralph = RalphMode(bench_workspace)
            ralph.enable("Test task")
            ralph.disable()
        
        benchmark(enable_disable)
    
    def test_enable_with_options(self, benchmark, bench_workspace):
        """Benchmark enable with all options."""
        def enable_disable():
            ralph = RalphMode(bench_workspace)
            ralph.enable(
                "Test task with options",
                max_iterations=100,
                completion_promise="DONE",
                model="gpt-5.2-codex",
                auto_agents=True
            )
            ralph.disable()
        
        benchmark(enable_disable)
    
    def test_enable_long_prompt(self, benchmark, bench_workspace):
        """Benchmark enable with very long prompt."""
        long_prompt = "Build a comprehensive " * 500  # ~10KB prompt
        
        def enable_disable():
            ralph = RalphMode(bench_workspace)
            ralph.enable(long_prompt)
            ralph.disable()
        
        benchmark(enable_disable)


# ═══════════════════════════════════════════════════════════════════════════════
# ITERATION BENCHMARKS
# ═══════════════════════════════════════════════════════════════════════════════


class TestIterateBenchmarks:
    """Benchmark iteration operations."""
    
    def test_single_iterate(self, benchmark, bench_workspace):
        """Benchmark single iteration."""
        ralph = RalphMode(bench_workspace)
        ralph.enable("Test", max_iterations=1000)
        
        def iterate():
            ralph.iterate()
        
        benchmark(iterate)
        ralph.disable()
    
    def test_iterate_100_times(self, benchmark, bench_workspace):
        """Benchmark 100 iterations."""
        def many_iterations():
            ralph = RalphMode(bench_workspace)
            ralph.enable("Test", max_iterations=200)
            for _ in range(100):
                ralph.iterate()
            ralph.disable()
        
        benchmark(many_iterations)


# ═══════════════════════════════════════════════════════════════════════════════
# STATE OPERATIONS BENCHMARKS
# ═══════════════════════════════════════════════════════════════════════════════


class TestStateBenchmarks:
    """Benchmark state operations."""
    
    def test_get_state(self, benchmark, bench_workspace):
        """Benchmark get_state."""
        ralph = RalphMode(bench_workspace)
        ralph.enable("Test")
        
        benchmark(ralph.get_state)
        ralph.disable()
    
    def test_save_state(self, benchmark, bench_workspace):
        """Benchmark save_state."""
        ralph = RalphMode(bench_workspace)
        ralph.enable("Test")
        state = ralph.get_state()
        
        benchmark(ralph.save_state, state)
        ralph.disable()
    
    def test_status(self, benchmark, bench_workspace):
        """Benchmark status call."""
        ralph = RalphMode(bench_workspace)
        ralph.enable("Test", max_iterations=50, completion_promise="DONE")
        
        benchmark(ralph.status)
        ralph.disable()


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLETION CHECK BENCHMARKS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompletionBenchmarks:
    """Benchmark completion checking."""
    
    def test_check_completion_short(self, benchmark, bench_workspace):
        """Benchmark completion check with short output."""
        ralph = RalphMode(bench_workspace)
        ralph.enable("Test", completion_promise="DONE")
        
        output = "<promise>DONE</promise>"
        benchmark(ralph.check_completion, output)
        ralph.disable()
    
    def test_check_completion_long(self, benchmark, bench_workspace):
        """Benchmark completion check with long output."""
        ralph = RalphMode(bench_workspace)
        ralph.enable("Test", completion_promise="DONE")
        
        # Long output with promise in middle
        output = "x" * 10000 + "<promise>DONE</promise>" + "y" * 10000
        benchmark(ralph.check_completion, output)
        ralph.disable()
    
    def test_check_completion_no_match(self, benchmark, bench_workspace):
        """Benchmark completion check that doesn't match."""
        ralph = RalphMode(bench_workspace)
        ralph.enable("Test", completion_promise="DONE")
        
        output = "Output without any promise tags at all" * 100
        benchmark(ralph.check_completion, output)
        ralph.disable()


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH MODE BENCHMARKS
# ═══════════════════════════════════════════════════════════════════════════════


class TestBatchBenchmarks:
    """Benchmark batch mode operations."""
    
    def test_init_batch_small(self, benchmark, bench_workspace):
        """Benchmark batch init with small task list."""
        tasks = [{"id": f"T{i}", "title": f"Task {i}", "prompt": f"Do {i}"} 
                 for i in range(5)]
        
        def init_batch():
            ralph = RalphMode(bench_workspace)
            ralph.init_batch(tasks, max_iterations=10)
            ralph.disable()
        
        benchmark(init_batch)
    
    def test_init_batch_large(self, benchmark, bench_workspace):
        """Benchmark batch init with large task list."""
        tasks = [{"id": f"T{i}", "title": f"Task {i}", "prompt": f"Do task number {i}"} 
                 for i in range(50)]
        
        def init_batch():
            ralph = RalphMode(bench_workspace)
            ralph.init_batch(tasks, max_iterations=10)
            ralph.disable()
        
        benchmark(init_batch)
    
    def test_next_task(self, benchmark, bench_workspace):
        """Benchmark next_task operation."""
        ralph = RalphMode(bench_workspace)
        tasks = [{"id": f"T{i}", "title": f"Task {i}", "prompt": f"Do {i}"} 
                 for i in range(100)]
        ralph.init_batch(tasks, max_iterations=1000)
        
        def next_task():
            try:
                ralph.next_task()
            except ValueError:
                # Re-init when we run out
                ralph.disable()
                ralph.init_batch(tasks, max_iterations=1000)
        
        benchmark(next_task)
        ralph.disable()


# ═══════════════════════════════════════════════════════════════════════════════
# TASK LIBRARY BENCHMARKS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTaskLibraryBenchmarks:
    """Benchmark TaskLibrary operations."""
    
    @pytest.fixture
    def large_task_library(self, bench_workspace):
        """Create a large task library."""
        tasks_dir = bench_workspace / "tasks"
        tasks_dir.mkdir()
        groups_dir = tasks_dir / "_groups"
        groups_dir.mkdir()
        
        # Create 100 tasks
        for i in range(100):
            content = f"""---
id: TASK-{i:03d}
title: Task Number {i}
tags: [test, tag{i % 10}]
---

This is the prompt for task {i}.
"""
            (tasks_dir / f"task-{i:03d}.md").write_text(content, encoding="utf-8")
        
        # Create 10 groups
        for g in range(10):
            group_tasks = [f"task-{i:03d}.md" for i in range(g * 10, (g + 1) * 10)]
            (groups_dir / f"group-{g}.json").write_text(json.dumps({
                "name": f"group-{g}",
                "title": f"Group {g}",
                "tasks": group_tasks
            }), encoding="utf-8")
        
        return TaskLibrary(bench_workspace)
    
    def test_list_tasks(self, benchmark, large_task_library):
        """Benchmark listing all tasks."""
        benchmark(large_task_library.list_tasks)
    
    def test_list_groups(self, benchmark, large_task_library):
        """Benchmark listing all groups."""
        benchmark(large_task_library.list_groups)
    
    def test_get_task_by_id(self, benchmark, large_task_library):
        """Benchmark getting task by ID."""
        benchmark(large_task_library.get_task, "TASK-050")
    
    def test_search_tasks(self, benchmark, large_task_library):
        """Benchmark searching tasks."""
        benchmark(large_task_library.search_tasks, "task")
    
    def test_get_group_tasks(self, benchmark, large_task_library):
        """Benchmark getting tasks in a group."""
        benchmark(large_task_library.get_group_tasks, "group-5")


# ═══════════════════════════════════════════════════════════════════════════════
# HISTORY BENCHMARKS
# ═══════════════════════════════════════════════════════════════════════════════


class TestHistoryBenchmarks:
    """Benchmark history operations."""
    
    def test_log_iteration(self, benchmark, bench_workspace):
        """Benchmark logging an iteration."""
        ralph = RalphMode(bench_workspace)
        ralph.enable("Test")
        
        benchmark(ralph.log_iteration, 1, "test", "Test notes")
        ralph.disable()
    
    def test_get_history_large(self, benchmark, bench_workspace):
        """Benchmark getting large history."""
        ralph = RalphMode(bench_workspace)
        ralph.enable("Test", max_iterations=1000)
        
        # Create large history
        for i in range(200):
            ralph.iterate()
        
        benchmark(ralph.get_history)
        ralph.disable()


# ═══════════════════════════════════════════════════════════════════════════════
# FILE I/O BENCHMARKS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFileIOBenchmarks:
    """Benchmark file I/O operations."""
    
    def test_save_prompt_small(self, benchmark, bench_workspace):
        """Benchmark saving small prompt."""
        ralph = RalphMode(bench_workspace)
        ralph.ralph_dir.mkdir(parents=True)
        
        benchmark(ralph.save_prompt, "Small prompt")
    
    def test_save_prompt_large(self, benchmark, bench_workspace):
        """Benchmark saving large prompt."""
        ralph = RalphMode(bench_workspace)
        ralph.ralph_dir.mkdir(parents=True)
        
        large_prompt = "x" * 100000  # 100KB
        benchmark(ralph.save_prompt, large_prompt)
    
    def test_get_prompt(self, benchmark, bench_workspace):
        """Benchmark getting prompt."""
        ralph = RalphMode(bench_workspace)
        ralph.enable("Test prompt")
        
        benchmark(ralph.get_prompt)
        ralph.disable()


# ═══════════════════════════════════════════════════════════════════════════════
# SLUGIFY BENCHMARKS
# ═══════════════════════════════════════════════════════════════════════════════


class TestSlugifyBenchmarks:
    """Benchmark _slugify function."""
    
    def test_slugify_simple(self, benchmark):
        """Benchmark slugify with simple input."""
        benchmark(RalphMode._slugify, "Simple Task Name")
    
    def test_slugify_complex(self, benchmark):
        """Benchmark slugify with complex input."""
        complex_text = "Complex!@#$%^&*() Task with Special Characters 123"
        benchmark(RalphMode._slugify, complex_text)
    
    def test_slugify_long(self, benchmark):
        """Benchmark slugify with long input."""
        long_text = "Task " * 100
        benchmark(RalphMode._slugify, long_text)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])
