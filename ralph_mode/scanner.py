"""Security scanning integration (CodeQL + grep fallback)."""

import json
import os
import re
import shutil
import subprocess
from typing import Any, Dict, List

from .constants import colors
from .memory import MemoryStore
from .state import RalphMode


def _detect_language(base_path: str) -> str:
    """Auto-detect the primary language of the project."""
    markers = {
        "package.json": "javascript",
        "tsconfig.json": "javascript",
        "go.mod": "go",
        "pyproject.toml": "python",
        "setup.py": "python",
        "requirements.txt": "python",
        "Cargo.toml": "rust",
        "pom.xml": "java",
        "build.gradle": "java",
        "build.gradle.kts": "java",
    }
    for marker, lang in markers.items():
        if os.path.exists(os.path.join(base_path, marker)):
            return lang
    # Check for .csproj files
    for f in os.listdir(base_path):
        if f.endswith(".csproj") or f.endswith(".sln"):
            return "csharp"
    return "unknown"


def _parse_sarif(sarif_path: str) -> List[Dict[str, Any]]:
    """Parse a SARIF file and return a list of alert dicts."""
    if not os.path.exists(sarif_path):
        return []
    with open(sarif_path) as f:
        sarif = json.load(f)
    results: List[Dict[str, Any]] = []
    for run in sarif.get("runs", []):
        for r in run.get("results", []):
            rule = r.get("ruleId", "unknown")
            level = r.get("level", "warning")
            msg = r.get("message", {}).get("text", "")
            locs = r.get("locations", [])
            loc = locs[0].get("physicalLocation", {}) if locs else {}
            file_uri = loc.get("artifactLocation", {}).get("uri", "?")
            line = loc.get("region", {}).get("startLine", "?")
            results.append(
                {
                    "rule": rule,
                    "level": level,
                    "message": msg,
                    "file": file_uri,
                    "line": line,
                }
            )
    return results


def _quick_grep_scan(base_path: str, language: str) -> List[Dict[str, Any]]:
    """Fallback grep-based scan for common security patterns (no CodeQL needed)."""
    patterns: Dict[str, list] = {
        "python": [
            (r"eval\s*\(", "Possible use of eval()"),
            (r"exec\s*\(", "Possible use of exec()"),
            (r"os\.system\s*\(", "Possible shell injection via os.system"),
            (r"subprocess\.call\s*\(.*shell\s*=\s*True", "Shell=True in subprocess"),
            (r"pickle\.loads?\s*\(", "Unsafe deserialization with pickle"),
        ],
        "javascript": [
            (r"eval\s*\(", "Possible use of eval()"),
            (r"innerHTML\s*=", "Possible XSS via innerHTML"),
            (r"document\.write\s*\(", "Possible XSS via document.write"),
            (r"child_process\.exec\s*\(", "Possible command injection"),
        ],
        "go": [
            (r"exec\.Command\s*\(", "Possible command injection"),
            (r"sql\.Query\s*\(.*\+", "Possible SQL injection (string concat)"),
        ],
    }
    lang_patterns = patterns.get(language, [])
    if not lang_patterns:
        return []

    ext_map = {"python": "*.py", "javascript": "*.js", "go": "*.go"}
    ext = ext_map.get(language, "*")
    findings: List[Dict[str, Any]] = []

    for root, _dirs, files in os.walk(base_path):
        # Skip hidden dirs and common non-source dirs
        if any(
            part.startswith(".") or part in ("node_modules", "dist", "build", "__pycache__", "venv")
            for part in root.split(os.sep)
        ):
            continue
        for fname in files:
            if ext != "*" and not fname.endswith(ext.lstrip("*")):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        for pattern, desc in lang_patterns:
                            if re.search(pattern, line):
                                findings.append(
                                    {
                                        "rule": "grep-scan",
                                        "level": "note",
                                        "message": desc,
                                        "file": os.path.relpath(fpath, base_path),
                                        "line": i,
                                    }
                                )
            except (OSError, UnicodeDecodeError):
                continue
    return findings


def cmd_scan(args: Any) -> int:
    """Handle scan command - run security scan on the project."""
    ralph = RalphMode()
    base_path = str(ralph.base_path) if ralph.is_active() else os.getcwd()
    quiet = getattr(args, "quiet", False)
    changed_only = getattr(args, "changed_only", False)
    language = getattr(args, "language", None) or _detect_language(base_path)
    sarif_dir = os.path.join(base_path, ".ralph-mode")
    sarif_path = os.path.join(sarif_dir, "scan-results.sarif")
    os.makedirs(sarif_dir, exist_ok=True)

    if language == "unknown":
        if not quiet:
            print(f"{colors.YELLOW}⚠️  Could not detect project language. Use --language to specify.{colors.NC}")
        return 0  # non-blocking

    has_codeql = shutil.which("codeql") is not None
    used_codeql = False
    results: List[Dict[str, Any]] = []

    if has_codeql:
        # --- CodeQL scan ---
        db_dir = os.path.join(sarif_dir, "codeql-db")
        if not quiet:
            print(f"{colors.CYAN}🔍 Running CodeQL scan ({language})...{colors.NC}")

        # Create or update database
        try:
            create_cmd = ["codeql", "database", "create", db_dir, f"--language={language}", "--overwrite"]
            subprocess.run(create_cmd, capture_output=True, timeout=600)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            if not quiet:
                print(f"{colors.YELLOW}⚠️  CodeQL database creation timed out, falling back to grep scan{colors.NC}")
            has_codeql = False

        if has_codeql:
            # Run analysis
            suite = f"codeql/{language}-queries:codeql-suites/{language}-security-and-quality.qls"
            try:
                analyze_cmd = [
                    "codeql",
                    "database",
                    "analyze",
                    db_dir,
                    suite,
                    "--format=sarif-latest",
                    f"--output={sarif_path}",
                ]
                subprocess.run(analyze_cmd, capture_output=True, timeout=600)
                results = _parse_sarif(sarif_path)
                used_codeql = True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                if not quiet:
                    print(f"{colors.YELLOW}⚠️  CodeQL analysis timed out, falling back to grep scan{colors.NC}")

    if not used_codeql:
        # --- Grep-based fallback scan ---
        if not quiet:
            print(f"{colors.CYAN}🔍 Running grep-based scan ({language})...{colors.NC}")
        results = _quick_grep_scan(base_path, language)

    # Filter to changed files only if requested
    if changed_only and results:
        try:
            diff_output = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1"], capture_output=True, text=True, cwd=base_path
            )
            changed_files = set(diff_output.stdout.strip().splitlines())
            results = [r for r in results if r.get("file") in changed_files]
        except (FileNotFoundError, subprocess.SubprocessError):
            pass  # can't filter, show all

    # Output
    if not results:
        if not quiet:
            print(f"{colors.GREEN}✅ No security issues found{colors.NC}")
        return 0

    # Group by severity
    errors = [r for r in results if r["level"] == "error"]
    warnings = [r for r in results if r["level"] == "warning"]
    notes = [r for r in results if r["level"] not in ("error", "warning")]

    engine = "CodeQL" if used_codeql else "grep-scan"
    if not quiet:
        print(f"\n{colors.YELLOW}📋 Scan Results ({engine}) — {len(results)} finding(s){colors.NC}")
        if errors:
            print(f"  {colors.RED}Errors: {len(errors)}{colors.NC}")
        if warnings:
            print(f"  {colors.YELLOW}Warnings: {len(warnings)}{colors.NC}")
        if notes:
            print(f"  {colors.CYAN}Notes: {len(notes)}{colors.NC}")
        print()
        for r in results[:20]:
            level_color = (
                colors.RED if r["level"] == "error" else (colors.YELLOW if r["level"] == "warning" else colors.CYAN)
            )
            print(f"  {level_color}[{r['level']}]{colors.NC} {r['rule']} @ {r['file']}:{r['line']}")
            if r["message"]:
                print(f"    {r['message'][:120]}")
        if len(results) > 20:
            print(f"\n  ... and {len(results) - 20} more")
    else:
        # Quiet mode: just summary line
        print(f"scan: {len(errors)} errors, {len(warnings)} warnings, {len(notes)} notes ({engine})")

    # Save to memory if Ralph is active
    if ralph.is_active():
        summary = f"Security scan ({engine}): {len(errors)} errors, {len(warnings)} warnings, {len(notes)} notes"
        try:
            store = MemoryStore(ralph)
            store.add(
                content=summary,
                memory_type="episodic",
                category="errors",
            )
        except Exception:
            pass  # Memory is optional; never block scan output

    return 1 if errors else 0
