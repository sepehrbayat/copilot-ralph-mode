# 🧭 Ralph Mode — Real‑World Lessons Learned

This document captures practical learnings from a full, end‑to‑end run on a real open‑source project.

---

## Environment & CLI Setup

- **Copilot CLI install may fail due to permissions** when npm tries to write to `/usr/local`. Use a user‑writable prefix:
  - `npm config set prefix "$HOME/.local"`
  - `NPM_CONFIG_PREFIX="$HOME/.local" npm install -g @github/copilot`
- **Prefer the `copilot` command** (not `gh copilot`) for Ralph loops to avoid download prompts.
- **Avoid interactive prompts** in loop terminals; they can block the run and break automation.

---

## Task Design Reliability

- **If a change already exists, tasks must fail** (by design). Create tasks that *must* change a file.
- **Keep scope strict**: only 1–2 files, explicit “ONLY modify” paths, and “DO NOT read” boundaries.
- **Verification commands should be deterministic** and directly prove the required change.

---

## Loop Execution Discipline

- **Run from project root** and keep a **dedicated terminal** for the loop.
- **Ensure `.ralph-mode/` exists** in the target project; missing directories can break loop logging.
- **Use batch mode with a tasks.json** when running grouped tasks.

---

## Contribution Hygiene (PRs)

- **Use neutral branch names** (avoid tool names in branch names if requested by maintainers).
- **Standard PR body sections** improve readability:
  - Summary
  - Changes
  - Notes (and Testing if run)
- **Permissions on public repos vary**: labels/review requests may be denied for forks.

---

## Practical Signals of Success

- **Visible diffs** after each task.
- **Clear, minimal PRs** with focused changes.
- **Owner‑friendly summaries** that highlight reliability/safety fixes and avoid noisy logs.
