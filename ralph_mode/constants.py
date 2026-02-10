"""Constants and configuration for Ralph Mode."""

import os
import sys

VERSION = "1.1.0"

# Default model configuration
DEFAULT_MODEL = "gpt-5.2-codex"
FALLBACK_MODEL = "auto"
AVAILABLE_MODELS = [
    "auto",
    "claude-sonnet-4.5",
    "claude-haiku-4.5",
    "claude-opus-4.5",
    "claude-sonnet-4",
    "gemini-3-pro-preview",
    "gpt-5.2-codex",
    "gpt-5.2",
    "gpt-5.1-codex-max",
    "gpt-5.1-codex",
    "gpt-5.1",
    "gpt-5",
    "gpt-5.1-codex-mini",
    "gpt-5-mini",
    "gpt-4.1",
]

REQUIRED_TASK_SECTIONS = [
    "## Objective",
    "## Scope",
    "## Pre-work",
    "## Changes Required",
    "## Acceptance Criteria",
    "## Verification",
    "## Completion",
]

REQUIRED_SCOPE_MARKERS = [
    "ONLY modify",
    "DO NOT read",
    "DO NOT touch",
]

STRICT_TASKS = os.environ.get("RALPH_STRICT_TASKS") == "1"
STRICT_ROOT = os.environ.get("RALPH_STRICT_ROOT") == "1"


class Colors:
    """ANSI color codes for terminal output."""

    def __init__(self) -> None:
        self.enabled = self._check_color_support()

    def _check_color_support(self) -> bool:
        """Check if terminal supports colors."""
        if os.name == "nt":  # Windows
            try:
                import colorama

                colorama.init()
                return True
            except ImportError:
                return os.environ.get("TERM") is not None
        return sys.stdout.isatty()

    @property
    def RED(self) -> str:
        return "\033[0;31m" if self.enabled else ""

    @property
    def GREEN(self) -> str:
        return "\033[0;32m" if self.enabled else ""

    @property
    def YELLOW(self) -> str:
        return "\033[1;33m" if self.enabled else ""

    @property
    def BLUE(self) -> str:
        return "\033[0;34m" if self.enabled else ""

    @property
    def CYAN(self) -> str:
        return "\033[0;36m" if self.enabled else ""

    @property
    def NC(self) -> str:
        return "\033[0m" if self.enabled else ""


colors = Colors()
