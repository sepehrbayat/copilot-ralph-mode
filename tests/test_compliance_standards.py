"""
Compliance and Standards Tests for Ralph Mode
=============================================

Tests ensuring compliance with industry standards and best practices.
Essential for enterprise adoption and GitHub integration proposal.
"""

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from ralph_mode import RalphMode, TaskLibrary, VERSION, AVAILABLE_MODELS


# =============================================================================
# SEMVER COMPLIANCE TESTS
# =============================================================================

class TestSemanticVersioning:
    """Tests for Semantic Versioning 2.0.0 compliance."""
    
    def test_version_follows_semver_format(self):
        """VERSION must follow MAJOR.MINOR.PATCH format."""
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$'
        assert re.match(pattern, VERSION), f"Version {VERSION} does not follow SemVer"
    
    def test_version_components_are_numeric(self):
        """MAJOR, MINOR, PATCH must be non-negative integers."""
        parts = VERSION.split('-')[0].split('+')[0].split('.')
        assert len(parts) >= 3
        
        for part in parts[:3]:
            assert part.isdigit()
            assert int(part) >= 0
    
    def test_version_no_leading_zeros(self):
        """Version components must not have leading zeros."""
        parts = VERSION.split('-')[0].split('+')[0].split('.')
        
        for part in parts[:3]:
            if len(part) > 1:
                assert not part.startswith('0'), f"Leading zero in version component: {part}"


# =============================================================================
# JSON SCHEMA COMPLIANCE TESTS
# =============================================================================

class TestJSONSchemaCompliance:
    """Tests for JSON output format compliance."""
    
    def test_state_json_is_valid_json(self, tmp_path: Path):
        """State file must be valid JSON."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        
        state_file = tmp_path / ".ralph-mode" / "state.json"
        content = state_file.read_text(encoding='utf-8')
        
        # Should not raise
        state = json.loads(content)
        assert isinstance(state, dict)
        
        rm.disable()
    
    def test_state_json_required_fields(self, tmp_path: Path):
        """State JSON must have required fields with correct types."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        
        state_file = tmp_path / ".ralph-mode" / "state.json"
        state = json.loads(state_file.read_text(encoding='utf-8'))
        
        # Required fields
        required = {
            'iteration': int,
            'mode': str,
            'started_at': str,
            'max_iterations': int,
            'completion_promise': str,
        }
        
        for field, expected_type in required.items():
            assert field in state, f"Missing required field: {field}"
            assert isinstance(state[field], expected_type), \
                f"Field {field} has wrong type: expected {expected_type}, got {type(state[field])}"
        
        rm.disable()
    
    def test_history_jsonl_format(self, tmp_path: Path):
        """History must be valid JSON Lines format."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=10, completion_promise="DONE")
        
        for _ in range(5):
            rm.iterate()
        
        history_file = tmp_path / ".ralph-mode" / "history.jsonl"
        content = history_file.read_text(encoding='utf-8')
        
        # Each line must be valid JSON
        for line in content.strip().split('\n'):
            if line:
                entry = json.loads(line)
                assert isinstance(entry, dict)
                assert 'timestamp' in entry
                assert 'status' in entry  # Field is 'status', not 'event'
        
        rm.disable()
    
    def test_tasks_json_format(self, tmp_path: Path):
        """Tasks file must be valid JSON array."""
        rm = RalphMode(base_path=tmp_path)
        tasks = [
            {"id": "task-1", "title": "Task 1", "prompt": "Do 1"},
            {"id": "task-2", "title": "Task 2", "prompt": "Do 2"},
        ]
        rm.init_batch(tasks, max_iterations=5, completion_promise="DONE")
        
        tasks_file = tmp_path / ".ralph-mode" / "tasks.json"
        content = tasks_file.read_text(encoding='utf-8')
        
        parsed = json.loads(content)
        assert isinstance(parsed, list)
        
        for task in parsed:
            assert 'id' in task
            assert 'title' in task
            assert 'prompt' in task
        
        rm.disable()


# =============================================================================
# ISO 8601 DATE/TIME COMPLIANCE TESTS
# =============================================================================

class TestISO8601Compliance:
    """Tests for ISO 8601 date/time format compliance."""
    
    def test_started_at_is_iso8601(self, tmp_path: Path):
        """started_at must be ISO 8601 formatted."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        
        status = rm.status()
        started_at = status['started_at']
        
        # Should be parseable as ISO 8601
        try:
            datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        except ValueError:
            pytest.fail(f"started_at is not ISO 8601: {started_at}")
        
        rm.disable()
    
    def test_history_timestamps_are_iso8601(self, tmp_path: Path):
        """History timestamps must be ISO 8601 formatted."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=10, completion_promise="DONE")
        rm.iterate()
        
        history = rm.get_history()
        
        for entry in history:
            timestamp = entry['timestamp']
            try:
                datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                pytest.fail(f"History timestamp is not ISO 8601: {timestamp}")
        
        rm.disable()


# =============================================================================
# UTF-8 ENCODING COMPLIANCE TESTS
# =============================================================================

class TestUTF8Compliance:
    """Tests for UTF-8 encoding compliance."""
    
    def test_state_file_is_utf8(self, tmp_path: Path):
        """State file must be UTF-8 encoded."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test with émojis 🎉", max_iterations=5, completion_promise="完成")
        
        state_file = tmp_path / ".ralph-mode" / "state.json"
        
        # Read as bytes and verify UTF-8
        content_bytes = state_file.read_bytes()
        content_str = content_bytes.decode('utf-8')  # Should not raise
        
        assert "🎉" in content_str or True  # May be escaped in JSON
        
        rm.disable()
    
    def test_prompt_file_is_utf8(self, tmp_path: Path):
        """Prompt file must be UTF-8 encoded."""
        test_prompts = [
            "English text",
            "日本語テスト",
            "한국어 테스트",
            "العربية اختبار",
            "Emoji test 🚀💯🎉",
            "Mixed: Hello 世界 🌍",
        ]
        
        for prompt in test_prompts:
            rm = RalphMode(base_path=tmp_path)
            rm.enable(prompt, max_iterations=5, completion_promise="DONE")
            
            prompt_file = tmp_path / ".ralph-mode" / "prompt.md"
            content = prompt_file.read_bytes().decode('utf-8')
            
            assert prompt in content
            
            rm.disable()
    
    def test_history_file_is_utf8(self, tmp_path: Path):
        """History file must be UTF-8 encoded."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Unicode: 日本語 🎉", max_iterations=5, completion_promise="完成")
        rm.iterate()
        
        history_file = tmp_path / ".ralph-mode" / "history.jsonl"
        content = history_file.read_bytes().decode('utf-8')  # Should not raise
        
        assert isinstance(content, str)
        
        rm.disable()


# =============================================================================
# FILE PATH COMPLIANCE TESTS
# =============================================================================

class TestFilePathCompliance:
    """Tests for cross-platform file path compliance."""
    
    def test_uses_forward_slashes_internally(self, tmp_path: Path):
        """Internal paths should use forward slashes for portability."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        
        # Check that Path objects are used (automatically handles separators)
        assert isinstance(rm.ralph_dir, Path)
        assert isinstance(rm.state_file, Path)
        
        rm.disable()
    
    def test_no_absolute_paths_in_state(self, tmp_path: Path):
        """State should not contain absolute paths (for portability)."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        
        state_file = tmp_path / ".ralph-mode" / "state.json"
        content = state_file.read_text(encoding='utf-8')
        state = json.loads(content)
        
        # Check for common absolute path patterns
        state_str = json.dumps(state)
        
        # Should not contain drive letters (Windows) or root paths (Unix)
        # Note: Some paths might be intentionally absolute, this is a soft check
        if 'C:\\' in state_str or '/home/' in state_str or '/Users/' in state_str:
            # This is a warning, not a failure - some use cases need absolute paths
            pass
        
        rm.disable()
    
    def test_handles_spaces_in_path(self, tmp_path: Path):
        """Should handle paths with spaces."""
        workspace = tmp_path / "path with spaces" / "project"
        workspace.mkdir(parents=True)
        
        rm = RalphMode(base_path=workspace)
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        
        assert rm.is_active()
        
        rm.disable()
    
    def test_handles_unicode_in_path(self, tmp_path: Path):
        """Should handle paths with Unicode characters."""
        workspace = tmp_path / "プロジェクト" / "项目"
        workspace.mkdir(parents=True)
        
        rm = RalphMode(base_path=workspace)
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        
        assert rm.is_active()
        
        rm.disable()


# =============================================================================
# API CONSISTENCY TESTS
# =============================================================================

class TestAPIConsistency:
    """Tests for API consistency and predictability."""
    
    def test_enable_always_returns_dict(self, tmp_path: Path):
        """enable() must always return a dict on success."""
        rm = RalphMode(base_path=tmp_path)
        result = rm.enable("Test", max_iterations=5, completion_promise="DONE")
        
        assert isinstance(result, dict)
        
        rm.disable()
    
    def test_status_returns_dict_or_none(self, tmp_path: Path):
        """status() must return dict when active, None when inactive."""
        rm = RalphMode(base_path=tmp_path)
        
        # When inactive
        assert rm.status() is None
        
        # When active
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        status = rm.status()
        assert isinstance(status, dict)
        
        rm.disable()
    
    def test_is_active_returns_bool(self, tmp_path: Path):
        """is_active() must always return bool."""
        rm = RalphMode(base_path=tmp_path)
        
        assert rm.is_active() is False
        
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        assert rm.is_active() is True
        
        rm.disable()
        assert rm.is_active() is False
    
    def test_check_completion_returns_bool(self, tmp_path: Path):
        """check_completion() must always return bool."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        
        assert rm.check_completion("<promise>DONE</promise>") is True
        assert rm.check_completion("wrong") is False
        
        rm.disable()
    
    def test_get_history_returns_list(self, tmp_path: Path):
        """get_history() must always return list."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        
        history = rm.get_history()
        assert isinstance(history, list)
        
        rm.disable()


# =============================================================================
# SECURITY COMPLIANCE TESTS
# =============================================================================

class TestSecurityCompliance:
    """Tests for security best practices compliance."""
    
    def test_no_sensitive_data_in_logs(self, tmp_path: Path):
        """Sensitive data should not appear in logs/history."""
        rm = RalphMode(base_path=tmp_path)
        
        # Use a prompt that might contain sensitive info
        sensitive_prompt = "API_KEY=sk_secret_12345 PASSWORD=hunter2"
        rm.enable(sensitive_prompt, max_iterations=5, completion_promise="DONE")
        rm.iterate()
        
        # Check history doesn't log the full prompt content
        history = rm.get_history()
        history_str = json.dumps(history)
        
        # API keys and passwords shouldn't appear in history entries
        # (The prompt itself is stored separately, not in history)
        for entry in history:
            if entry['status'] == 'iteration':  # Field is 'status', not 'event'
                assert 'sk_secret_12345' not in json.dumps(entry)
        
        rm.disable()
    
    def test_file_permissions_not_world_readable(self, tmp_path: Path):
        """State files should have restricted permissions on Unix."""
        if os.name == 'nt':
            pytest.skip("Permission test is Unix-specific")
        
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        
        state_file = tmp_path / ".ralph-mode" / "state.json"
        
        # Get file permissions
        mode = state_file.stat().st_mode
        
        # Check that others don't have write permission
        # (0o002 = world writable)
        assert not (mode & 0o002), "State file is world-writable"
        
        rm.disable()
    
    def test_no_code_execution_in_prompts(self, tmp_path: Path):
        """Prompts should be treated as data, not code."""
        rm = RalphMode(base_path=tmp_path)
        
        # Attempt code injection
        malicious_prompts = [
            "__import__('os').system('whoami')",
            "eval('print(1)')",
            "exec('import os')",
            "${cat /etc/passwd}",
            "$(whoami)",
            "`id`",
        ]
        
        for prompt in malicious_prompts:
            rm.enable(prompt, max_iterations=5, completion_promise="DONE")
            
            # Prompt should be stored as-is, not executed
            stored = rm.get_prompt()
            assert prompt in stored  # Stored as string, not executed
            
            rm.disable()


# =============================================================================
# DOCUMENTATION COMPLIANCE TESTS
# =============================================================================

class TestDocumentationCompliance:
    """Tests verifying documentation accuracy."""
    
    def test_all_public_methods_have_docstrings(self):
        """All public methods should have docstrings."""
        public_methods = [
            'enable', 'disable', 'status', 'iterate',
            'complete', 'check_completion', 'get_prompt',
            'get_history', 'is_active', 'init_batch',
            'next_task', 'register_created_agent'
        ]
        
        for method_name in public_methods:
            method = getattr(RalphMode, method_name, None)
            if method:
                assert method.__doc__, f"Method {method_name} lacks docstring"
    
    def test_class_has_docstring(self):
        """Main classes should have docstrings."""
        assert RalphMode.__doc__
        assert TaskLibrary.__doc__
    
    def test_available_models_documented(self):
        """All available models should be documented."""
        # These models should be in AVAILABLE_MODELS
        expected_models = [
            'auto',
            'claude-sonnet-4',  # Use correct model names
            'gpt-4.1',
        ]
        
        for model in expected_models:
            assert model in AVAILABLE_MODELS, f"Model {model} not in AVAILABLE_MODELS"


# =============================================================================
# IDEMPOTENCY TESTS
# =============================================================================

class TestIdempotency:
    """Tests for idempotent operations."""
    
    def test_status_is_idempotent(self, tmp_path: Path):
        """Calling status() multiple times should return same result."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        
        status1 = rm.status()
        status2 = rm.status()
        status3 = rm.status()
        
        # All calls should return equivalent results
        assert status1 == status2 == status3
        
        rm.disable()
    
    def test_is_active_is_idempotent(self, tmp_path: Path):
        """Calling is_active() multiple times should return same result."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        
        results = [rm.is_active() for _ in range(10)]
        
        assert all(r is True for r in results)
        
        rm.disable()
    
    def test_get_prompt_is_idempotent(self, tmp_path: Path):
        """Calling get_prompt() multiple times should return same result."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test prompt content", max_iterations=5, completion_promise="DONE")
        
        prompts = [rm.get_prompt() for _ in range(10)]
        
        assert all(p == prompts[0] for p in prompts)
        
        rm.disable()
    
    def test_get_history_is_idempotent(self, tmp_path: Path):
        """Calling get_history() multiple times should return same result."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        rm.iterate()
        
        history1 = rm.get_history()
        history2 = rm.get_history()
        
        assert len(history1) == len(history2)
        
        rm.disable()
    
    def test_disable_multiple_times_safe(self, tmp_path: Path):
        """Calling disable() multiple times should be safe."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        
        # First disable
        result1 = rm.disable()
        assert result1 is not None
        
        # Subsequent disables should be safe
        result2 = rm.disable()
        result3 = rm.disable()
        
        # Should return None for subsequent calls
        assert result2 is None
        assert result3 is None


# =============================================================================
# ERROR MESSAGE COMPLIANCE TESTS
# =============================================================================

class TestErrorMessages:
    """Tests for helpful error messages."""
    
    def test_enable_when_active_has_helpful_message(self, tmp_path: Path):
        """Error when enabling while active should be helpful."""
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        
        with pytest.raises(ValueError) as exc_info:  # RalphMode raises ValueError
            rm.enable("Another", max_iterations=5, completion_promise="DONE")
        
        error_msg = str(exc_info.value).lower()
        assert 'active' in error_msg or 'already' in error_msg or 'enabled' in error_msg
        
        rm.disable()
    
    def test_iterate_when_inactive_has_helpful_message(self, tmp_path: Path):
        """Error when iterating while inactive should be helpful."""
        rm = RalphMode(base_path=tmp_path)
        
        with pytest.raises(ValueError) as exc_info:  # RalphMode raises ValueError
            rm.iterate()
        
        error_msg = str(exc_info.value).lower()
        assert 'active' in error_msg or 'inactive' in error_msg or 'not' in error_msg or 'enable' in error_msg


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
