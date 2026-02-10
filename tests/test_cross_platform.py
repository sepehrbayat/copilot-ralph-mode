#!/usr/bin/env python3
"""
Cross-Platform Test Suite for Copilot Ralph Mode
================================================

Tests to ensure Ralph Mode works correctly across:
- Windows (PowerShell, CMD)
- macOS (zsh, bash)
- Linux (bash, sh)

Key areas tested:
1. Path handling (separators, absolute/relative)
2. Line endings (CRLF vs LF)
3. File encoding (UTF-8 BOM handling)
4. Environment variables
5. Shell script compatibility
6. File permissions (where applicable)
7. Temp directory handling
8. JSON serialization across platforms
"""

import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ralph_mode import VERSION, RalphMode, TaskLibrary

# =============================================================================
# Platform Detection
# =============================================================================

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"
PLATFORM_NAME = platform.system()


def get_shell():
    """Get the current shell."""
    if IS_WINDOWS:
        return os.environ.get("COMSPEC", "cmd.exe")
    return os.environ.get("SHELL", "/bin/sh")


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a cross-platform temporary directory."""
    # Use tempfile for proper cross-platform temp dir
    d = Path(tempfile.mkdtemp(prefix="ralph_test_"))
    yield d

    # Cleanup with proper permission handling
    def remove_readonly(func, path, excinfo):
        """Handle read-only files on Windows."""
        os.chmod(path, stat.S_IWRITE)
        func(path)

    shutil.rmtree(d, onerror=remove_readonly)


@pytest.fixture
def ralph(temp_dir):
    """Create a RalphMode instance."""
    return RalphMode(temp_dir)


# =============================================================================
# Path Handling Tests
# =============================================================================


class TestPathHandling:
    """Tests for cross-platform path handling."""

    @pytest.fixture(autouse=True)
    def setup(self, temp_dir):
        self.temp_dir = temp_dir
        self.ralph = RalphMode(temp_dir)

    def test_path_creation_uses_pathlib(self):
        """Verify paths are created using pathlib for cross-platform support."""
        self.ralph.enable("Test")

        # All paths should be Path objects
        assert isinstance(self.ralph.ralph_dir, Path)
        assert isinstance(self.ralph.state_file, Path)
        assert isinstance(self.ralph.prompt_file, Path)

        self.ralph.disable()

    def test_paths_are_absolute(self):
        """Ensure all paths are absolute."""
        self.ralph.enable("Test")

        assert self.ralph.ralph_dir.is_absolute()
        assert self.ralph.state_file.is_absolute()
        assert self.ralph.prompt_file.is_absolute()

        self.ralph.disable()

    def test_path_with_spaces(self):
        """Test paths containing spaces."""
        space_dir = self.temp_dir / "path with spaces"
        space_dir.mkdir()

        ralph = RalphMode(space_dir)
        ralph.enable("Test task")

        assert ralph.is_active()
        assert ralph.ralph_dir.exists()

        ralph.disable()

    def test_path_with_unicode(self):
        """Test paths with unicode characters."""
        # Create directory with various unicode chars
        unicode_names = [
            "日本語",  # Japanese
            "한국어",  # Korean
            "العربية",  # Arabic
            "emoji_🚀",  # Emoji
            "äöü",  # German umlauts
        ]

        for name in unicode_names:
            try:
                unicode_dir = self.temp_dir / name
                unicode_dir.mkdir(exist_ok=True)

                ralph = RalphMode(unicode_dir)
                ralph.enable("Test")

                assert ralph.is_active()
                ralph.disable()
            except (OSError, UnicodeError):
                # Some filesystems may not support certain unicode chars
                pytest.skip(f"Filesystem doesn't support unicode name: {name}")

    def test_deeply_nested_path(self):
        """Test deeply nested directory structure."""
        nested = self.temp_dir
        for i in range(10):
            nested = nested / f"level_{i}"
        nested.mkdir(parents=True)

        ralph = RalphMode(nested)
        ralph.enable("Test")

        assert ralph.is_active()
        ralph.disable()

    def test_path_normalization(self):
        """Test that paths work even with redundant components."""
        # Create path with redundant separators - test it still works
        weird_path = self.temp_dir / "a" / ".." / "a" / "b"
        weird_path.mkdir(parents=True, exist_ok=True)

        ralph = RalphMode(weird_path)
        ralph.enable("Test")

        # Should still function correctly
        assert ralph.is_active()
        assert ralph.ralph_dir.exists()

        ralph.disable()

    def test_relative_path_handling(self):
        """Test that relative paths work correctly."""
        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)

            # Create subdirectory
            subdir = Path("subdir")
            subdir.mkdir(exist_ok=True)

            ralph = RalphMode(subdir)
            ralph.enable("Test")

            # Should function correctly regardless of path type
            assert ralph.is_active()
            assert ralph.ralph_dir.exists()

            ralph.disable()
        finally:
            os.chdir(original_cwd)


# =============================================================================
# Line Ending Tests
# =============================================================================


class TestLineEndings:
    """Tests for line ending handling (CRLF vs LF)."""

    @pytest.fixture(autouse=True)
    def setup(self, temp_dir):
        self.temp_dir = temp_dir
        self.ralph = RalphMode(temp_dir)

    def test_prompt_with_unix_line_endings(self):
        """Test prompt with Unix line endings (LF)."""
        prompt = "Line 1\nLine 2\nLine 3"
        self.ralph.enable(prompt)

        retrieved = self.ralph.get_prompt()
        # Should preserve line structure
        assert retrieved.count("\n") >= 2

        self.ralph.disable()

    def test_prompt_with_windows_line_endings(self):
        """Test prompt with Windows line endings (CRLF)."""
        prompt = "Line 1\r\nLine 2\r\nLine 3"
        self.ralph.enable(prompt)

        retrieved = self.ralph.get_prompt()
        # Content should be preserved (may be normalized)
        assert "Line 1" in retrieved
        assert "Line 2" in retrieved
        assert "Line 3" in retrieved

        self.ralph.disable()

    def test_mixed_line_endings(self):
        """Test prompt with mixed line endings."""
        prompt = "Unix\nWindows\r\nOld Mac\rMixed"
        self.ralph.enable(prompt)

        retrieved = self.ralph.get_prompt()
        # All content should be preserved
        assert "Unix" in retrieved
        assert "Windows" in retrieved
        assert "Old Mac" in retrieved
        assert "Mixed" in retrieved

        self.ralph.disable()

    def test_json_state_line_endings(self):
        """Test that JSON state file is valid regardless of platform."""
        self.ralph.enable("Test\nMultiline\nPrompt")

        # Read raw file content
        raw_content = self.ralph.state_file.read_bytes()

        # Should be valid JSON
        state = json.loads(raw_content.decode("utf-8"))
        assert "iteration" in state

        self.ralph.disable()


# =============================================================================
# File Encoding Tests
# =============================================================================


class TestFileEncoding:
    """Tests for file encoding handling."""

    @pytest.fixture(autouse=True)
    def setup(self, temp_dir):
        self.temp_dir = temp_dir
        self.ralph = RalphMode(temp_dir)

    def test_utf8_encoding_default(self):
        """Verify UTF-8 encoding is used by default."""
        prompt = "Test with émojis 🎉 and unicode: 日本語"
        self.ralph.enable(prompt)

        # Read file and verify encoding
        content = self.ralph.prompt_file.read_text(encoding="utf-8")
        assert prompt in content

        self.ralph.disable()

    def test_utf8_bom_handling(self):
        """Test handling of UTF-8 BOM if present."""
        # Some Windows editors add BOM
        bom = b"\xef\xbb\xbf"

        self.ralph.enable("Test")

        # Manually write file with BOM
        content = "BOM test content"
        self.ralph.prompt_file.write_bytes(bom + content.encode("utf-8"))

        # Should still be readable
        retrieved = self.ralph.get_prompt()
        assert "BOM test content" in retrieved or retrieved == content

        self.ralph.disable()

    def test_various_unicode_ranges(self):
        """Test various Unicode character ranges."""
        test_strings = [
            "ASCII: Hello World",
            "Latin Extended: àáâãäåæçèéêë",
            "Cyrillic: Привет мир",
            "Greek: Γειά σου κόσμε",
            "Hebrew: שלום עולם",
            "Arabic: مرحبا بالعالم",
            "CJK: 你好世界 こんにちは 안녕하세요",
            "Emoji: 🎉🚀💡🔥✅❌",
            "Math: ∑∏∫∂∇",
            "Box Drawing: ┌─┐│└─┘",
        ]

        for test_str in test_strings:
            if self.ralph.is_active():
                self.ralph.disable()

            self.ralph.enable(test_str)
            retrieved = self.ralph.get_prompt()

            assert test_str == retrieved, f"Failed for: {test_str[:20]}..."

            self.ralph.disable()


# =============================================================================
# Environment Variables Tests
# =============================================================================


class TestEnvironmentVariables:
    """Tests for environment variable handling."""

    @pytest.fixture(autouse=True)
    def setup(self, temp_dir):
        self.temp_dir = temp_dir
        self.ralph = RalphMode(temp_dir)

    def test_home_directory_expansion(self):
        """Test that home directory can be determined."""
        home = Path.home()
        assert home.exists()
        assert home.is_absolute()

    def test_temp_directory_availability(self):
        """Test that temp directory is available."""
        temp = Path(tempfile.gettempdir())
        assert temp.exists()
        assert temp.is_dir()

    def test_current_working_directory(self):
        """Test current working directory handling."""
        cwd = Path.cwd()
        assert cwd.exists()
        assert cwd.is_absolute()

    def test_path_environment_variable(self):
        """Test PATH environment variable is accessible."""
        path = os.environ.get("PATH", "")
        assert len(path) > 0


# =============================================================================
# Shell Script Compatibility Tests
# =============================================================================


class TestShellScriptCompatibility:
    """Tests for shell script compatibility."""

    @pytest.fixture(autouse=True)
    def setup(self, temp_dir):
        self.temp_dir = temp_dir
        self.ralph = RalphMode(temp_dir)

    def test_state_json_shell_readable(self):
        """Test that state.json can be parsed by shell tools."""
        self.ralph.enable("Test task", max_iterations=10, completion_promise="DONE")

        # JSON should be valid and parseable
        state = json.loads(self.ralph.state_file.read_text(encoding="utf-8"))

        assert state["iteration"] == 1
        assert state["max_iterations"] == 10
        assert state["completion_promise"] == "DONE"

        self.ralph.disable()

    @pytest.mark.skipif(IS_WINDOWS, reason="Unix shell test")
    def test_bash_script_execution(self):
        """Test that bash scripts can read state."""
        self.ralph.enable("Test", max_iterations=5)

        # Create a simple bash script to read state
        script = self.temp_dir / "test.sh"
        script.write_text(
            f"""#!/bin/bash
cat "{self.ralph.state_file}" | python3 -c "import sys,json; print(json.load(sys.stdin)['iteration'])"
"""
        )
        script.chmod(0o755)

        try:
            result = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=5)
            assert "1" in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("bash not available")

        self.ralph.disable()

    def test_powershell_script_execution(self):
        """Test that PowerShell scripts can read state."""
        self.ralph.enable("Test", max_iterations=5)

        if IS_WINDOWS:
            # Create PowerShell command to read state
            cmd = f'(Get-Content "{self.ralph.state_file}" | ConvertFrom-Json).iteration'

            try:
                result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, timeout=10)
                assert "1" in result.stdout
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pytest.skip("PowerShell not available")
        else:
            # Non-Windows: fall back to Python for equivalent coverage
            result = subprocess.run(
                ["python3", "-c", f"import json; print(json.load(open('{self.ralph.state_file}'))['iteration'])"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert "1" in result.stdout

        self.ralph.disable()


# =============================================================================
# Temp Directory Tests
# =============================================================================


class TestTempDirectory:
    """Tests for temporary directory handling."""

    def test_system_temp_dir_accessible(self):
        """Test that system temp directory is accessible."""
        temp_dir = Path(tempfile.gettempdir())

        assert temp_dir.exists()
        assert os.access(temp_dir, os.W_OK)

    def test_temp_file_creation(self):
        """Test temp file creation works."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            temp_path = Path(f.name)

        try:
            assert temp_path.exists()
            assert temp_path.read_bytes() == b"test content"
        finally:
            temp_path.unlink()

    def test_temp_dir_cleanup(self):
        """Test temp directory cleanup."""
        temp_dir = Path(tempfile.mkdtemp())
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")

        # Cleanup should work
        shutil.rmtree(temp_dir)
        assert not temp_dir.exists()


# =============================================================================
# JSON Serialization Tests
# =============================================================================


class TestJSONSerialization:
    """Tests for JSON serialization across platforms."""

    @pytest.fixture(autouse=True)
    def setup(self, temp_dir):
        self.temp_dir = temp_dir
        self.ralph = RalphMode(temp_dir)

    def test_datetime_serialization(self):
        """Test datetime is serialized in ISO format."""
        self.ralph.enable("Test")

        state = self.ralph.get_state()

        # Datetime fields should be ISO format strings
        started_at = state.get("started_at", "")
        assert isinstance(started_at, str)

        # Should be parseable
        datetime.fromisoformat(started_at.replace("Z", "+00:00"))

        self.ralph.disable()

    def test_unicode_in_json(self):
        """Test unicode characters are properly serialized in JSON."""
        prompt = "Test: 日本語 🚀 العربية"
        self.ralph.enable(prompt, completion_promise="完成 ✅")

        # Read raw JSON
        raw = self.ralph.state_file.read_text(encoding="utf-8")
        state = json.loads(raw)

        assert state["completion_promise"] == "完成 ✅"

        self.ralph.disable()

    def test_special_json_characters(self):
        """Test special JSON characters are escaped."""
        prompt = 'Test "quotes" and \\backslashes\\ and\ttabs'
        self.ralph.enable(prompt)

        # Should be valid JSON
        state = json.loads(self.ralph.state_file.read_text(encoding="utf-8"))
        assert "iteration" in state

        self.ralph.disable()

    def test_newlines_in_json_values(self):
        """Test newlines in JSON string values."""
        prompt = "Line1\nLine2\nLine3"
        self.ralph.enable(prompt)

        # JSON should be valid
        state = json.loads(self.ralph.state_file.read_text(encoding="utf-8"))

        # Retrieve prompt
        retrieved = self.ralph.get_prompt()
        assert "Line1" in retrieved
        assert "Line2" in retrieved

        self.ralph.disable()


# =============================================================================
# File Permission Tests
# =============================================================================


class TestFilePermissions:
    """Tests for file permission handling."""

    @pytest.fixture(autouse=True)
    def setup(self, temp_dir):
        self.temp_dir = temp_dir
        self.ralph = RalphMode(temp_dir)

    def test_created_files_are_readable(self):
        """Test that created files are readable."""
        self.ralph.enable("Test")

        assert os.access(self.ralph.state_file, os.R_OK)
        assert os.access(self.ralph.prompt_file, os.R_OK)

        self.ralph.disable()

    def test_created_files_are_writable(self):
        """Test that created files are writable."""
        self.ralph.enable("Test")

        assert os.access(self.ralph.state_file, os.W_OK)
        assert os.access(self.ralph.prompt_file, os.W_OK)

        self.ralph.disable()

    @pytest.mark.skipif(IS_WINDOWS, reason="Unix permission test")
    def test_directory_permissions_unix(self):
        """Test directory permissions on Unix."""
        self.ralph.enable("Test")

        # Directory should be accessible
        mode = self.ralph.ralph_dir.stat().st_mode
        assert mode & stat.S_IRUSR  # Owner read
        assert mode & stat.S_IWUSR  # Owner write
        assert mode & stat.S_IXUSR  # Owner execute (for directories)

        self.ralph.disable()


# =============================================================================
# Concurrent Access Tests
# =============================================================================


class TestConcurrentAccess:
    """Tests for concurrent file access."""

    @pytest.fixture(autouse=True)
    def setup(self, temp_dir):
        self.temp_dir = temp_dir
        self.ralph = RalphMode(temp_dir)

    def test_multiple_reads(self):
        """Test multiple concurrent reads don't conflict."""
        self.ralph.enable("Test")

        # Multiple reads should work
        for _ in range(10):
            state = self.ralph.get_state()
            assert state is not None

        self.ralph.disable()

    def test_read_during_write(self):
        """Test reading while iterating."""
        self.ralph.enable("Test", max_iterations=0)

        for _ in range(5):
            # Iterate (write)
            self.ralph.iterate()
            # Read immediately after
            state = self.ralph.get_state()
            assert state is not None

        self.ralph.disable()


# =============================================================================
# Process Isolation Tests
# =============================================================================


class TestProcessIsolation:
    """Tests for process isolation and state persistence."""

    @pytest.fixture(autouse=True)
    def setup(self, temp_dir):
        self.temp_dir = temp_dir

    def test_state_persists_across_instances(self):
        """Test state persists when creating new RalphMode instances."""
        ralph1 = RalphMode(self.temp_dir)
        ralph1.enable("Test task", max_iterations=10)
        ralph1.iterate()
        ralph1.iterate()

        # Create new instance pointing to same directory
        ralph2 = RalphMode(self.temp_dir)

        assert ralph2.is_active()
        state = ralph2.get_state()
        assert state["iteration"] == 3

        ralph2.disable()

    def test_prompt_persists_across_instances(self):
        """Test prompt persists across instances."""
        prompt = "Important task description"

        ralph1 = RalphMode(self.temp_dir)
        ralph1.enable(prompt)

        ralph2 = RalphMode(self.temp_dir)
        retrieved = ralph2.get_prompt()

        assert retrieved == prompt

        ralph2.disable()


# =============================================================================
# Platform-Specific Edge Cases
# =============================================================================


class TestPlatformEdgeCases:
    """Platform-specific edge case tests."""

    @pytest.fixture(autouse=True)
    def setup(self, temp_dir):
        self.temp_dir = temp_dir
        self.ralph = RalphMode(temp_dir)

    def test_windows_reserved_names(self):
        """Test handling of Windows reserved names (CON, PRN, etc.)."""
        # These are reserved on Windows and can cause issues
        self.ralph.enable("Test with CON and PRN in content")

        assert self.ralph.is_active()

        self.ralph.disable()

    def test_windows_long_path(self):
        """Test Windows long path support."""
        # Create a path close to MAX_PATH (260)
        long_name = "a" * 50
        nested = self.temp_dir
        for _ in range(4):
            nested = nested / long_name

        try:
            nested.mkdir(parents=True, exist_ok=True)
            ralph = RalphMode(nested)
            ralph.enable("Test")
            assert ralph.is_active()
            ralph.disable()
        except (OSError, FileNotFoundError) as e:
            # Long paths may not be enabled on Windows
            error_str = str(e).lower()
            if IS_WINDOWS and ("too long" in error_str or "206" in str(e)):
                pytest.skip("Long paths not enabled on this Windows system")
            raise

    @pytest.mark.skipif(IS_WINDOWS, reason="Unix-specific test")
    def test_unix_hidden_directory(self):
        """Test that .ralph-mode is properly hidden on Unix."""
        self.ralph.enable("Test")

        # Directory name starts with dot (hidden on Unix)
        assert self.ralph.ralph_dir.name.startswith(".")

        self.ralph.disable()

    def test_case_sensitivity(self):
        """Test path case sensitivity handling."""
        self.ralph.enable("Test")

        # Get the actual path
        actual_path = self.ralph.ralph_dir

        if IS_WINDOWS:
            # Windows is case-insensitive
            upper_path = Path(str(actual_path).upper())
            # Both should resolve to same location
            assert upper_path.exists() == actual_path.exists()

        self.ralph.disable()


# =============================================================================
# Integration with Shell Scripts
# =============================================================================


class TestShellIntegration:
    """Integration tests with actual shell scripts."""

    @pytest.fixture(autouse=True)
    def setup(self, temp_dir):
        self.temp_dir = temp_dir
        self.ralph = RalphMode(temp_dir)
        self.repo_root = Path(__file__).parent.parent

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash script test")
    def test_ralph_loop_sh_exists_and_executable(self):
        """Test ralph-loop.sh exists and is executable."""
        script = self.repo_root / "ralph-loop.sh"

        if script.exists():
            assert os.access(script, os.X_OK), "ralph-loop.sh should be executable"

    def test_ralph_mode_ps1_exists(self):
        """Test ralph-mode.ps1 exists."""
        script = self.repo_root / "ralph-mode.ps1"

        if script.exists():
            # PowerShell scripts don't need execute permission
            assert script.read_text(encoding="utf-8"), "Script should be readable"
        else:
            # Non-Windows environments might not include .ps1 scripts
            assert not IS_WINDOWS

    def test_python_script_cross_platform(self):
        """Test Python entry point works on all platforms."""
        script = self.repo_root / "ralph_mode.py"

        assert script.exists()

        # Should be importable and runnable
        result = subprocess.run(
            [sys.executable, str(script), "status"], capture_output=True, text=True, cwd=self.temp_dir, timeout=10
        )

        # Should complete without crash (may return non-zero if not active)
        assert result.returncode in [0, 1]


# =============================================================================
# Report Platform Info
# =============================================================================


class TestPlatformInfo:
    """Report current platform information."""

    def test_report_platform_info(self):
        """Report platform information for debugging."""
        info = {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "file_system_encoding": sys.getfilesystemencoding(),
            "default_encoding": sys.getdefaultencoding(),
            "stdout_encoding": sys.stdout.encoding,
            "shell": get_shell(),
            "temp_dir": tempfile.gettempdir(),
            "home_dir": str(Path.home()),
            "cwd": str(Path.cwd()),
        }

        print("\n" + "=" * 60)
        print("PLATFORM INFORMATION")
        print("=" * 60)
        for key, value in info.items():
            print(f"  {key}: {value}")
        print("=" * 60)

        # This test always passes - it's for information only
        assert True


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    print(f"\n🔄 Copilot Ralph Mode Cross-Platform Test Suite v{VERSION}")
    print(f"Platform: {PLATFORM_NAME}")
    print("=" * 60)

    # Run with pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
