#!/usr/bin/env python3
"""
Test suite for MemoryStore (mem0-inspired multi-level memory system).

Tests cover:
- CRUD operations (add, get, update, delete, get_all)
- Deduplication (hash-based and keyword overlap)
- Search with scoring (keyword, recency, category, access)
- Memory types (working, episodic, semantic, procedural)
- Categories (file_changes, errors, decisions, etc.)
- Bulk operations (add_many)
- Extraction from output (extract_from_output)
- Fact extraction (extract_facts)
- Memory promotion (episodic → semantic)
- Temporal decay (apply_decay)
- Context formatting (format_for_context)
- Statistics (stats)
- Reset operations (full and per-type)
- Edge cases and error handling
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ralph_mode import ContextManager, MemoryStore, RalphMode

# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def temp_dir():
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def ralph(temp_dir):
    return RalphMode(temp_dir)


@pytest.fixture
def active_ralph(ralph):
    ralph.enable("Build unit tests for MemoryStore")
    return ralph


@pytest.fixture
def mem(active_ralph):
    return MemoryStore(active_ralph)


@pytest.fixture
def ctx(active_ralph):
    return ContextManager(active_ralph)


# ═══════════════════════════════════════════════════════════════════
# CRUD Tests
# ═══════════════════════════════════════════════════════════════════


class TestMemoryAdd:
    def test_add_basic(self, mem):
        result = mem.add("test memory content")
        assert result["event"] == "ADD"
        assert "id" in result

    def test_add_returns_memory_content(self, mem):
        result = mem.add("hello world")
        assert result["memory"] == "hello world"

    def test_add_with_type(self, mem):
        result = mem.add("working note", memory_type=mem.WORKING)
        assert result["event"] == "ADD"
        got = mem.get(result["id"])
        assert got is not None
        assert got["memory_type"] == "working"

    def test_add_with_category(self, mem):
        result = mem.add("error found", category="errors")
        got = mem.get(result["id"])
        assert got["category"] == "errors"

    def test_add_with_metadata(self, mem):
        result = mem.add("note", metadata={"source": "test"})
        got = mem.get(result["id"])
        assert got["metadata"] == {"source": "test"}

    def test_add_empty_content_skipped(self, mem):
        result = mem.add("")
        assert result["event"] == "SKIP"

    def test_add_whitespace_only_skipped(self, mem):
        result = mem.add("   \n  ")
        assert result["event"] == "SKIP"

    def test_add_strips_whitespace(self, mem):
        result = mem.add("  hello  ")
        got = mem.get(result["id"])
        assert got["content"] == "hello"

    def test_add_sets_iteration(self, mem):
        result = mem.add("note", iteration=5)
        got = mem.get(result["id"])
        assert got["iteration"] == 5

    def test_add_sets_score(self, mem):
        result = mem.add("note")
        got = mem.get(result["id"])
        assert got["score"] == 1.0

    def test_add_sets_access_count(self, mem):
        result = mem.add("note")
        got = mem.get(result["id"])
        assert got["access_count"] == 0


class TestMemoryDeduplication:
    def test_exact_duplicate_skipped(self, mem):
        r1 = mem.add("exact same content")
        r2 = mem.add("exact same content")
        assert r1["event"] == "ADD"
        assert r2["event"] == "SKIP"

    def test_high_overlap_duplicate_skipped(self, mem):
        r1 = mem.add("this is a very specific error message about authentication", category="errors")
        r2 = mem.add("this is a very specific error message about authentication failure", category="errors")
        # Should be deduplicated due to >85% keyword overlap in same category
        assert r1["event"] == "ADD"
        assert r2["event"] == "SKIP"

    def test_different_content_not_deduplicated(self, mem):
        r1 = mem.add("file_a.py was modified")
        r2 = mem.add("completely different topic about testing")
        assert r1["event"] == "ADD"
        assert r2["event"] == "ADD"

    def test_deduplicate_false_allows_duplicates(self, mem):
        r1 = mem.add("same content")
        r2 = mem.add("same content", deduplicate=False)
        assert r1["event"] == "ADD"
        assert r2["event"] == "ADD"

    def test_same_content_different_type_not_deduplicated(self, mem):
        r1 = mem.add("note about files", memory_type=mem.EPISODIC)
        r2 = mem.add("note about files", memory_type=mem.SEMANTIC)
        assert r1["event"] == "ADD"
        assert r2["event"] == "ADD"


class TestMemoryGet:
    def test_get_existing(self, mem):
        r = mem.add("findme")
        got = mem.get(r["id"])
        assert got is not None
        assert got["content"] == "findme"

    def test_get_nonexistent(self, mem):
        assert mem.get("nonexistent-id") is None

    def test_get_across_types(self, mem):
        r1 = mem.add("working", memory_type=mem.WORKING)
        r2 = mem.add("semantic", memory_type=mem.SEMANTIC)
        assert mem.get(r1["id"])["content"] == "working"
        assert mem.get(r2["id"])["content"] == "semantic"


class TestMemoryGetAll:
    def test_get_all_empty(self, mem):
        assert mem.get_all() == []

    def test_get_all_returns_added(self, mem):
        mem.add("one")
        mem.add("two")
        mem.add("three")
        all_mems = mem.get_all()
        assert len(all_mems) == 3

    def test_get_all_filter_by_type(self, mem):
        mem.add("w1", memory_type=mem.WORKING)
        mem.add("e1", memory_type=mem.EPISODIC)
        mem.add("e2", memory_type=mem.EPISODIC)
        result = mem.get_all(memory_type=mem.EPISODIC)
        assert len(result) == 2

    def test_get_all_filter_by_category(self, mem):
        mem.add("err1", category="errors")
        mem.add("prog1", category="progress")
        mem.add("err2", category="errors")
        result = mem.get_all(category="errors")
        assert len(result) == 2

    def test_get_all_limit(self, mem):
        for i in range(10):
            mem.add(f"memory number {i}", deduplicate=False)
        result = mem.get_all(limit=3)
        assert len(result) == 3

    def test_get_all_sorted_by_recency(self, mem):
        mem.add("first")
        mem.add("second")
        mem.add("third")
        result = mem.get_all()
        # Most recent first
        assert result[0]["content"] == "third"


class TestMemoryUpdate:
    def test_update_content(self, mem):
        r = mem.add("original")
        result = mem.update(r["id"], "updated")
        assert result["event"] == "UPDATE"
        assert result["old_memory"] == "original"
        assert result["memory"] == "updated"
        got = mem.get(r["id"])
        assert got["content"] == "updated"

    def test_update_nonexistent(self, mem):
        result = mem.update("nonexistent-id", "new content")
        assert result["event"] == "SKIP"

    def test_update_changes_hash(self, mem):
        r = mem.add("before")
        old_hash = mem.get(r["id"])["hash"]
        mem.update(r["id"], "after")
        new_hash = mem.get(r["id"])["hash"]
        assert old_hash != new_hash


class TestMemoryDelete:
    def test_delete_existing(self, mem):
        r = mem.add("to be deleted")
        result = mem.delete(r["id"])
        assert result["event"] == "DELETE"
        assert mem.get(r["id"]) is None

    def test_delete_nonexistent(self, mem):
        result = mem.delete("nonexistent-id")
        assert result["event"] == "SKIP"

    def test_delete_only_target(self, mem):
        r1 = mem.add("keep this")
        r2 = mem.add("delete this")
        mem.delete(r2["id"])
        assert mem.get(r1["id"]) is not None
        assert mem.get(r2["id"]) is None


# ═══════════════════════════════════════════════════════════════════
# Search Tests
# ═══════════════════════════════════════════════════════════════════


class TestMemorySearch:
    def test_search_basic(self, mem):
        mem.add("authentication error in login module")
        mem.add("database connection timeout")
        mem.add("CSS styling for sidebar component")
        result = mem.search("authentication login")
        assert len(result["results"]) > 0
        # First result should be the auth-related memory
        assert "authentication" in result["results"][0]["content"]

    def test_search_empty_query(self, mem):
        mem.add("something")
        result = mem.search("")
        # Empty query should still work (returns based on other scoring factors)
        assert "results" in result

    def test_search_no_results(self, mem):
        mem.add("python programming")
        result = mem.search("xyznonexistent", threshold=0.5)
        assert len(result["results"]) == 0

    def test_search_limit(self, mem):
        for i in range(20):
            mem.add(f"memory about testing iteration {i}", deduplicate=False)
        result = mem.search("testing iteration", limit=5)
        assert len(result["results"]) <= 5

    def test_search_by_type(self, mem):
        mem.add("working note", memory_type=mem.WORKING)
        mem.add("episodic note", memory_type=mem.EPISODIC)
        result = mem.search("note", memory_type=mem.WORKING)
        for r in result["results"]:
            assert r["memory_type"] == "working"

    def test_search_by_category(self, mem):
        mem.add("error in auth", category="errors")
        mem.add("progress on auth", category="progress")
        result = mem.search("auth", category="errors")
        for r in result["results"]:
            assert r["category"] == "errors"

    def test_search_scores_sorted(self, mem):
        mem.add("relevant query match here")
        mem.add("something completely different unrelated")
        result = mem.search("relevant query match")
        if len(result["results"]) > 1:
            for i in range(len(result["results"]) - 1):
                assert result["results"][i]["score"] >= result["results"][i + 1]["score"]

    def test_search_exact_match_bonus(self, mem):
        mem.add("fix the authentication bug in login module")
        mem.add("authentication improvements needed for security")
        result = mem.search("fix the authentication bug")
        # The one with exact substring match should score higher
        assert result["results"][0]["content"].startswith("fix the authentication")

    def test_search_category_boost(self, mem):
        mem.add("error in test runner output", category="errors")
        mem.add("error in test runner output duplicate", category="progress")
        result = mem.search("errors test runner")
        # The one with matching category should get a boost
        if len(result["results"]) >= 2:
            error_mem = [r for r in result["results"] if r["category"] == "errors"]
            assert len(error_mem) > 0


# ═══════════════════════════════════════════════════════════════════
# Extraction Tests
# ═══════════════════════════════════════════════════════════════════


class TestExtractFromOutput:
    def test_extract_file_changes(self, mem):
        output = "I created file src/utils.py and modified tests/test_main.py"
        results = mem.extract_from_output(output, iteration=1)
        # Should extract file_changes memory
        file_mems = [
            r
            for r in results
            if r.get("category") == "file_changes" or (isinstance(r, dict) and r.get("event") != "SKIP")
        ]
        assert len(file_mems) > 0

    def test_extract_errors(self, mem):
        output = "Error: ModuleNotFoundError: No module named 'requests'"
        results = mem.extract_from_output(output, iteration=1)
        error_mems = [r for r in results if isinstance(r, dict)]
        assert len(error_mems) > 0

    def test_extract_test_results(self, mem):
        output = "pytest: 42 passed, 3 failed"
        results = mem.extract_from_output(output, iteration=1)
        assert len(results) > 0

    def test_extract_completion_signal(self, mem):
        output = "Everything is done. <promise>COMPLETE</promise>"
        results = mem.extract_from_output(output, iteration=1)
        completion = [
            r
            for r in results
            if isinstance(r, dict) and r.get("event") == "ADD" and "promise" in r.get("memory", "").lower()
        ]
        assert len(completion) > 0

    def test_extract_git_operations(self, mem):
        output = "Running git commit -m 'fix test failures'"
        results = mem.extract_from_output(output, iteration=1)
        assert len(results) > 0

    def test_extract_empty_output(self, mem):
        results = mem.extract_from_output("", iteration=1)
        assert results == []


class TestExtractFacts:
    def test_extract_dependency_fact(self, mem):
        text = "The project uses React and TypeScript for the frontend"
        results = mem.extract_facts(text, iteration=1)
        assert len(results) > 0

    def test_extract_decision_fact(self, mem):
        text = "We decided to use PostgreSQL instead of MySQL for performance"
        results = mem.extract_facts(text, iteration=1)
        assert len(results) > 0

    def test_extract_fix_pattern(self, mem):
        text = "To fix the import error, you need to install the missing package first"
        results = mem.extract_facts(text, iteration=1)
        assert len(results) > 0

    def test_extract_empty_text(self, mem):
        results = mem.extract_facts("", iteration=1)
        assert results == []


# ═══════════════════════════════════════════════════════════════════
# Promotion Tests
# ═══════════════════════════════════════════════════════════════════


class TestPromoteMemories:
    def test_promote_basic(self, mem):
        # Add episodic memories with access count >= 2
        r = mem.add("frequently accessed pattern", memory_type=mem.EPISODIC)
        # Manually bump access count
        mems = mem._read_all(mem.EPISODIC)
        for m in mems:
            if m["id"] == r["id"]:
                m["access_count"] = 3
        mem._write_all(mem.EPISODIC, mems)

        promoted = mem.promote_memories(min_access=2)
        assert len(promoted) > 0
        # The memory should now exist in semantic store too
        semantic = mem.get_all(memory_type=mem.SEMANTIC)
        assert len(semantic) > 0

    def test_promote_nothing_if_low_access(self, mem):
        mem.add("rarely accessed", memory_type=mem.EPISODIC)
        promoted = mem.promote_memories(min_access=5)
        assert len(promoted) == 0

    def test_promote_empty_store(self, mem):
        promoted = mem.promote_memories()
        assert promoted == []


# ═══════════════════════════════════════════════════════════════════
# Decay Tests
# ═══════════════════════════════════════════════════════════════════


class TestApplyDecay:
    def test_decay_reduces_old_scores(self, active_ralph, mem):
        # Add memory at iteration 1
        mem.add("old memory content", memory_type=mem.EPISODIC, iteration=1)
        # Advance iteration to 5
        for _ in range(4):
            active_ralph.iterate()
        count = mem.apply_decay()
        assert count > 0
        # Score should be reduced
        mems = mem.get_all(memory_type=mem.EPISODIC)
        assert mems[0]["score"] < 1.0

    def test_decay_preserves_minimum(self, active_ralph, mem):
        mem.add("very old memory", memory_type=mem.EPISODIC, iteration=1)
        # Advance many iterations
        for _ in range(50):
            active_ralph.iterate()
        mem.apply_decay()
        mems = mem.get_all(memory_type=mem.EPISODIC)
        assert mems[0]["score"] >= 0.1  # minimum floor

    def test_decay_empty_store(self, mem):
        count = mem.apply_decay()
        assert count == 0


# ═══════════════════════════════════════════════════════════════════
# Format for Context Tests
# ═══════════════════════════════════════════════════════════════════


class TestFormatForContext:
    def test_format_empty(self, mem):
        result = mem.format_for_context()
        assert result == ""

    def test_format_working_memory(self, mem):
        mem.add("current focus: fixing tests", memory_type=mem.WORKING)
        result = mem.format_for_context()
        assert "Working Memory" in result
        assert "fixing tests" in result

    def test_format_episodic_memory(self, mem):
        mem.add("iteration 1: created auth module", memory_type=mem.EPISODIC)
        result = mem.format_for_context()
        assert "Episodic Memory" in result
        assert "auth module" in result

    def test_format_semantic_memory(self, mem):
        mem.add("React uses JSX syntax", memory_type=mem.SEMANTIC, category="patterns")
        result = mem.format_for_context()
        assert "Semantic Memory" in result

    def test_format_procedural_memory(self, mem):
        mem.add("to deploy: run npm build then npm publish", memory_type=mem.PROCEDURAL)
        result = mem.format_for_context()
        assert "Procedural Memory" in result

    def test_format_with_query(self, mem):
        mem.add("authentication uses JWT tokens", memory_type=mem.EPISODIC)
        mem.add("database uses PostgreSQL", memory_type=mem.EPISODIC)
        result = mem.format_for_context(query="authentication JWT")
        # Should include auth-related memory with higher relevance
        assert "authentication" in result.lower() or "jwt" in result.lower()

    def test_format_contains_memory_bank_header(self, mem):
        mem.add("some content")
        result = mem.format_for_context()
        assert result.startswith("## Memory Bank")

    def test_format_respects_limits(self, mem):
        for i in range(30):
            mem.add(f"episodic memory number {i}", memory_type=mem.EPISODIC, deduplicate=False)
        result = mem.format_for_context(max_episodic=5)
        # Should limit number of episodic memories shown
        lines = [l for l in result.splitlines() if l.strip().startswith("- ")]
        assert len(lines) <= 10  # generous bound (5 per section)


# ═══════════════════════════════════════════════════════════════════
# Statistics Tests
# ═══════════════════════════════════════════════════════════════════


class TestStats:
    def test_stats_empty(self, mem):
        st = mem.stats()
        assert st["total"] == 0

    def test_stats_counts(self, mem):
        mem.add("w1", memory_type=mem.WORKING)
        mem.add("e1", memory_type=mem.EPISODIC)
        mem.add("e2", memory_type=mem.EPISODIC)
        mem.add("s1", memory_type=mem.SEMANTIC)
        st = mem.stats()
        assert st["total"] == 4
        assert st["working"] == 1
        assert st["episodic"] == 2
        assert st["semantic"] == 1
        assert st["procedural"] == 0

    def test_stats_categories(self, mem):
        mem.add("err1", category="errors")
        mem.add("err2", category="errors")
        mem.add("prog1", category="progress")
        st = mem.stats()
        assert st["categories"]["errors"] == 2
        assert st["categories"]["progress"] == 1


# ═══════════════════════════════════════════════════════════════════
# Reset Tests
# ═══════════════════════════════════════════════════════════════════


class TestReset:
    def test_reset_all(self, mem):
        mem.add("w", memory_type=mem.WORKING)
        mem.add("e", memory_type=mem.EPISODIC)
        mem.add("s", memory_type=mem.SEMANTIC)
        mem.add("p", memory_type=mem.PROCEDURAL)
        mem.reset()
        assert mem.stats()["total"] == 0

    def test_reset_specific_type(self, mem):
        mem.add("w", memory_type=mem.WORKING)
        mem.add("e", memory_type=mem.EPISODIC)
        mem.reset(memory_type=mem.WORKING)
        assert mem.stats()["working"] == 0
        assert mem.stats()["episodic"] == 1

    def test_reset_idempotent(self, mem):
        mem.reset()
        mem.reset()  # Should not error
        assert mem.stats()["total"] == 0


# ═══════════════════════════════════════════════════════════════════
# Bulk Operations
# ═══════════════════════════════════════════════════════════════════


class TestAddMany:
    def test_add_many_strings(self, mem):
        results = mem.add_many(["first", "second", "third"])
        assert len(results) == 3
        assert all(r["event"] == "ADD" for r in results)

    def test_add_many_dicts(self, mem):
        results = mem.add_many(
            [
                {"content": "error happened", "category": "errors"},
                {"content": "test passed", "category": "test_results"},
            ]
        )
        assert len(results) == 2

    def test_add_many_empty(self, mem):
        results = mem.add_many([])
        assert results == []


# ═══════════════════════════════════════════════════════════════════
# History Tests
# ═══════════════════════════════════════════════════════════════════


class TestHistory:
    def test_history_existing(self, mem):
        r = mem.add("trackable")
        hist = mem.history(r["id"])
        assert len(hist) == 1
        assert hist[0]["memory"] == "trackable"

    def test_history_nonexistent(self, mem):
        hist = mem.history("nope")
        assert hist == []


# ═══════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_memory_dir_created(self, mem):
        mem.add("trigger dir creation")
        assert mem.memory_dir.exists()

    def test_jsonl_persistence(self, active_ralph):
        mem1 = MemoryStore(active_ralph)
        mem1.add("persistent memory", memory_type=MemoryStore.SEMANTIC)
        # Create new store pointing at same dir
        mem2 = MemoryStore(active_ralph)
        mems = mem2.get_all(memory_type=MemoryStore.SEMANTIC)
        assert len(mems) == 1
        assert mems[0]["content"] == "persistent memory"

    def test_corrupted_jsonl_line_skipped(self, mem):
        # Add a valid memory
        mem.add("valid", memory_type=mem.EPISODIC)
        # Corrupt the file by appending bad JSON
        path = mem._stores[mem.EPISODIC]
        with open(path, "a") as f:
            f.write("THIS IS NOT JSON\n")
        # Should still read the valid memory
        mems = mem._read_all(mem.EPISODIC)
        assert len(mems) == 1
        assert mems[0]["content"] == "valid"

    def test_max_memories_enforced(self, mem):
        original_max = mem.MAX_MEMORIES_PER_TYPE
        mem.MAX_MEMORIES_PER_TYPE = 5
        try:
            for i in range(10):
                mem.add(f"overflow memory number {i}", deduplicate=False)
            mems = mem._read_all(mem.EPISODIC)
            assert len(mems) <= 5
        finally:
            mem.MAX_MEMORIES_PER_TYPE = original_max

    def test_special_characters_in_content(self, mem):
        special = "quotes \"here\" and 'there' and\nnewlines\ttabs"
        r = mem.add(special)
        got = mem.get(r["id"])
        assert got["content"] == special

    def test_unicode_content(self, mem):
        r = mem.add("متن فارسی 🎯 日本語テスト")
        got = mem.get(r["id"])
        assert "فارسی" in got["content"]
        assert "🎯" in got["content"]

    def test_tokenize_basic(self, mem):
        tokens = mem._tokenize("Hello World test")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens

    def test_tokenize_filters_short(self, mem):
        tokens = mem._tokenize("a bb ccc dddd")
        assert "a" not in tokens
        assert "bb" not in tokens
        assert "ccc" in tokens
        assert "dddd" in tokens

    def test_hash_deterministic(self, mem):
        h1 = mem._hash("test content")
        h2 = mem._hash("test content")
        assert h1 == h2

    def test_hash_different_inputs(self, mem):
        h1 = mem._hash("content A")
        h2 = mem._hash("content B")
        assert h1 != h2
