"""Helper functions for Ralph Mode CLI."""

import json
from pathlib import Path
from typing import List, Optional

from .constants import REQUIRED_SCOPE_MARKERS, REQUIRED_TASK_SECTIONS, colors
from .state import RalphMode


def print_banner(title: str) -> None:
    """Print a colored banner."""
    width = 60
    print()
    print(f"{colors.GREEN}╔{'═' * width}╗{colors.NC}")
    print(f"{colors.GREEN}║{title:^{width}}║{colors.NC}")
    print(f"{colors.GREEN}╚{'═' * width}╝{colors.NC}")
    print()


def _find_git_root(path: Path) -> Optional[Path]:
    """Find the nearest git root from the given path."""
    current = path.resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            return parent
    return None


def _ensure_project_root(strict: bool = False) -> bool:
    """Warn or error if not running from project root."""
    cwd = Path.cwd()
    git_root = _find_git_root(cwd)
    if git_root and git_root != cwd:
        message = "Run Ralph from the project root. " f"Detected git root at: {git_root}. Current: {cwd}."
        if strict:
            print(f"{colors.RED}❌ Error: {message}{colors.NC}")
            return False
        print(f"{colors.YELLOW}⚠️ Warning: {message}{colors.NC}")
    return True


def _missing_task_requirements(prompt: str) -> List[str]:
    """Return a list of missing task sections or scope markers."""
    missing: List[str] = []
    normalized = prompt.lower()

    for section in REQUIRED_TASK_SECTIONS:
        if section.lower() not in normalized:
            missing.append(section)

    for marker in REQUIRED_SCOPE_MARKERS:
        if marker.lower() not in normalized:
            missing.append(marker)

    return missing


def _validate_task_prompt(task_label: str, prompt: str, strict: bool = False) -> bool:
    """Validate task prompt against required sections and scope markers."""
    if not prompt.strip():
        missing = REQUIRED_TASK_SECTIONS + REQUIRED_SCOPE_MARKERS
    else:
        missing = _missing_task_requirements(prompt)

    if not missing:
        return True

    missing_list = ", ".join(missing)
    message = f"Task '{task_label}' is missing required sections or scope rules: {missing_list}"
    if strict:
        print(f"{colors.RED}❌ Error: {message}{colors.NC}")
        return False
    print(f"{colors.YELLOW}⚠️ Warning: {message}{colors.NC}")
    return True


def _load_prompt_for_validation(prompt_parts: Optional[List[str]], ralph: RalphMode) -> str:
    """Load prompt for validation from args or active state."""
    if prompt_parts:
        return " ".join(prompt_parts).strip()
    if ralph.is_active():
        return (ralph.get_prompt() or "").strip()
    return ""


def _load_tasks_from_file(tasks_file: str) -> list:
    """Load tasks from a JSON file."""
    path = Path(tasks_file)
    if not path.exists():
        raise ValueError(f"Tasks file not found: {tasks_file}")

    if path.suffix.lower() != ".json":
        raise ValueError("Tasks file must be a .json file")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in tasks file: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError("Tasks file must contain a JSON array")

    return data
