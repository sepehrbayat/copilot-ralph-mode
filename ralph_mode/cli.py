"""CLI commands and entry point for Ralph Mode."""

import argparse
import importlib
import sys

from .constants import AVAILABLE_MODELS, DEFAULT_MODEL, FALLBACK_MODEL, STRICT_ROOT, STRICT_TASKS, VERSION, colors
from .helpers import (
    _ensure_project_root,
    _load_prompt_for_validation,
    _load_tasks_from_file,
    _validate_task_prompt,
    print_banner,
)
from .scanner import cmd_scan
from .verification import _extract_verification_commands, _run_verification_commands


def _pkg():
    return importlib.import_module("ralph_mode")


def cmd_enable(args: argparse.Namespace) -> int:
    """Handle enable command."""
    if not _ensure_project_root(strict=STRICT_ROOT):
        return 1

    pkg = _pkg()
    ralph = pkg.RalphMode()

    prompt = " ".join(args.prompt) if args.prompt else ""
    if not prompt:
        print(f"{colors.RED}❌ Error: No prompt provided{colors.NC}")
        print('\nUsage: ralph-mode enable "Your task description" [options]')
        return 1

    if not _validate_task_prompt("manual prompt", prompt, strict=STRICT_TASKS):
        return 1

    # Validate model if provided
    model = args.model
    if model and model != "auto" and model not in AVAILABLE_MODELS:
        print(f"{colors.YELLOW}⚠️ Warning: Model '{model}' may not be available. Using anyway...{colors.NC}")

    try:
        state = ralph.enable(
            prompt=prompt,
            max_iterations=args.max_iterations,
            completion_promise=args.completion_promise,
            model=model,
            auto_agents=args.auto_agents,
        )
    except ValueError as e:
        print(f"{colors.RED}❌ Error: {e}{colors.NC}")
        return 1

    print_banner("🔄 RALPH MODE ENABLED")

    print(f"{colors.CYAN}Iteration:{colors.NC}          1")
    print(
        f"{colors.CYAN}Max Iterations:{colors.NC}     {args.max_iterations if args.max_iterations > 0 else 'unlimited'}"
    )
    print(f"{colors.CYAN}Model:{colors.NC}              {state.get('model', DEFAULT_MODEL)}")
    print(f"{colors.CYAN}Fallback:{colors.NC}           {state.get('fallback_model', FALLBACK_MODEL)}")
    print(f"{colors.CYAN}Auto-Agents:{colors.NC}        {'enabled' if args.auto_agents else 'disabled'}")
    print(f"{colors.CYAN}Completion Promise:{colors.NC} {args.completion_promise or 'none'}")
    print()
    print(f"{colors.YELLOW}📝 Task:{colors.NC}")
    print(prompt)
    print()

    if args.completion_promise:
        print(f"{colors.YELLOW}{'═' * 60}{colors.NC}")
        print(f"{colors.YELLOW}COMPLETION PROMISE REQUIREMENTS{colors.NC}")
        print(f"{colors.YELLOW}{'═' * 60}{colors.NC}")
        print()
        print("To complete this loop, Copilot must output:")
        print(f"  {colors.GREEN}<promise>{args.completion_promise}</promise>{colors.NC}")
        print()
        print("⚠️  ONLY when the statement is GENUINELY TRUE")
        print(f"{colors.YELLOW}{'═' * 60}{colors.NC}")

    print()
    print(f"{colors.GREEN}✅ Ralph mode is now active!{colors.NC}")
    print(f"{colors.BLUE}ℹ Copilot will read .ralph-mode/INSTRUCTIONS.md for guidance{colors.NC}")

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Handle validate command - check task template requirements."""
    pkg = _pkg()
    ralph = pkg.RalphMode()

    prompt = _load_prompt_for_validation(args.prompt, ralph)
    if not prompt:
        print(f"{colors.RED}❌ No prompt provided and no active Ralph mode{colors.NC}")
        return 1

    strict = bool(args.strict) or not bool(args.warn_only)
    ok = _validate_task_prompt(args.label or "task", prompt, strict=strict)
    if ok:
        print(f"{colors.GREEN}✅ Task template validation passed{colors.NC}")
        return 0
    return 0 if args.warn_only else 1


def cmd_batch_init(args: argparse.Namespace) -> int:
    """Handle batch-init command."""
    if not _ensure_project_root(strict=STRICT_ROOT):
        return 1

    pkg = _pkg()
    ralph = pkg.RalphMode()

    # Validate model if provided
    model = args.model
    if model and model != "auto" and model not in AVAILABLE_MODELS:
        print(f"{colors.YELLOW}⚠️ Warning: Model '{model}' may not be available. Using anyway...{colors.NC}")

    try:
        tasks = _load_tasks_from_file(args.tasks_file)
    except ValueError as e:
        print(f"{colors.RED}❌ Error: {e}{colors.NC}")
        return 1

    for idx, task in enumerate(tasks, start=1):
        if isinstance(task, str):
            task_label = f"TASK-{idx:03d}"
            prompt = task
        else:
            task_label = task.get("id") or f"TASK-{idx:03d}"
            prompt = task.get("prompt", "")

        if not _validate_task_prompt(task_label, prompt, strict=STRICT_TASKS):
            return 1

    try:
        state = ralph.init_batch(
            tasks=tasks,
            max_iterations=args.max_iterations,
            completion_promise=args.completion_promise,
            model=model,
            auto_agents=args.auto_agents,
        )
    except ValueError as e:
        print(f"{colors.RED}❌ Error: {e}{colors.NC}")
        return 1

    print_banner("🔄 RALPH MODE BATCH STARTED")
    print(f"{colors.CYAN}Mode:{colors.NC}             batch")
    print(f"{colors.CYAN}Tasks Total:{colors.NC}      {state.get('tasks_total')}")
    print(f"{colors.CYAN}Current Task:{colors.NC}     1/{state.get('tasks_total')}")
    print(f"{colors.CYAN}Iteration:{colors.NC}        1")
    print(f"{colors.CYAN}Max Iterations:{colors.NC}   {args.max_iterations}")
    print(f"{colors.CYAN}Model:{colors.NC}            {state.get('model', DEFAULT_MODEL)}")
    print(f"{colors.CYAN}Fallback:{colors.NC}         {state.get('fallback_model', FALLBACK_MODEL)}")
    print(f"{colors.CYAN}Auto-Agents:{colors.NC}      {'enabled' if args.auto_agents else 'disabled'}")
    print(f"{colors.CYAN}Completion Promise:{colors.NC} {args.completion_promise or 'none'}")
    print()
    print(f"{colors.YELLOW}📝 Current Task:{colors.NC}")
    print(state.get("current_task_title") or "")
    print()
    print(f"{colors.GREEN}✅ Ralph batch mode is now active!{colors.NC}")
    print(f"{colors.BLUE}ℹ Copilot will read .ralph-mode/INSTRUCTIONS.md for guidance{colors.NC}")

    return 0


def cmd_next_task(args: argparse.Namespace) -> int:
    """Handle next-task command."""
    pkg = _pkg()
    ralph = pkg.RalphMode()

    try:
        state = ralph.next_task(reason="manual_next")
    except ValueError as e:
        print(f"{colors.YELLOW}⚠️ {e}{colors.NC}")
        return 1

    print(f"🔄 Moved to next task: {state.get('current_task_index', 0) + 1}/{state.get('tasks_total', 0)}")
    print(f"{colors.YELLOW}📝 Current Task:{colors.NC} {state.get('current_task_title') or ''}")
    return 0


def cmd_disable(args: argparse.Namespace) -> int:
    """Handle disable command."""
    pkg = _pkg()
    ralph = pkg.RalphMode()

    state = ralph.disable()
    if state:
        print()
        print(f"{colors.GREEN}✅ Ralph mode disabled (was at iteration {state.get('iteration', '?')}){colors.NC}")
    else:
        print(f"{colors.YELLOW}⚠️ No active Ralph mode found{colors.NC}")

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Handle status command."""
    pkg = _pkg()
    ralph = pkg.RalphMode()

    status = ralph.status()
    if not status:
        print()
        print(f"{colors.YELLOW}Ralph Mode: {colors.RED}INACTIVE{colors.NC}")
        print()
        print('To enable: ralph-mode enable "Your task" --max-iterations 20')
        return 0

    print_banner("🔄 RALPH MODE STATUS")

    print(f"{colors.CYAN}Status:{colors.NC}             {colors.GREEN}ACTIVE{colors.NC}")
    print(f"{colors.CYAN}Mode:{colors.NC}               {status.get('mode', 'single')}")
    print(f"{colors.CYAN}Iteration:{colors.NC}          {status.get('iteration', '?')}")
    max_iter = status.get("max_iterations", 0)
    print(f"{colors.CYAN}Max Iterations:{colors.NC}     {max_iter if max_iter > 0 else 'unlimited'}")
    model = status.get("model", DEFAULT_MODEL)
    fallback = status.get("fallback_model", FALLBACK_MODEL)
    print(f"{colors.CYAN}Model:{colors.NC}              {model}")
    print(f"{colors.CYAN}Fallback:{colors.NC}           {fallback}")
    auto_agents = status.get("auto_agents", False)
    print(f"{colors.CYAN}Auto-Agents:{colors.NC}        {'enabled' if auto_agents else 'disabled'}")
    created_agents = status.get("created_agents", [])
    if created_agents:
        print(f"{colors.CYAN}Created Agents:{colors.NC}     {len(created_agents)}")
        for agent in created_agents:
            print(f"  - {agent.get('name', 'unknown')} (iter {agent.get('iteration', '?')})")
    promise = status.get("completion_promise")
    print(f"{colors.CYAN}Completion Promise:{colors.NC} {promise if promise else 'none'}")
    print(f"{colors.CYAN}Started At:{colors.NC}         {status.get('started_at', '?')}")
    print(f"{colors.CYAN}History Entries:{colors.NC}    {status.get('history_entries', 0)}")
    if status.get("mode") == "batch":
        print(f"{colors.CYAN}Tasks Total:{colors.NC}        {status.get('tasks_total', 0)}")
        current_task = status.get("current_task_number", 0)
        total_tasks = status.get("tasks_total", 0)
        print(f"{colors.CYAN}Current Task:{colors.NC}       {current_task}/{total_tasks}")
        print(f"{colors.CYAN}Current Task ID:{colors.NC}    {status.get('current_task_id') or 'n/a'}")
    print()
    print(f"{colors.YELLOW}📝 Current Task:{colors.NC}")
    print(status.get("prompt", "No prompt found"))
    print()

    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    """Handle prompt command."""
    pkg = _pkg()
    ralph = pkg.RalphMode()

    if not ralph.is_active():
        print(f"{colors.RED}❌ No active Ralph mode{colors.NC}")
        return 1

    prompt = ralph.get_prompt()
    if prompt:
        print(prompt)
    else:
        print(f"{colors.RED}❌ No prompt found{colors.NC}")
        return 1

    return 0


def cmd_iterate(args: argparse.Namespace) -> int:
    """Handle iterate command."""
    pkg = _pkg()
    ralph = pkg.RalphMode()

    try:
        state = ralph.iterate()
        print(f"🔄 Ralph iteration: {colors.GREEN}{state['iteration']}{colors.NC}")
    except ValueError as e:
        print(f"{colors.YELLOW}⚠️ {e}{colors.NC}")
        return 1

    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    """Handle complete command - check if output contains promise."""
    pkg = _pkg()
    ralph = pkg.RalphMode()

    if not ralph.is_active():
        print(f"{colors.RED}❌ No active Ralph mode{colors.NC}")
        return 1

    # Read output from stdin or argument
    if args.output:
        output = " ".join(args.output)
    else:
        output = sys.stdin.read()

    try:
        completed = ralph.complete(output)
    except ValueError as e:
        # In batch mode, completing the final task disables Ralph mode and raises
        # ValueError("All tasks completed. Ralph mode disabled.") by design.
        msg = str(e)
        if "All tasks completed" in msg:
            print(f"{colors.GREEN}✅ All tasks completed. Ralph mode disabled.{colors.NC}")
            return 0
        print(f"{colors.RED}❌ Error: {e}{colors.NC}")
        return 1

    if completed:
        state = ralph.get_state()
        if state and state.get("mode") == "batch":
            print(f"{colors.GREEN}✅ Completion promise detected! Moved to next task.{colors.NC}")
            return 0

        print(f"{colors.GREEN}✅ Completion promise detected! Ralph mode disabled.{colors.NC}")
        return 0

    print(f"{colors.YELLOW}⚠️ No completion promise found. Continue iterating.{colors.NC}")
    return 1


def cmd_history(args: argparse.Namespace) -> int:
    """Handle history command."""
    pkg = _pkg()
    ralph = pkg.RalphMode()

    history = ralph.get_history()
    if not history:
        print("No history found.")
        return 0

    print(f"\n{'Iteration':<12} {'Status':<15} {'Timestamp':<25} Notes")
    print("-" * 80)

    for entry in history:
        print(
            f"{entry.get('iteration', '?'):<12} "
            f"{entry.get('status', '?'):<15} "
            f"{entry.get('timestamp', '?')[:19]:<25} "
            f"{entry.get('notes', '')[:30]}"
        )

    print()
    return 0


def cmd_verification(args: argparse.Namespace) -> int:
    """Handle verification command - show or run verification steps."""
    pkg = _pkg()
    ralph = pkg.RalphMode()
    if not ralph.is_active():
        print(f"{colors.RED}❌ No active Ralph mode{colors.NC}")
        return 1

    prompt = ralph.get_prompt() or ""
    commands = _extract_verification_commands(prompt)
    if args.action == "show":
        if not commands:
            print(f"{colors.YELLOW}No verification commands found{colors.NC}")
            return 0
        print("\n".join(commands))
        return 0

    if not commands:
        print(f"{colors.RED}❌ No verification commands found in task prompt{colors.NC}")
        return 1

    ok, results = _run_verification_commands(commands, cwd=ralph.base_path, timeout=args.timeout)
    ctx = pkg.ContextManager(ralph)
    ctx.write_summary_report(exit_code=0 if ok else 1, verification=results)

    for result in results:
        status = f"{colors.GREEN}PASS{colors.NC}" if result.get("ok") else f"{colors.RED}FAIL{colors.NC}"
        print(f"{status} {result.get('command')}")
        if result.get("stderr"):
            print(result["stderr"])

    return 0 if ok else 1


def cmd_tasks(args: argparse.Namespace) -> int:
    """Handle tasks command - list, search, show tasks."""
    pkg = _pkg()
    library = pkg.TaskLibrary()

    action = args.action if hasattr(args, "action") else "list"

    if action == "list":
        tasks = library.list_tasks()
        groups = library.list_groups()

        if not tasks and not groups:
            print(f"{colors.YELLOW}No tasks found in tasks/ directory{colors.NC}")
            print("Create task files like: tasks/my-task.md")
            return 0

        print_banner("📋 TASK LIBRARY")

        if tasks:
            print(f"{colors.CYAN}Tasks:{colors.NC}")
            for task in tasks:
                task_id = task.get("id", "N/A")
                title = task.get("title", "Untitled")
                tags = task.get("tags", [])
                tags_str = f" [{', '.join(tags)}]" if tags else ""
                print(f"  {colors.GREEN}{task_id:<12}{colors.NC} {title}{colors.YELLOW}{tags_str}{colors.NC}")
            print()

        if groups:
            print(f"{colors.CYAN}Groups:{colors.NC}")
            for group in groups:
                name = group.get("name", "N/A")
                title = group.get("title", "Untitled")
                task_count = len(group.get("tasks", []))
                print(f"  {colors.GREEN}{name:<12}{colors.NC} {title} ({task_count} tasks)")
            print()

        return 0

    elif action == "show":
        identifier = args.identifier if hasattr(args, "identifier") else None
        if not identifier:
            print(f"{colors.RED}❌ Please specify a task ID or filename{colors.NC}")
            return 1

        task = library.get_task(identifier)
        if not task:
            print(f"{colors.RED}❌ Task not found: {identifier}{colors.NC}")
            return 1

        print_banner(f"📋 {task.get('id', 'TASK')}")
        print(f"{colors.CYAN}Title:{colors.NC}      {task.get('title', 'Untitled')}")
        print(f"{colors.CYAN}ID:{colors.NC}         {task.get('id', 'N/A')}")
        tags = task.get("tags", [])
        print(f"{colors.CYAN}Tags:{colors.NC}       {', '.join(tags) if tags else 'none'}")
        print(f"{colors.CYAN}Model:{colors.NC}      {task.get('model', DEFAULT_MODEL)}")
        print(f"{colors.CYAN}Max Iter:{colors.NC}   {task.get('max_iterations', 20)}")
        print(f"{colors.CYAN}Promise:{colors.NC}    {task.get('completion_promise', 'DONE')}")
        print(f"{colors.CYAN}File:{colors.NC}       {task.get('file', 'N/A')}")
        print()
        print(f"{colors.YELLOW}📝 Prompt:{colors.NC}")
        print(task.get("prompt", "No prompt"))
        print()

        return 0

    elif action == "search":
        query = args.identifier if hasattr(args, "identifier") and args.identifier else ""
        if not query:
            print(f"{colors.RED}❌ Please specify a search query{colors.NC}")
            return 1

        results = library.search_tasks(query)
        if not results:
            print(f"{colors.YELLOW}No tasks found matching: {query}{colors.NC}")
            return 0

        print(f"\n{colors.GREEN}Found {len(results)} task(s):{colors.NC}\n")
        for task in results:
            task_id = task.get("id", "N/A")
            title = task.get("title", "Untitled")
            print(f"  {colors.GREEN}{task_id:<12}{colors.NC} {title}")
        print()

        return 0

    else:
        print(f"{colors.RED}❌ Unknown action: {action}{colors.NC}")
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    """Handle run command - run a task from library."""
    if not _ensure_project_root(strict=STRICT_ROOT):
        return 1

    pkg = _pkg()
    library = pkg.TaskLibrary()
    ralph = pkg.RalphMode()

    # Check if already active
    if ralph.is_active():
        print(f"{colors.RED}❌ Ralph mode is already active. Use 'disable' first.{colors.NC}")
        return 1

    # Get task or group
    task_id = args.task if hasattr(args, "task") and args.task else None
    group_name = args.group if hasattr(args, "group") and args.group else None

    if not task_id and not group_name:
        print(f"{colors.RED}❌ Please specify --task or --group{colors.NC}")
        print("\nUsage:")
        print("  ralph-mode run --task RTL-001")
        print("  ralph-mode run --task rtl-text-direction.md")
        print("  ralph-mode run --group rtl")
        return 1

    # Handle single task
    if task_id:
        task = library.get_task(task_id)
        if not task:
            print(f"{colors.RED}❌ Task not found: {task_id}{colors.NC}")
            print("\nAvailable tasks:")
            for t in library.list_tasks()[:5]:
                print(f"  - {t.get('id', 'N/A')}")
            return 1

        if not _validate_task_prompt(task.get("id", "TASK"), task.get("prompt", ""), strict=STRICT_TASKS):
            return 1

        # Get options from task file or args
        model = args.model if hasattr(args, "model") and args.model else task.get("model")
        max_iter = (
            args.max_iterations
            if hasattr(args, "max_iterations") and args.max_iterations
            else task.get("max_iterations", 20)
        )
        promise = (
            args.completion_promise
            if hasattr(args, "completion_promise") and args.completion_promise
            else task.get("completion_promise", "DONE")
        )

        try:
            state = ralph.enable(
                prompt=task.get("prompt", ""), max_iterations=max_iter, completion_promise=promise, model=model
            )
        except ValueError as e:
            print(f"{colors.RED}❌ Error: {e}{colors.NC}")
            return 1

        print_banner(f"🔄 RUNNING: {task.get('id', 'TASK')}")
        print(f"{colors.CYAN}Title:{colors.NC}       {task.get('title', 'Untitled')}")
        print(f"{colors.CYAN}Model:{colors.NC}       {state.get('model', DEFAULT_MODEL)}")
        print(f"{colors.CYAN}Max Iter:{colors.NC}    {max_iter}")
        print(f"{colors.CYAN}Promise:{colors.NC}     {promise}")
        print()
        print(f"{colors.GREEN}✅ Task loaded! Run ./ralph-loop.sh run to start.{colors.NC}")

        return 0

    # Handle group
    if group_name:
        tasks = library.get_group_tasks(group_name)
        if not tasks:
            print(f"{colors.RED}❌ Group not found or empty: {group_name}{colors.NC}")
            print("\nAvailable groups:")
            for g in library.list_groups():
                print(f"  - {g.get('name', 'N/A')}")
            return 1

        for task in tasks:
            if not _validate_task_prompt(task.get("id", "TASK"), task.get("prompt", ""), strict=STRICT_TASKS):
                return 1

        # Get options from args
        model = args.model if hasattr(args, "model") and args.model else None
        max_iter = args.max_iterations if hasattr(args, "max_iterations") and args.max_iterations else 20
        promise = args.completion_promise if hasattr(args, "completion_promise") and args.completion_promise else "DONE"

        # Prepare batch tasks
        batch_tasks = []
        for task in tasks:
            batch_tasks.append(
                {
                    "id": task.get("id"),
                    "title": task.get("title"),
                    "prompt": task.get("prompt"),
                    "model": task.get("model", model),
                    "max_iterations": task.get("max_iterations", max_iter),
                    "completion_promise": task.get("completion_promise", promise),
                }
            )

        try:
            state = ralph.init_batch(
                tasks=batch_tasks, max_iterations=max_iter, completion_promise=promise, model=model
            )
        except ValueError as e:
            print(f"{colors.RED}❌ Error: {e}{colors.NC}")
            return 1

        print_banner(f"🔄 RUNNING GROUP: {group_name}")
        print(f"{colors.CYAN}Tasks:{colors.NC}       {len(batch_tasks)}")
        print(f"{colors.CYAN}Model:{colors.NC}       {state.get('model', DEFAULT_MODEL)}")
        print(f"{colors.CYAN}Max Iter:{colors.NC}    {max_iter} per task")
        print()
        print(f"{colors.YELLOW}Tasks in queue:{colors.NC}")
        for i, t in enumerate(batch_tasks, 1):
            print(f"  {i}. {t.get('id', 'N/A')} - {t.get('title', 'Untitled')}")
        print()
        print(f"{colors.GREEN}✅ Group loaded! Run ./ralph-loop.sh run to start.{colors.NC}")

        return 0

    return 1


def cmd_context(args: argparse.Namespace) -> int:
    """Handle context command — build, show, or save iteration context."""
    pkg = _pkg()
    ralph = pkg.RalphMode()
    if not ralph.is_active():
        print(f"{colors.RED}❌ No active Ralph mode{colors.NC}")
        return 1

    ctx = pkg.ContextManager(ralph)
    action = args.action if hasattr(args, "action") else "show"

    if action == "build":
        path = ctx.write_context_file()
        print(f"{colors.GREEN}✅ Context written to {path}{colors.NC}")
        return 0

    elif action == "show":
        content = ctx.build_full_context()
        print(content)
        return 0

    elif action == "save-summary":
        state = ralph.get_state() or {}
        iteration = state.get("iteration", 1)
        action_text = " ".join(args.notes) if hasattr(args, "notes") and args.notes else ""
        ctx.save_iteration_summary(
            iteration=iteration,
            action=action_text or "manual summary save",
        )
        print(f"{colors.GREEN}✅ Iteration {iteration} summary saved{colors.NC}")
        return 0

    elif action == "progress":
        progress = ctx.get_progress()
        if progress:
            print(progress)
        else:
            print(f"{colors.YELLOW}No progress recorded yet{colors.NC}")
        return 0

    elif action == "set-progress":
        text = " ".join(args.notes) if hasattr(args, "notes") and args.notes else ""
        if not text:
            print(f"{colors.RED}❌ Provide progress text{colors.NC}")
            return 1
        ctx.save_progress(text)
        print(f"{colors.GREEN}✅ Progress updated{colors.NC}")
        return 0

    elif action == "memories":
        print(ctx.format_memories())
        return 0

    elif action == "report":
        exit_code = int(args.exit_code) if hasattr(args, "exit_code") and args.exit_code is not None else 0
        path = ctx.write_summary_report(exit_code=exit_code)
        print(f"{colors.GREEN}✅ Summary report written to {path}{colors.NC}")
        return 0

    else:
        print(f"{colors.RED}❌ Unknown context action: {action}{colors.NC}")
        return 1


def cmd_memory(args: argparse.Namespace) -> int:
    """Handle memory command — mem0-inspired long-term memory management."""
    pkg = _pkg()
    ralph = pkg.RalphMode()
    if not ralph.is_active():
        print(f"{colors.RED}❌ No active Ralph mode{colors.NC}")
        return 1

    ctx = pkg.ContextManager(ralph)
    mem = ctx.memory
    action = args.action if hasattr(args, "action") else "stats"

    if action == "add":
        text = " ".join(args.text) if hasattr(args, "text") and args.text else ""
        if not text:
            print(f"{colors.RED}❌ Provide memory text{colors.NC}")
            return 1
        category = args.category if hasattr(args, "category") and args.category else "progress"
        memory_type = args.memory_type if hasattr(args, "memory_type") and args.memory_type else "semantic"
        result = mem.add(
            content=text,
            memory_type=memory_type,
            category=category,
            metadata={"source": "cli"},
        )
        event = result.get("event", "?")
        mem_id = result.get("id", "?")
        if event == "ADD":
            print(f"{colors.GREEN}✅ Memory added: {mem_id}{colors.NC}")
        else:
            print(f"{colors.YELLOW}⚠️ Skipped: {result.get('reason', 'unknown')}{colors.NC}")
        return 0

    elif action == "search":
        query = " ".join(args.text) if hasattr(args, "text") and args.text else ""
        if not query:
            print(f"{colors.RED}❌ Provide search query{colors.NC}")
            return 1
        limit = args.limit if hasattr(args, "limit") and args.limit else 10
        search_result = mem.search(query=query, limit=limit)
        results = search_result.get("results", [])
        if not results:
            print(f"{colors.YELLOW}No matching memories found{colors.NC}")
            return 0
        for r in results:
            score = r.get("score", 0)
            cat = r.get("category", "?")
            mtype = r.get("memory_type", "?")
            content = r.get("content", "")
            it = r.get("iteration", "?")
            print(f"  [{score:.2f}] ({mtype}/{cat}) iter={it}")
            print(f"    {content[:200]}")
            print()
        return 0

    elif action == "stats":
        st = mem.stats()
        print(f"{colors.GREEN}📊 Memory Bank Statistics{colors.NC}")
        print(f"  Total memories:    {st.get('total', 0)}")
        print(f"  By type:")
        for mtype in [mem.WORKING, mem.EPISODIC, mem.SEMANTIC, mem.PROCEDURAL]:
            count = st.get(mtype, 0)
            if count > 0:
                print(f"    {mtype}: {count}")
        cats = st.get("categories", {})
        if cats:
            print(f"  By category:")
            for cat, count in sorted(cats.items()):
                print(f"    {cat}: {count}")
        return 0

    elif action == "extract":
        # Extract memories from last iteration output
        state = ralph.get_state() or {}
        iteration = state.get("iteration", 1)
        # Try multiple output file locations
        output_paths = [
            ralph.ralph_dir / "output" / f"iteration-{iteration}.log",
            ralph.ralph_dir / "output" / "last-output.log",
            ralph.ralph_dir / "output.txt",
        ]
        output_text = ""
        for opath in output_paths:
            if opath.exists():
                output_text = opath.read_text(encoding="utf-8", errors="replace")
                if output_text.strip():
                    break
        if not output_text.strip():
            print(f"{colors.YELLOW}⚠️ No output file found for extraction{colors.NC}")
            return 1
        extracted = mem.extract_from_output(output_text, iteration=iteration)
        print(f"{colors.GREEN}✅ Extracted {len(extracted)} memories from iteration {iteration}{colors.NC}")
        for m in extracted:
            cat = m.get("category", "?")
            content = m.get("content", m.get("memory", ""))
            print(f"  [{cat}] {content[:120]}")
        return 0

    elif action == "show":
        # Show all memories formatted for context
        formatted = mem.format_for_context()
        if formatted:
            print(formatted)
        else:
            print(f"{colors.YELLOW}No memories stored yet{colors.NC}")
        return 0

    elif action == "reset":
        mem.reset()
        print(f"{colors.GREEN}✅ Memory bank cleared{colors.NC}")
        return 0

    elif action == "clear-working":
        mem.reset(memory_type=mem.WORKING)
        print(f"{colors.GREEN}✅ Working memory cleared{colors.NC}")
        return 0

    elif action == "decay":
        count = mem.apply_decay()
        print(f"{colors.GREEN}✅ Decay applied to {count} memories{colors.NC}")
        return 0

    elif action == "promote":
        min_access = args.limit if hasattr(args, "limit") and args.limit else 2
        promoted = mem.promote_memories(min_access=min_access)
        print(f"{colors.GREEN}✅ Promoted {len(promoted)} memories from episodic → semantic{colors.NC}")
        for mid in promoted:
            print(f"  • {mid}")
        return 0

    elif action == "extract-facts":
        # Extract semantic facts from last iteration output
        state = ralph.get_state() or {}
        iteration = state.get("iteration", 1)
        output_paths = [
            ralph.ralph_dir / "output" / f"iteration-{iteration}.log",
            ralph.ralph_dir / "output" / "last-output.log",
            ralph.ralph_dir / "output.txt",
        ]
        output_text = ""
        for opath in output_paths:
            if opath.exists():
                output_text = opath.read_text(encoding="utf-8", errors="replace")
                if output_text.strip():
                    break
        if not output_text.strip():
            print(f"{colors.YELLOW}⚠️ No output file found for fact extraction{colors.NC}")
            return 1
        extracted = mem.extract_facts(output_text, iteration=iteration)
        print(f"{colors.GREEN}✅ Extracted {len(extracted)} facts from iteration {iteration}{colors.NC}")
        for m in extracted:
            cat = m.get("category", "?")
            content = m.get("content", m.get("memory", ""))
            print(f"  [{cat}] {content[:120]}")
        return 0

    else:
        print(f"{colors.RED}❌ Unknown memory action: {action}{colors.NC}")
        return 1


def cmd_help(args: argparse.Namespace) -> int:
    """Handle help command."""
    models_str = ", ".join(AVAILABLE_MODELS[:5]) + "..."
    print(
        f"""
{colors.GREEN}🔄 Copilot Ralph Mode v{VERSION}{colors.NC}

Implementation of the Ralph Wiggum technique for iterative,
self-referential AI development loops with GitHub Copilot.

{colors.YELLOW}USAGE:{colors.NC}
    ralph-mode <command> [options]

{colors.YELLOW}COMMANDS:{colors.NC}
    enable      Enable Ralph mode with a prompt
    run         Run a task from the task library
    tasks       List, search, or show tasks
    batch-init  Initialize batch mode with multiple tasks
    disable     Disable Ralph mode
    status      Show current status
    prompt      Show current prompt
    iterate     Increment iteration counter
    next-task   Move to next task in batch mode
    complete    Check if output contains completion promise
    validate    Validate task template requirements
    verify      Show or run verification commands
    scan        Run security scan (CodeQL or grep fallback)
    context     Advanced context management
    memory      Long-term memory management (mem0-inspired)
    history     Show iteration history
    help        Show this help message

{colors.YELLOW}CONTEXT COMMANDS:{colors.NC}
    context show            Show full context that AI receives
    context build           Write context to .ralph-mode/context.md
    context save-summary    Record iteration summary
    context progress        Show cumulative progress
    context set-progress    Update cumulative progress
    context memories        Show iteration-by-iteration memory
    context report          Write iteration summary report

{colors.YELLOW}MEMORY COMMANDS (mem0-inspired):{colors.NC}
    memory stats            Show memory bank statistics
    memory show             Show all memories formatted for context
    memory add <text>       Add a memory (--category, --level)
    memory search <query>   Search memories by relevance (--limit)
    memory extract          Extract memories from last iteration output
    memory extract-facts    Extract semantic facts from iteration output
    memory decay            Apply temporal decay to old memory scores
    memory promote          Promote frequently-accessed episodic → semantic
    memory reset            Clear all memories

{colors.YELLOW}TASK LIBRARY:{colors.NC}
    tasks list              List all available tasks
    tasks show <id>         Show task details
    tasks search <query>    Search tasks
    run --task <id>         Run a single task
    run --group <name>      Run a group of tasks

{colors.YELLOW}ENABLE OPTIONS:{colors.NC}
    --max-iterations <n>        Maximum iterations (default: 0 = unlimited)
    --completion-promise <text> Phrase that signals completion
    --model <model>             AI model to use (default: {DEFAULT_MODEL})

{colors.YELLOW}BATCH OPTIONS:{colors.NC}
    --tasks-file <path>          JSON file with tasks list
    --max-iterations <n>         Maximum iterations per task (default: 20)
    --completion-promise <text>  Phrase that signals completion
    --model <model>              AI model to use (default: {DEFAULT_MODEL})

{colors.YELLOW}MODEL OPTIONS:{colors.NC}
    auto                         Automatic model selection
    {DEFAULT_MODEL}                    Default model (recommended for coding)
    Available: {models_str}

{colors.YELLOW}EXAMPLES:{colors.NC}
    ralph-mode enable "Build a REST API" --max-iterations 20
    ralph-mode run --task RTL-001
    ralph-mode run --group rtl
    ralph-mode tasks list
    ralph-mode tasks show RTL-001
    ralph-mode enable "Fix tests" --model claude-sonnet-4.5
    ralph-mode batch-init --tasks-file tasks.json --max-iterations 20
    ralph-mode status
    ralph-mode disable
    ralph-mode verify show
    ralph-mode verify run
    ralph-mode scan
    ralph-mode scan --language python --changed-only

{colors.YELLOW}PHILOSOPHY:{colors.NC}
    • Iteration > Perfection
    • Failures Are Data
    • Persistence Wins

{colors.YELLOW}LEARN MORE:{colors.NC}
    • Original technique: https://ghuntley.com/ralph/
    • Claude Code plugin: https://github.com/anthropics/claude-code
"""
    )
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="ralph-mode", description="Copilot Ralph Mode - Iterative AI development loops"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Enable command
    enable_parser = subparsers.add_parser("enable", help="Enable Ralph mode")
    enable_parser.add_argument("prompt", nargs="*", help="Task prompt")
    enable_parser.add_argument("--max-iterations", type=int, default=0, help="Maximum iterations (0 = unlimited)")
    enable_parser.add_argument("--completion-promise", type=str, default=None, help="Phrase that signals completion")
    enable_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"AI model to use (default: {DEFAULT_MODEL}, fallback: {FALLBACK_MODEL}). "
        f'Use "auto" for automatic selection.',
    )
    enable_parser.add_argument(
        "--auto-agents", action="store_true", default=False, help="Enable dynamic sub-agent creation during iterations"
    )
    enable_parser.set_defaults(func=cmd_enable)

    # Batch init command
    batch_parser = subparsers.add_parser("batch-init", help="Initialize batch mode")
    batch_parser.add_argument("--tasks-file", required=True, help="Path to tasks JSON file")
    batch_parser.add_argument(
        "--max-iterations", type=int, default=20, help="Maximum iterations per task (default: 20)"
    )
    batch_parser.add_argument("--completion-promise", type=str, default=None, help="Phrase that signals completion")
    batch_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"AI model to use (default: {DEFAULT_MODEL}, fallback: {FALLBACK_MODEL}). "
        f'Use "auto" for automatic selection.',
    )
    batch_parser.add_argument(
        "--auto-agents", action="store_true", default=False, help="Enable dynamic sub-agent creation during iterations"
    )
    batch_parser.set_defaults(func=cmd_batch_init)

    # Disable command
    disable_parser = subparsers.add_parser("disable", help="Disable Ralph mode")
    disable_parser.set_defaults(func=cmd_disable)

    # Status command
    status_parser = subparsers.add_parser("status", help="Show status")
    status_parser.set_defaults(func=cmd_status)

    # Prompt command
    prompt_parser = subparsers.add_parser("prompt", help="Show current prompt")
    prompt_parser.set_defaults(func=cmd_prompt)

    # Iterate command
    iterate_parser = subparsers.add_parser("iterate", help="Increment iteration")
    iterate_parser.set_defaults(func=cmd_iterate)

    # Next task command
    next_parser = subparsers.add_parser("next-task", help="Move to next task in batch mode")
    next_parser.set_defaults(func=cmd_next_task)

    # Complete command
    complete_parser = subparsers.add_parser("complete", help="Check completion")
    complete_parser.add_argument("output", nargs="*", help="Output to check")
    complete_parser.set_defaults(func=cmd_complete)

    # History command
    history_parser = subparsers.add_parser("history", help="Show history")
    history_parser.set_defaults(func=cmd_history)

    # Verification command
    verify_parser = subparsers.add_parser("verify", help="Show or run verification commands")
    verify_parser.add_argument("action", choices=["show", "run"], help="Verification action")
    verify_parser.add_argument("--timeout", type=int, default=120, help="Timeout per command (seconds)")
    verify_parser.set_defaults(func=cmd_verification)

    # Tasks command (task library)
    tasks_parser = subparsers.add_parser("tasks", help="Manage task library")
    tasks_parser.add_argument("action", choices=["list", "show", "search"], help="Action to perform")
    tasks_parser.add_argument("identifier", nargs="?", default=None, help="Task ID, filename, or search query")
    tasks_parser.set_defaults(func=cmd_tasks)

    # Run command (run from task library)
    run_parser = subparsers.add_parser("run", help="Run task from library")
    run_parser.add_argument("--task", type=str, default=None, help="Task ID or filename to run")
    run_parser.add_argument("--group", type=str, default=None, help="Task group name to run")
    run_parser.add_argument(
        "--model", type=str, default=None, help=f"Override model (default from task file or {DEFAULT_MODEL})"
    )
    run_parser.add_argument("--max-iterations", type=int, default=None, help="Override max iterations")
    run_parser.add_argument("--completion-promise", type=str, default=None, help="Override completion promise")
    run_parser.set_defaults(func=cmd_run)

    # Context command (advanced contexting)
    context_parser = subparsers.add_parser("context", help="Advanced context management")
    context_parser.add_argument(
        "action",
        choices=["show", "build", "save-summary", "progress", "set-progress", "memories", "report"],
        help="Context action",
    )
    context_parser.add_argument("notes", nargs="*", default=None, help="Notes or text for save-summary/set-progress")
    context_parser.add_argument("--exit-code", type=int, default=None, help="Exit code for report action")
    context_parser.set_defaults(func=cmd_context)

    # Memory command (mem0-inspired long-term memory)
    memory_parser = subparsers.add_parser("memory", help="Long-term memory management (mem0-inspired)")
    memory_parser.add_argument(
        "action",
        choices=[
            "add",
            "search",
            "stats",
            "extract",
            "extract-facts",
            "show",
            "reset",
            "decay",
            "promote",
            "clear-working",
        ],
        help="Memory action",
    )
    memory_parser.add_argument("text", nargs="*", default=None, help="Text for add/search")
    memory_parser.add_argument(
        "--category",
        choices=[
            "file_changes",
            "errors",
            "decisions",
            "blockers",
            "progress",
            "patterns",
            "dependencies",
            "test_results",
            "environment",
            "task_context",
        ],
        default="progress",
        help="Memory category (for add)",
    )
    memory_parser.add_argument(
        "--memory-type",
        choices=["working", "episodic", "semantic", "procedural"],
        default="semantic",
        help="Memory type (for add): working=short-term, episodic=per-iteration, semantic=facts, procedural=workflows",
    )
    memory_parser.add_argument("--limit", type=int, default=10, help="Max results (for search)")
    memory_parser.set_defaults(func=cmd_memory)

    # Help command
    help_parser = subparsers.add_parser("help", help="Show help")
    help_parser.set_defaults(func=cmd_help)

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate task template requirements")
    validate_parser.add_argument("prompt", nargs="*", help="Prompt to validate (defaults to active prompt)")
    validate_parser.add_argument("--label", type=str, default="task", help="Label for the task in messages")
    validate_parser.add_argument("--strict", action="store_true", default=False, help="Fail on missing sections")
    validate_parser.add_argument("--warn-only", action="store_true", default=False, help="Warn but return success")
    validate_parser.set_defaults(func=cmd_validate)

    # Scan command (CodeQL / security scanning)
    scan_parser = subparsers.add_parser("scan", help="Run security scan (CodeQL or grep fallback)")
    scan_parser.add_argument("--language", type=str, default=None, help="Project language (auto-detected if omitted)")
    scan_parser.add_argument(
        "--changed-only", action="store_true", default=False, help="Only scan files changed since last commit"
    )
    scan_parser.add_argument("--quiet", action="store_true", default=False, help="Minimal output (summary line only)")
    scan_parser.set_defaults(func=cmd_scan)

    args = parser.parse_args()

    if not args.command:
        return cmd_help(args)

    return args.func(args)
