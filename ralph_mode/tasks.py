"""Task library manager for loading tasks from files."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class TaskLibrary:
    """Task library manager for loading tasks from files."""

    TASKS_DIR = "tasks"
    GROUPS_DIR = "_groups"

    def __init__(self, base_path: Optional[Path] = None) -> None:
        """Initialize task library."""
        self.base_path = Path(base_path) if base_path else Path(__file__).parent.parent
        self.tasks_dir = self.base_path / self.TASKS_DIR
        self.groups_dir = self.tasks_dir / self.GROUPS_DIR

    def parse_task_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse a task markdown file with YAML frontmatter."""
        content = file_path.read_text(encoding="utf-8")

        # Parse YAML frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    # Simple YAML parsing without external deps
                    frontmatter: Dict[str, Any] = {}
                    for line in parts[1].strip().split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            key = key.strip()
                            value_str = value.strip()
                            # Handle arrays
                            if value_str.startswith("[") and value_str.endswith("]"):
                                frontmatter[key] = [v.strip().strip("\"'") for v in value_str[1:-1].split(",")]
                            # Handle numbers
                            elif value_str.isdigit():
                                frontmatter[key] = int(value_str)
                            else:
                                frontmatter[key] = value_str

                    return {**frontmatter, "prompt": parts[2].strip(), "file": str(file_path)}
                except Exception:
                    pass

        # Fallback: use filename as ID
        return {
            "id": file_path.stem.upper(),
            "title": file_path.stem.replace("-", " ").title(),
            "prompt": content,
            "file": str(file_path),
        }

    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all available tasks."""
        tasks: List[Dict[str, Any]] = []
        if not self.tasks_dir.exists():
            return tasks

        for file_path in sorted(self.tasks_dir.glob("*.md")):
            if file_path.name.startswith("_") or file_path.name == "README.md":
                continue
            try:
                task = self.parse_task_file(file_path)
                tasks.append(task)
            except Exception:
                pass

        return tasks

    def list_groups(self) -> List[Dict[str, Any]]:
        """List all task groups."""
        groups: List[Dict[str, Any]] = []
        if not self.groups_dir.exists():
            return groups

        for file_path in sorted(self.groups_dir.glob("*.json")):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                data["file"] = str(file_path)
                groups.append(data)
            except Exception:
                pass

        return groups

    def get_task(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID, filename, or partial match."""
        identifier_lower = identifier.lower()

        # Try exact filename match first
        exact_path = self.tasks_dir / identifier
        if exact_path.exists():
            return self.parse_task_file(exact_path)

        # Try with .md extension
        if not identifier.endswith(".md"):
            exact_path = self.tasks_dir / f"{identifier}.md"
            if exact_path.exists():
                return self.parse_task_file(exact_path)

        # Search by ID or title
        for task in self.list_tasks():
            task_id = str(task.get("id", "")).lower()
            task_title = str(task.get("title", "")).lower()
            task_file = Path(task.get("file", "")).stem.lower()

            if identifier_lower in [task_id, task_file]:
                return task
            if identifier_lower in task_title:
                return task

        return None

    def get_group(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a task group by name."""
        name_lower = name.lower()

        # Try exact filename
        exact_path = self.groups_dir / f"{name}.json"
        if exact_path.exists():
            try:
                return json.loads(exact_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Search by name
        for group in self.list_groups():
            if group.get("name", "").lower() == name_lower:
                return group

        return None

    def get_group_tasks(self, group_name: str) -> List[Dict[str, Any]]:
        """Get all tasks in a group."""
        group = self.get_group(group_name)
        if not group:
            return []

        tasks: List[Dict[str, Any]] = []
        for task_ref in group.get("tasks", []):
            task = self.get_task(task_ref)
            if task:
                tasks.append(task)

        return tasks

    def search_tasks(self, query: str) -> List[Dict[str, Any]]:
        """Search tasks by query string."""
        query_lower = query.lower()
        results: List[Dict[str, Any]] = []

        for task in self.list_tasks():
            task_id = task.get("id", "").lower()
            task_title = task.get("title", "").lower()
            task_tags = task.get("tags", [])
            task_prompt = task.get("prompt", "").lower()

            if (
                query_lower in task_id
                or query_lower in task_title
                or query_lower in task_prompt
                or any(query_lower in str(tag).lower() for tag in task_tags)
            ):
                results.append(task)

        return results
