"""Verification command extraction and execution."""

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _extract_section(prompt: str, header: str) -> str:
    """Extract a markdown section body by header name."""
    if not prompt:
        return ""
    pattern = re.compile(rf"^{re.escape(header)}\s*$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(prompt)
    if not match:
        return ""
    start = match.end()
    remainder = prompt[start:]
    next_header = re.search(r"^##\s+", remainder, flags=re.MULTILINE)
    if next_header:
        return remainder[: next_header.start()].strip()
    return remainder.strip()


def _extract_verification_commands(prompt: str) -> List[str]:
    """Parse verification commands from the prompt's Verification section."""
    section = _extract_section(prompt, "## Verification")
    if not section:
        return []

    commands: List[str] = []
    code_blocks = re.findall(r"```(?:bash|sh)?\n(.*?)```", section, flags=re.DOTALL | re.IGNORECASE)
    for block in code_blocks:
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("$"):
                stripped = stripped.lstrip("$ ")
            commands.append(stripped)

    if commands:
        return commands

    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("$"):
            commands.append(stripped.lstrip("$ "))
        elif stripped.startswith("- "):
            commands.append(stripped[2:])
        elif re.match(r"\d+\.\s+", stripped):
            commands.append(re.sub(r"^\d+\.\s+", "", stripped))

    return [cmd for cmd in commands if cmd]


def _truncate_output(text: str, max_lines: int = 200) -> str:
    """Truncate output to a maximum number of lines."""
    lines = text.strip().splitlines()
    if len(lines) <= max_lines:
        return text.strip()
    truncated = lines[:max_lines] + [f"... ({len(lines) - max_lines} more lines)"]
    return "\n".join(truncated)


def _run_verification_commands(
    commands: List[str],
    cwd: Path,
    timeout: int = 120,
) -> Tuple[bool, List[Dict[str, Any]]]:
    """Run verification commands and collect structured results."""
    results: List[Dict[str, Any]] = []
    all_ok = True
    for cmd in commands:
        try:
            completed = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd),
            )
            stdout = _truncate_output(completed.stdout or "", max_lines=120)
            stderr = _truncate_output(completed.stderr or "", max_lines=60)
            ok = completed.returncode == 0
            if not ok:
                all_ok = False
            results.append(
                {
                    "command": cmd,
                    "ok": ok,
                    "returncode": completed.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                }
            )
        except subprocess.TimeoutExpired:
            all_ok = False
            results.append(
                {
                    "command": cmd,
                    "ok": False,
                    "returncode": None,
                    "stdout": "",
                    "stderr": f"Timed out after {timeout}s",
                }
            )
    return all_ok, results
