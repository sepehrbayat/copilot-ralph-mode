"""mem0-inspired multi-level memory system for Ralph Mode.

Inspired by mem0ai/mem0 (https://github.com/mem0ai/mem0), this implements
a lightweight, zero-dependency memory layer that mirrors mem0's core
architecture:

  ┌────────────────────┐
  │  Working Memory    │  Current iteration state, tool output, focus
  │  (short-term)      │  Discarded each iteration; rebuilt from output
  ├────────────────────┤
  │  Episodic Memory   │  Per-iteration summaries — what happened, what
  │  (session)         │  changed, what failed. Promotes to long-term.
  ├────────────────────┤
  │  Semantic Memory   │  Extracted facts, patterns, relationships between
  │  (long-term)       │  files/concepts.  Survives across tasks.
  ├────────────────────┤
  │  Procedural Memory │  Learned workflows — "to fix X, run Y then Z".
  │  (long-term)       │  Built from repeated iteration patterns.
  └────────────────────┘

Storage: JSONL files in .ralph-mode/memory/
Search:  TF-IDF-like keyword overlap + recency decay + category boost
No external dependencies (no embeddings, no vector DB).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid as _uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .state import RalphMode


class MemoryStore:
    """mem0-inspired multi-level memory store for Ralph Mode.

    Provides: add, search, update, delete, get, get_all, history, decay, reset.
    All state lives in JSONL files — no DB, no embeddings, no network.
    """

    # Memory types (mirrors mem0 MemoryType enum)
    WORKING = "working"  # short-term, per-iteration scratch
    EPISODIC = "episodic"  # per-iteration summaries
    SEMANTIC = "semantic"  # extracted facts & relationships
    PROCEDURAL = "procedural"  # learned workflows & patterns

    # Categories (inspired by openclaw mem0 plugin)
    CATEGORIES = [
        "file_changes",  # which files were modified and how
        "errors",  # errors encountered and resolutions
        "decisions",  # choices made during the task
        "blockers",  # outstanding blockers or unknowns
        "progress",  # task completion milestones
        "patterns",  # repeated code patterns observed
        "dependencies",  # import/package dependencies touched
        "test_results",  # test runs and outcomes
        "environment",  # env setup, paths, config
        "task_context",  # info about the current task scope
    ]

    # Scoring weights
    RECENCY_DECAY = 0.05  # per-iteration decay factor
    CATEGORY_BOOST = 0.15  # bonus when category matches query
    KEYWORD_WEIGHT = 1.0  # base keyword overlap weight
    EXACT_MATCH_BONUS = 0.3  # bonus for exact substring match
    CATEGORY_PRIORITY: Dict[str, float] = {
        "errors": 1.15,
        "blockers": 1.1,
        "test_results": 1.05,
        "file_changes": 1.05,
        "decisions": 1.05,
        "dependencies": 1.0,
        "progress": 1.0,
        "patterns": 0.95,
        "environment": 0.95,
        "task_context": 0.9,
    }

    # Limits
    MAX_MEMORIES_PER_TYPE = 500
    MAX_SEARCH_RESULTS = 20
    DEFAULT_SEARCH_LIMIT = 10

    def __init__(self, ralph: RalphMode) -> None:
        self.ralph = ralph
        self.memory_dir = ralph.ralph_dir / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # Separate files per memory type (like mem0's multi-store)
        self._stores = {
            self.WORKING: self.memory_dir / "working.jsonl",
            self.EPISODIC: self.memory_dir / "episodic.jsonl",
            self.SEMANTIC: self.memory_dir / "semantic.jsonl",
            self.PROCEDURAL: self.memory_dir / "procedural.jsonl",
        }

    # ── Core CRUD (mirrors mem0 MemoryBase) ─────────────────────────

    def add(
        self,
        content: str,
        *,
        memory_type: str = "episodic",
        category: str = "progress",
        metadata: Optional[Dict[str, Any]] = None,
        iteration: Optional[int] = None,
        deduplicate: bool = True,
    ) -> Dict[str, Any]:
        """Add a memory.  Returns the created memory dict.

        If deduplicate=True, skips adding if a very similar memory exists
        (same hash or >90% keyword overlap within same type+category).
        """
        if not content or not content.strip():
            return {"event": "SKIP", "reason": "empty content"}

        content = content.strip()
        content_hash = self._hash(content)
        normalized_hash = self._hash(self._normalize_content(content))

        # Deduplication (mem0 does this via embedding similarity)
        if deduplicate:
            existing = self._find_duplicate(content_hash, content, memory_type, category)
            if existing:
                return {"event": "SKIP", "id": existing["id"], "reason": "duplicate"}

        memory = {
            "id": str(_uuid.uuid4()),
            "content": content,
            "hash": content_hash,
            "normalized_hash": normalized_hash,
            "memory_type": memory_type,
            "category": category,
            "metadata": metadata or {},
            "iteration": iteration or self._current_iteration(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "access_count": 0,
            "score": 1.0,
        }

        self._append(memory_type, memory)
        return {"event": "ADD", "id": memory["id"], "memory": content}

    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get a single memory by ID."""
        for mtype in self._stores:
            for m in self._read_all(mtype):
                if m.get("id") == memory_id:
                    return m
        return None

    def get_all(
        self,
        *,
        memory_type: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """List memories with optional filters."""
        results: List[Dict[str, Any]] = []
        types = [memory_type] if memory_type else list(self._stores.keys())
        for mtype in types:
            for m in self._read_all(mtype):
                if category and m.get("category") != category:
                    continue
                results.append(m)
        # Sort by recency
        results.sort(key=lambda m: m.get("created_at", ""), reverse=True)
        return results[:limit]

    def search(
        self,
        query: str,
        *,
        memory_type: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
        threshold: float = 0.1,
    ) -> Dict[str, Any]:
        """Search memories by keyword relevance + recency + category.

        Returns {"results": [memory_with_score, ...]} like mem0.
        """
        query_lower = query.lower()
        query_tokens = set(self._tokenize(query_lower))
        current_iter = self._current_iteration()

        candidates: List[Dict[str, Any]] = []
        types = [memory_type] if memory_type else list(self._stores.keys())

        for mtype in types:
            for m in self._read_all(mtype):
                if category and m.get("category") != category:
                    continue
                score = self._score_memory(m, query_lower, query_tokens, current_iter)
                if score >= threshold:
                    mem_copy = dict(m)
                    mem_copy["score"] = round(score, 4)
                    candidates.append(mem_copy)

        # Sort by score descending
        candidates.sort(key=lambda m: m["score"], reverse=True)
        return {"results": candidates[:limit]}

    def update(self, memory_id: str, content: str) -> Dict[str, Any]:
        """Update a memory's content (like mem0.update)."""
        for mtype in self._stores:
            memories = self._read_all(mtype)
            for i, m in enumerate(memories):
                if m.get("id") == memory_id:
                    old_content = m.get("content", "")
                    m["content"] = content
                    m["hash"] = self._hash(content)
                    m["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self._write_all(mtype, memories)
                    return {
                        "event": "UPDATE",
                        "id": memory_id,
                        "old_memory": old_content,
                        "memory": content,
                    }
        return {"event": "SKIP", "reason": "not found"}

    def delete(self, memory_id: str) -> Dict[str, Any]:
        """Delete a memory by ID."""
        for mtype in self._stores:
            memories = self._read_all(mtype)
            filtered = [m for m in memories if m.get("id") != memory_id]
            if len(filtered) < len(memories):
                self._write_all(mtype, filtered)
                return {"event": "DELETE", "id": memory_id}
        return {"event": "SKIP", "reason": "not found"}

    def history(self, memory_id: str) -> list:
        """Get the history log for a memory (stub — records via parent history)."""
        mem = self.get(memory_id)
        if not mem:
            return []
        return [
            {"memory": mem.get("content"), "created_at": mem.get("created_at"), "updated_at": mem.get("updated_at")}
        ]

    def reset(self, memory_type: Optional[str] = None) -> None:
        """Clear all memories (or a specific type)."""
        types = [memory_type] if memory_type else list(self._stores.keys())
        for mtype in types:
            path = self._stores[mtype]
            if path.exists():
                path.unlink()

    # ── Bulk operations ─────────────────────────────────────────────

    def add_many(self, entries: list) -> list:
        """Add multiple memories. Each entry is a dict with content + optional fields."""
        results = []
        for entry in entries:
            if isinstance(entry, str):
                entry = {"content": entry}
            result = self.add(
                entry.get("content", ""),
                memory_type=entry.get("memory_type", self.EPISODIC),
                category=entry.get("category", "progress"),
                metadata=entry.get("metadata"),
                iteration=entry.get("iteration"),
            )
            results.append(result)
        return results

    # ── Extraction: auto-extract memories from iteration output ─────

    def extract_from_output(self, output: str, iteration: int) -> list:
        """Extract structured memories from raw iteration output.

        This mimics mem0's 'add(messages)' with infer=True — we parse the
        output to find facts, file changes, errors, and decisions.
        No LLM needed; uses pattern matching.
        """
        results = []

        # 1. File changes
        file_patterns = [
            r'(?:created?|modified?|edited?|updated?|changed?|wrote|writing)\s+(?:file\s+)?[`\'"]?([^\s`\'"]+\.\w{1,10})[`\'"]?',
            r"(?:in|to|from)\s+\[?([^\s\]]+\.\w{1,10})\]?",
        ]
        files_seen: set = set()
        for pat in file_patterns:
            for match in re.finditer(pat, output, re.IGNORECASE):
                fname = match.group(1)
                if fname not in files_seen and not fname.startswith("http"):
                    files_seen.add(fname)
        if files_seen:
            results.append(
                self.add(
                    f"Files touched in iteration {iteration}: {', '.join(sorted(files_seen))}",
                    memory_type=self.EPISODIC,
                    category="file_changes",
                    iteration=iteration,
                    deduplicate=True,
                )
            )

        # 2. Errors & failures
        error_patterns = [
            r"(?:error|Error|ERROR|failed|Failed|FAIL|exception|Exception|traceback|Traceback)[\s:]+(.{20,120})",
        ]
        errors_seen: set = set()
        for pat in error_patterns:
            for match in re.finditer(pat, output):
                err = match.group(1).strip()[:120]
                if err not in errors_seen:
                    errors_seen.add(err)
        if errors_seen:
            for err in list(errors_seen)[:5]:
                results.append(
                    self.add(
                        f"Error in iteration {iteration}: {err}",
                        memory_type=self.EPISODIC,
                        category="errors",
                        iteration=iteration,
                        deduplicate=True,
                    )
                )

        # 3. Test results
        test_patterns = [
            r"(\d+)\s+(?:tests?\s+)?passed",
            r"(\d+)\s+(?:tests?\s+)?failed",
            r"PASSED|FAILED|OK\b",
            r"pytest.*?(\d+ passed.*)",
        ]
        for pat in test_patterns:
            match = re.search(pat, output, re.IGNORECASE)
            if match:
                results.append(
                    self.add(
                        f"Test results iteration {iteration}: {match.group(0)[:100]}",
                        memory_type=self.EPISODIC,
                        category="test_results",
                        iteration=iteration,
                        deduplicate=True,
                    )
                )
                break

        # 4. Completion signals
        if "<promise>" in output:
            results.append(
                self.add(
                    f"Completion promise detected in iteration {iteration}",
                    memory_type=self.EPISODIC,
                    category="progress",
                    iteration=iteration,
                    deduplicate=True,
                )
            )

        # 5. Git operations
        git_patterns = [
            r"git\s+(commit|add|push|checkout|merge|rebase)\b.*",
        ]
        for pat in git_patterns:
            for match in re.finditer(pat, output, re.IGNORECASE):
                results.append(
                    self.add(
                        f"Git operation iter {iteration}: {match.group(0)[:80]}",
                        memory_type=self.EPISODIC,
                        category="file_changes",
                        iteration=iteration,
                        deduplicate=True,
                    )
                )

        return results

    def extract_facts(self, text: str, iteration: int) -> list:
        """Extract semantic facts from text (long-term knowledge).

        Like mem0's fact extraction but rule-based instead of LLM-based.
        """
        results = []
        fact_patterns = [
            # "X is located in Y", "X uses Y"
            (r"(?:project|repo|codebase)\s+(?:uses?|requires?|depends? on)\s+(.{10,80})", "dependencies"),
            # "The main file is X"
            (r'(?:main|entry|config)\s+(?:file|module|script)\s+(?:is|at)\s+[`\'"]?([^\s`\'"]+)', "task_context"),
            # "To fix X, you need to Y"
            (r"(?:to\s+(?:fix|solve|resolve|handle))\s+(.{15,100})", "patterns"),
            # Decisions: "decided to", "chose to", "using X instead of Y"
            (r"(?:decided?|chose?|choosing|selected?)\s+(?:to\s+)?(.{10,100})", "decisions"),
        ]
        for pat, cat in fact_patterns:
            for match in re.finditer(pat, text, re.IGNORECASE):
                fact = match.group(1).strip()[:120]
                results.append(
                    self.add(
                        fact,
                        memory_type=self.SEMANTIC,
                        category=cat,
                        iteration=iteration,
                        deduplicate=True,
                    )
                )
        return results

    # ── Promote: move important episodic memories to semantic ───────

    def promote_memories(self, min_access: int = 2) -> list:
        """Promote frequently-accessed episodic memories to semantic.

        mem0 does this via its Capture → Promote → Retrieve pipeline.
        """
        promoted = []
        episodic = self._read_all(self.EPISODIC)
        for m in episodic:
            if m.get("access_count", 0) >= min_access:
                self.add(
                    m["content"],
                    memory_type=self.SEMANTIC,
                    category=m.get("category", "progress"),
                    metadata={"promoted_from": m["id"]},
                    iteration=m.get("iteration"),
                    deduplicate=True,
                )
                promoted.append(m["id"])
        return promoted

    # ── Decay: reduce scores of old unused memories ─────────────────

    def apply_decay(self) -> int:
        """Apply temporal decay to memory scores (like mem0's recency ranking).

        Called once per iteration to reduce old memories' base scores.
        """
        current_iter = self._current_iteration()
        count = 0
        for mtype in [self.EPISODIC, self.SEMANTIC, self.PROCEDURAL]:
            memories = self._read_all(mtype)
            changed = False
            for m in memories:
                age = current_iter - m.get("iteration", current_iter)
                if age > 0:
                    new_score = max(0.1, m.get("score", 1.0) - (self.RECENCY_DECAY * age * 0.1))
                    if abs(new_score - m.get("score", 1.0)) > 0.001:
                        m["score"] = round(new_score, 4)
                        changed = True
                        count += 1
            if changed:
                self._write_all(mtype, memories)
        return count

    # ── Context builder: format memories for AI consumption ─────────

    def format_for_context(
        self,
        query: str = "",
        *,
        max_working: int = 5,
        max_episodic: int = 15,
        max_semantic: int = 10,
        max_procedural: int = 5,
    ) -> str:
        """Build a formatted memory block for injection into AI context.

        Like mem0's auto-recall: searches across all memory types and
        assembles a structured summary.
        """
        sections = []

        # Working memory (most recent iteration's scratch)
        working = self.get_all(memory_type=self.WORKING, limit=max_working)
        if working:
            lines = [f"  - {m['content']}" for m in working]
            sections.append("### Working Memory (this iteration)\n" + "\n".join(lines))

        # Episodic memory — search if query provided, else get recent
        if query:
            ep_results = self.search(query, memory_type=self.EPISODIC, limit=max_episodic)
            episodic = ep_results.get("results", [])
        else:
            episodic = self.get_all(memory_type=self.EPISODIC, limit=max_episodic)
        if episodic:
            lines = []
            for m in episodic:
                cat = m.get("category", "")
                it = m.get("iteration", "?")
                score = m.get("score", "")
                score_str = f" ({score:.0%})" if isinstance(score, float) else ""
                lines.append(f"  - [iter {it}|{cat}]{score_str} {m['content']}")
            sections.append("### Episodic Memory (what happened)\n" + "\n".join(lines))

        # Semantic memory — long-term facts
        if query:
            sem_results = self.search(query, memory_type=self.SEMANTIC, limit=max_semantic)
            semantic = sem_results.get("results", [])
        else:
            semantic = self.get_all(memory_type=self.SEMANTIC, limit=max_semantic)
        if semantic:
            lines = [f"  - [{m.get('category','')}] {m['content']}" for m in semantic]
            sections.append("### Semantic Memory (known facts)\n" + "\n".join(lines))

        # Procedural memory — learned workflows
        procedural = self.get_all(memory_type=self.PROCEDURAL, limit=max_procedural)
        if procedural:
            lines = [f"  - {m['content']}" for m in procedural]
            sections.append("### Procedural Memory (learned workflows)\n" + "\n".join(lines))

        if not sections:
            return ""

        return "## Memory Bank\n\n" + "\n\n".join(sections)

    # ── Statistics ──────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """Return memory statistics (like mem0 /stats endpoint)."""
        result: Dict[str, Any] = {}
        total = 0
        for mtype, path in self._stores.items():
            count = len(self._read_all(mtype))
            result[mtype] = count
            total += count
        result["total"] = total

        # Category breakdown
        cats: Dict[str, int] = {}
        for mtype in self._stores:
            for m in self._read_all(mtype):
                cat = m.get("category", "unknown")
                cats[cat] = cats.get(cat, 0) + 1
        result["categories"] = cats
        return result

    # ── Internal helpers ────────────────────────────────────────────

    def _current_iteration(self) -> int:
        state = self.ralph.get_state()
        return state.get("iteration", 1) if state else 1

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _normalize_content(content: str) -> str:
        """Normalize content for deduplication and matching."""
        text = content.lower()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^a-z0-9 _\-./]", "", text)
        return text.strip()

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple word tokenizer."""
        return [w for w in re.split(r"\W+", text.lower()) if len(w) > 2]

    def _score_memory(self, memory: Dict[str, Any], query_lower: str, query_tokens: set, current_iter: int) -> float:
        """Score a memory against a query.

        Combines:
        - Keyword overlap (TF-IDF-like)
        - Exact substring match bonus
        - Recency decay
        - Category relevance boost
        - Access frequency boost
        """
        content_lower = memory.get("content", "").lower()
        content_tokens = set(self._tokenize(content_lower))

        # 1. Keyword overlap
        if not query_tokens or not content_tokens:
            keyword_score = 0.0
        else:
            overlap = query_tokens & content_tokens
            keyword_score = len(overlap) / max(len(query_tokens), 1)

        # 2. Exact substring match
        exact_bonus = self.EXACT_MATCH_BONUS if query_lower in content_lower else 0.0

        # 3. Recency decay
        age = current_iter - memory.get("iteration", current_iter)
        recency = math.exp(-self.RECENCY_DECAY * max(age, 0))

        # 4. Category boost (if query mentions the category)
        cat = memory.get("category", "").lower()
        cat_boost = self.CATEGORY_BOOST if cat and cat.replace("_", " ") in query_lower else 0.0

        # 5. Access frequency (subtle boost)
        access_boost = min(0.1, memory.get("access_count", 0) * 0.02)

        # 6. Base score from memory
        base = memory.get("score", 1.0)

        # 7. Category priority
        priority = self.CATEGORY_PRIORITY.get(cat, 1.0)

        # Combine
        final = (
            (keyword_score * self.KEYWORD_WEIGHT + exact_bonus) * 0.5
            + recency * 0.3
            + base * 0.1
            + cat_boost
            + access_boost
        ) * priority
        return min(final, 1.0)

    def _find_duplicate(self, content_hash: str, content: str, memory_type: str, category: str) -> Optional[Dict]:
        """Find a duplicate memory by hash or high keyword overlap."""
        memories = self._read_all(memory_type)
        content_tokens = set(self._tokenize(content.lower()))
        normalized_hash = self._hash(self._normalize_content(content))
        for m in memories:
            # Exact hash match
            if m.get("hash") == content_hash:
                return m
            if m.get("normalized_hash") == normalized_hash:
                return m
            # High keyword overlap within same category
            if m.get("category") == category:
                m_tokens = set(self._tokenize(m.get("content", "").lower()))
                if content_tokens and m_tokens:
                    overlap = len(content_tokens & m_tokens) / max(len(content_tokens | m_tokens), 1)
                    if overlap > 0.85:
                        return m
        return None

    def _read_all(self, memory_type: str) -> list:
        """Read all memories of a given type."""
        path = self._stores.get(memory_type)
        if not path or not path.exists():
            return []
        entries = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return entries

    def _write_all(self, memory_type: str, memories: list) -> None:
        """Overwrite all memories of a given type."""
        path = self._stores.get(memory_type)
        if not path:
            return
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for m in memories:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")

    def _append(self, memory_type: str, memory: Dict[str, Any]) -> None:
        """Append a single memory."""
        path = self._stores.get(memory_type)
        if not path:
            return
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(memory, ensure_ascii=False) + "\n")

        # Enforce limit
        all_mems = self._read_all(memory_type)
        if len(all_mems) > self.MAX_MEMORIES_PER_TYPE:
            # Keep most recent + highest scored
            all_mems.sort(key=lambda m: (m.get("score", 0), m.get("created_at", "")), reverse=True)
            self._write_all(memory_type, all_mems[: self.MAX_MEMORIES_PER_TYPE])
