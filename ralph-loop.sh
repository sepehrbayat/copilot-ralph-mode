#!/usr/bin/env bash
#
# ralph-loop.sh - The actual Ralph loop runner for GitHub Copilot CLI
#
# This script runs the continuous iteration loop with Copilot CLI.
# It's the "real Ralph" - a bash while loop that keeps running until done.
#
# Fully compatible with GitHub Copilot CLI features:
# - Custom agents
# - Plan mode
# - Context management
# - MCP servers
# - Session resume
# - Network resilience with automatic retry
#
# Author: Sepehr Bayat
# Repository: https://github.com/sepehrbayat/copilot-ralph-mode

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Defaults
RALPH_DIR=".ralph-mode"
STATE_FILE="$RALPH_DIR/state.json"
PROMPT_FILE="$RALPH_DIR/prompt.md"
OUTPUT_FILE="$RALPH_DIR/output.txt"
HISTORY_FILE="$RALPH_DIR/history.jsonl"
SESSION_FILE="$RALPH_DIR/session.json"
CHECKPOINT_FILE="$RALPH_DIR/checkpoint.json"
LOG_FILE="$RALPH_DIR/ralph-loop.log"
SLEEP_BETWEEN=2

# Context snapshot limits
CONTEXT_OUTPUT_LINES=120
CONTEXT_HISTORY_LINES=5
CONTEXT_STATUS_LINES=50
CONTEXT_DIFF_STAT_LINES=50

# Network resilience settings
NETWORK_CHECK_HOSTS=("api.github.com" "github.com" "1.1.1.1")
NETWORK_CHECK_TIMEOUT=5
NETWORK_RETRY_INITIAL=5
NETWORK_RETRY_MAX=300
NETWORK_RETRY_MULTIPLIER=2
MAX_CONSECUTIVE_FAILURES=3

# Default model configuration
DEFAULT_MODEL="gpt-5.2-codex"
FALLBACK_MODEL="auto"

# Default process limits
DEFAULT_NPROC_LIMIT=65535
DEFAULT_NOFILE_LIMIT=1048576

# Permission flags
ALLOW_ALL_TOOLS=true
ALLOW_ALL_PATHS=true
ALLOW_ALL_URLS=false
ALLOWED_URLS=""
DENIED_TOOLS=""
ALLOWED_TOOLS_EXTRA=""

# Hooks directory
HOOKS_DIR=".github/hooks"

# Add copilot to PATH if needed
export PATH="$HOME/.local/bin:$PATH"

# Copilot CLI command
COPILOT_CMD="copilot"
COPILOT_ENV_PREFIX=""
COPILOT_PREFLIGHT_DONE=false
SKIP_CHANGE_CHECK="${RALPH_SKIP_CHANGE_CHECK:-0}"

# Ensure Copilot CLI is available
ensure_copilot_cli() {
    if command -v "$COPILOT_CMD" >/dev/null 2>&1; then
        return 0
    fi

    if command -v gh >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️ Copilot CLI not found. Attempting to install gh-copilot extension...${NC}"
        if gh extension install github/gh-copilot >/dev/null 2>&1 || gh extension upgrade github/gh-copilot >/dev/null 2>&1; then
            if ! command -v "$COPILOT_CMD" >/dev/null 2>&1; then
                echo -e "${YELLOW}⚠️ Creating copilot wrapper to gh copilot...${NC}"
                sudo bash -c 'printf "#!/usr/bin/env bash\nexec gh copilot \"$@\"\n" > /usr/local/bin/copilot'
                sudo chmod +x /usr/local/bin/copilot
            fi
        fi
    fi

    if ! command -v "$COPILOT_CMD" >/dev/null 2>&1; then
        echo -e "${RED}❌ Copilot CLI is required but not found.${NC}"
        echo -e "${YELLOW}Install it with: npm install -g @github/copilot${NC}"
        return 1
    fi
    return 0
}

# Resolve project root to keep .ralph-mode in target repo
resolve_project_root() {
    local root=""
    root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
    if [[ -n "$root" && "$root" != "$PWD" ]]; then
        echo -e "${YELLOW}⚠️ Not at project root. Switching to: $root${NC}"
        cd "$root"
    fi
}

# Configure Copilot environment (avoid GITHUB_TOKEN auth hijack)
setup_copilot_env() {
    if [[ -n "${GITHUB_TOKEN:-}" && "${RALPH_KEEP_GITHUB_TOKEN:-0}" != "1" ]]; then
        echo -e "${YELLOW}⚠️ GITHUB_TOKEN is set. Copilot CLI may fail auth (401).${NC}"
        echo -e "${YELLOW}   Unsetting GITHUB_TOKEN for this run. Set RALPH_KEEP_GITHUB_TOKEN=1 to keep it.${NC}"
        COPILOT_ENV_PREFIX="env -u GITHUB_TOKEN"
    fi
}

# Validate task prompt in strict mode before running
validate_task_prompt() {
    if [[ "${RALPH_SKIP_TASK_VALIDATION:-0}" == "1" ]]; then
        return 0
    fi
    if ! python3 "$SCRIPT_DIR/ralph_mode.py" validate --strict; then
        echo -e "${RED}❌ Task validation failed. Fix prompt template requirements.${NC}"
        return 1
    fi
    return 0
}

# Preflight Copilot auth & model availability
copilot_preflight() {
    if [[ "${RALPH_SKIP_PREFLIGHT:-0}" == "1" ]]; then
        return 0
    fi
    if [[ "$COPILOT_PREFLIGHT_DONE" == "true" ]]; then
        return 0
    fi

    local output=""
    local exit_code=0

    set +e
    output=$(timeout 30 $COPILOT_ENV_PREFIX $COPILOT_CMD -p "ping" --allow-all-tools --allow-all-paths --log-level error 2>&1)
    exit_code=$?
    set -e

    if [[ $exit_code -ne 0 ]]; then
        echo -e "${RED}❌ Copilot preflight failed (exit code: $exit_code).${NC}"
        echo -e "${YELLOW}Output:${NC}\n$output"
        return 1
    fi

    if echo "$output" | grep -qi "failed to list models\|401\|authenticate\|login/device\|no auth info"; then
        echo -e "${RED}❌ Copilot authentication failed.${NC}"
        echo -e "${YELLOW}Run: copilot login${NC}"
        return 1
    fi

    COPILOT_PREFLIGHT_DONE=true
    return 0
}

# Ensure process limits are high enough for Copilot CLI
ensure_process_limits() {
    local nproc_limit="${1:-$DEFAULT_NPROC_LIMIT}"
    local nofile_limit="${2:-$DEFAULT_NOFILE_LIMIT}"
    local current_nproc
    local current_nofile

    current_nproc=$(ulimit -u 2>/dev/null || echo "0")
    current_nofile=$(ulimit -n 2>/dev/null || echo "0")

    if [[ "$current_nproc" != "unlimited" ]] && [[ "$current_nproc" -lt "$nproc_limit" ]]; then
        if ! ulimit -u "$nproc_limit" 2>/dev/null; then
            echo -e "${YELLOW}⚠️ Unable to raise max user processes to $nproc_limit${NC}"
        fi
    fi

    if [[ "$current_nofile" != "unlimited" ]] && [[ "$current_nofile" -lt "$nofile_limit" ]]; then
        if ! ulimit -n "$nofile_limit" 2>/dev/null; then
            echo -e "${YELLOW}⚠️ Unable to raise max open files to $nofile_limit${NC}"
        fi
    fi
}

# Logging helpers
init_logging() {
    mkdir -p "$RALPH_DIR"
    touch "$LOG_FILE"
}

log_line() {
    local level="$1"
    local message="$2"
    local ts
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    printf '%s [%s] %s\n' "$ts" "$level" "$message" >> "$LOG_FILE"
}

log_snapshot() {
    log_line "INFO" "pid=$$"
    log_line "INFO" "cwd=$PWD"
    log_line "INFO" "user=$(id -u):$(id -g)"
    log_line "INFO" "ulimit_nproc=$(ulimit -u 2>/dev/null || echo unknown)"
    log_line "INFO" "ulimit_nofile=$(ulimit -n 2>/dev/null || echo unknown)"
    log_line "INFO" "pids_max=$(cat /sys/fs/cgroup/pids.max 2>/dev/null || echo unknown)"
    log_line "INFO" "pids_current=$(cat /sys/fs/cgroup/pids.current 2>/dev/null || echo unknown)"
}

# Detect whether any meaningful file changes were made (ignores .ralph-mode)
detect_changes() {
    local status
    status=$(git status --short 2>/dev/null | grep -vE '^\?\? \.(ralph-mode|ralph-mode/)' || true)
    if [[ -z "$status" ]]; then
        return 1
    fi
    return 0
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ═══════════════════════════════════════════════════════════════
# Network Resilience Functions
# ═══════════════════════════════════════════════════════════════

# Check if internet is available
check_internet() {
    # Check for mock file first (for testing)
    if [[ -f "$RALPH_DIR/mock_network_down" ]]; then
        return 1
    fi

    local host
    for host in "${NETWORK_CHECK_HOSTS[@]}"; do
        if ping -c 1 -W "$NETWORK_CHECK_TIMEOUT" "$host" &>/dev/null 2>&1; then
            return 0
        fi
        # Fallback to curl if ping doesn't work
        if curl -s --connect-timeout "$NETWORK_CHECK_TIMEOUT" --head "https://$host" &>/dev/null 2>&1; then
            return 0
        fi
    done
    return 1
}

# Wait for internet connection with exponential backoff
wait_for_internet() {
    local wait_time=$NETWORK_RETRY_INITIAL
    local total_waited=0
    local attempt=1

    echo -e "\n${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}🔌 Network connection lost - waiting for reconnection...${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}\n"

    # Save checkpoint before waiting
    save_checkpoint "network_disconnected"

    while ! check_internet; do
        local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        echo -e "${MAGENTA}[$timestamp]${NC} Attempt $attempt: Waiting ${wait_time}s for network... (total: ${total_waited}s)"

        sleep "$wait_time"
        total_waited=$((total_waited + wait_time))
        attempt=$((attempt + 1))

        # Exponential backoff with max limit
        wait_time=$((wait_time * NETWORK_RETRY_MULTIPLIER))
        if [[ $wait_time -gt $NETWORK_RETRY_MAX ]]; then
            wait_time=$NETWORK_RETRY_MAX
        fi

        # Run hook if exists
        run_hook "on-network-wait" 2>/dev/null || true
    done

    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "\n${GREEN}[$timestamp] ✅ Network connection restored after ${total_waited}s!${NC}\n"

    # Small delay to ensure connection is stable
    sleep 2

    # Update checkpoint
    save_checkpoint "network_restored"

    return 0
}

# Save checkpoint for resume capability
save_checkpoint() {
    local status="$1"
    local iteration=$(get_iteration)
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    cat > "$CHECKPOINT_FILE" << EOF
{
    "status": "$status",
    "iteration": $iteration,
    "timestamp": "$timestamp",
    "pid": $$,
    "last_output_lines": $(tail -n 20 "$OUTPUT_FILE" 2>/dev/null | jq -Rs . || echo '""')
}
EOF
}

# Check if we should resume from checkpoint
check_checkpoint() {
    if [[ -f "$CHECKPOINT_FILE" ]]; then
        local status=$(jq -r '.status // empty' "$CHECKPOINT_FILE" 2>/dev/null || echo "")
        local checkpoint_iter=$(jq -r '.iteration // 0' "$CHECKPOINT_FILE" 2>/dev/null || echo "0")
        local current_iter=$(get_iteration)

        if [[ "$status" == "network_disconnected" || "$status" == "iteration_failed" ]]; then
            echo -e "${YELLOW}📌 Found checkpoint at iteration $checkpoint_iter (status: $status)${NC}"
            return 0
        fi
    fi
    return 1
}

# Clear checkpoint
clear_checkpoint() {
    rm -f "$CHECKPOINT_FILE" 2>/dev/null || true
}

# Execute with network resilience
execute_with_resilience() {
    local cmd="$1"
    local max_retries=${2:-3}
    local retry_count=0
    local exit_code=0

    while [[ $retry_count -lt $max_retries ]]; do
        # Check internet before execution
        if ! check_internet; then
            wait_for_internet
        fi

        # Save checkpoint before execution
        save_checkpoint "executing"

        # Execute the command
        set +e
        eval "$cmd"
        exit_code=$?
        set -e

        if [[ $exit_code -eq 0 ]]; then
            clear_checkpoint
            return 0
        fi

        # Check if it's a network error (common exit codes)
        # Exit codes: 6=couldn't resolve host, 7=couldn't connect, 28=timeout
        if [[ $exit_code -eq 6 || $exit_code -eq 7 || $exit_code -eq 28 || $exit_code -eq 56 ]]; then
            echo -e "${YELLOW}⚠️ Network error detected (exit code: $exit_code)${NC}"
            save_checkpoint "network_error"

            if ! check_internet; then
                wait_for_internet
                retry_count=$((retry_count + 1))
                echo -e "${CYAN}🔄 Retrying... (attempt $((retry_count + 1))/$max_retries)${NC}"
                continue
            fi
        fi

        # Non-network error
        save_checkpoint "iteration_failed"
        return $exit_code
    done

    echo -e "${RED}❌ Max retries ($max_retries) exceeded${NC}"
    return 1
}

# ═══════════════════════════════════════════════════════════════
# End Network Resilience Functions
# ═══════════════════════════════════════════════════════════════

# Run a hook if it exists
run_hook() {
    local hook_name="$1"
    local hook_file="$HOOKS_DIR/$hook_name.sh"

    if [[ -f "$hook_file" && -x "$hook_file" ]]; then
        echo -e "${BLUE}🪝 Running hook: $hook_name${NC}"
        "$hook_file" || true
    fi
}

# Help message
show_help() {
    cat << EOF
${GREEN}🔄 Ralph Loop Runner${NC}

Runs the actual Ralph loop with GitHub Copilot CLI.
Fully compatible with Copilot CLI features.

${YELLOW}USAGE:${NC}
    ralph-loop.sh run [options]          # Start the loop
    ralph-loop.sh single [options]       # Run single iteration
    ralph-loop.sh resume [options]       # Resume previous session
    ralph-loop.sh verify                 # Run verification commands only
    ralph-loop.sh check-network          # Check network connectivity
    ralph-loop.sh help                   # Show this help

${YELLOW}OPTIONS:${NC}
    --sleep <seconds>       Sleep between iterations (default: 2)
    --agent <name>          Use a custom agent (ralph, plan, task, etc.)
    --model <model>         Override the model
    --allow-all             Enable all permissions (--yolo mode)
    --allow-url <domain>    Pre-approve specific URL domain
    --allow-tool <tool>     Allow specific tool (e.g., 'shell(git)')
    --deny-tool <tool>      Deny specific tool (takes precedence)
    --no-allow-tools        Don't auto-allow all tools
    --no-allow-paths        Don't auto-allow all paths
    --no-network-check      Disable network resilience (not recommended)
    --network-retry <sec>   Initial retry wait time (default: 5)
    --network-max <sec>     Max retry wait time (default: 300)
    --dry-run               Print commands without executing
    --verbose               Verbose output

${YELLOW}NETWORK RESILIENCE:${NC}
    Ralph automatically handles network interruptions:
    - Detects connection loss during execution
    - Waits with exponential backoff until reconnected
    - Resumes from the exact point of interruption
    - Saves checkpoints for recovery

    Hooks for network events:
    - on-network-wait.sh    Called during network wait

${YELLOW}TOOL APPROVAL SYNTAX:${NC}
    --allow-tool 'shell(COMMAND)'       Allow shell command
    --allow-tool 'shell(git push)'      Allow specific git subcommand
    --allow-tool 'shell'                Allow all shell commands
    --allow-tool 'write'                Allow file modifications
    --allow-tool 'MCP_SERVER_NAME'      Allow all tools from MCP server
    --deny-tool 'shell(rm)'             Deny rm command

${YELLOW}COPILOT CLI INTEGRATION:${NC}
    Slash commands available during interactive mode:
    /context    - View current token usage
    /compact    - Compress conversation history
    /usage      - View session statistics
    /review     - Review code changes
    /agent      - Select a custom agent
    /model      - Change the model
    /cwd        - Change working directory
    /resume     - Resume a previous session
    /mcp add    - Add an MCP server

${YELLOW}HOOKS:${NC}
    Custom hooks in .github/hooks/:
    - pre-iteration.sh    Run before each iteration
    - post-iteration.sh   Run after each iteration
    - pre-tool.sh         Run before tool execution
    - on-completion.sh    Run when task completes
    - on-network-wait.sh  Run during network wait

${YELLOW}EXAMPLES:${NC}
    # First, enable Ralph mode
    python3 ralph_mode.py enable "Fix all linting errors" --max-iterations 10 --completion-promise "DONE"

    # Then run the loop
    ./ralph-loop.sh run

    # Use a specific agent
    ./ralph-loop.sh run --agent ralph

    # Allow git but deny rm
    ./ralph-loop.sh run --allow-tool 'shell(git)' --deny-tool 'shell(rm)'

    # Run single iteration manually
    ./ralph-loop.sh single

    # Resume previous session
    ./ralph-loop.sh resume

    # Check network connectivity
    ./ralph-loop.sh check-network

    # Verify-only
    ./ralph-loop.sh verify

${YELLOW}CUSTOM AGENTS:${NC}
    Available in .github/agents/:
    - ralph       Main Ralph Mode iteration agent
    - plan        Create implementation plans
    - code-review Review changes
    - task        Run tests and builds
    - explore     Quick codebase exploration

${YELLOW}REQUIREMENTS:${NC}
    - GitHub Copilot CLI (https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli)
    - Ralph mode enabled (python3 ralph_mode.py enable ...)

EOF
}

# Check if Ralph mode is active
check_active() {
    if [[ ! -f "$STATE_FILE" ]]; then
        echo -e "${RED}❌ Ralph mode is not active${NC}"
        echo "Enable it first: python3 ralph_mode.py enable \"Your task\" --max-iterations 20"
        exit 1
    fi
}

# Get state value
get_state() {
    local key="$1"
    jq -r ".$key // empty" "$STATE_FILE" 2>/dev/null || echo ""
}

# Get current iteration
get_iteration() {
    get_state "iteration"
}

# Get max iterations
get_max_iterations() {
    get_state "max_iterations"
}

# Get completion promise
get_promise() {
    get_state "completion_promise"
}
# Get model from state
get_model() {
    local model=$(get_state "model")
    echo "${model:-$DEFAULT_MODEL}"
}

# Get fallback model from state
get_fallback_model() {
    local fallback=$(get_state "fallback_model")
    echo "${fallback:-$FALLBACK_MODEL}"
}

# Build copilot CLI options based on flags
build_copilot_opts() {
    local opts=""

    # Permission flags
    if [[ "$ALLOW_ALL_TOOLS" == "true" ]]; then
        opts="$opts --allow-all-tools"
    fi

    if [[ "$ALLOW_ALL_PATHS" == "true" ]]; then
        opts="$opts --allow-all-paths"
    fi

    if [[ "$ALLOW_ALL_URLS" == "true" ]]; then
        opts="$opts --allow-all-urls"
    fi

    # Pre-approved URLs
    if [[ -n "$ALLOWED_URLS" ]]; then
        for url in $ALLOWED_URLS; do
            opts="$opts --allow-url $url"
        done
    fi

    # Denied tools (--deny-tool takes precedence)
    if [[ -n "$DENIED_TOOLS" ]]; then
        for tool in $DENIED_TOOLS; do
            # Do not embed extra quotes; this value is already a single shell token.
            opts="$opts --deny-tool $tool"
        done
    fi

    # Additional allowed tools
    if [[ -n "$ALLOWED_TOOLS_EXTRA" ]]; then
        for tool in $ALLOWED_TOOLS_EXTRA; do
            # Do not embed extra quotes; this value is already a single shell token.
            opts="$opts --allow-tool $tool"
        done
    fi

    echo "$opts"
}

# Check whether an output file contains the completion promise.
# Uses the same parsing semantics as the Python implementation (strip + compare)
# but does NOT mutate state.
output_has_promise() {
    local promise="$1"
    local output_file="$2"

    if [[ -z "$promise" || ! -f "$output_file" ]]; then
        return 1
    fi

    PROMISE="$promise" OUTPUT_FILE="$output_file" python3 <<'PY'
import re
import sys
import os

promise = os.environ.get('PROMISE', '').strip()
output_file = os.environ.get('OUTPUT_FILE', '')

if not promise or not output_file:
    sys.exit(1)

try:
    with open(output_file, 'r') as f:
        text = f.read()
except Exception:
    sys.exit(1)

matches = re.findall(r"<promise>(.*?)</promise>", text, re.DOTALL)
sys.exit(0 if any(m.strip() == promise for m in matches) else 1)
PY
}

# Get prompt
get_prompt() {
    cat "$PROMPT_FILE" 2>/dev/null || echo ""
}

# Check if auto_agents is enabled
is_auto_agents_enabled() {
    local auto_agents=$(get_state "auto_agents")
    [[ "$auto_agents" == "true" ]]
}

# Build the full context for gh copilot
# ═══════════════════════════════════════════════════════════════
# Advanced Context System
# ═══════════════════════════════════════════════════════════════

# Build the full context for Copilot CLI using ContextManager (Python).
# Falls back to a minimal shell-native context on failure.
build_context() {
    local context=""

    # Try the advanced Python-based context builder first
    if context=$(python3 "$SCRIPT_DIR/ralph_mode.py" context show 2>/dev/null) && [[ -n "$context" ]]; then
        echo "$context"
        return 0
    fi

    # Fallback: minimal shell-native context
    log_line "WARN" "Python context builder failed, using shell fallback"
    _build_context_fallback
}

# Save iteration context to file for reference / debugging
write_context_file() {
    python3 "$SCRIPT_DIR/ralph_mode.py" context build 2>/dev/null || true
}

# Record what happened in this iteration (called after copilot finishes)
save_iteration_memory() {
    local iteration="$1"
    local notes="${2:-}"
    python3 "$SCRIPT_DIR/ralph_mode.py" context save-summary "$notes" 2>/dev/null || true
}

# Extract memories from iteration output using mem0-inspired memory bank
extract_iteration_memories() {
    local iteration="$1"
    python3 "$SCRIPT_DIR/ralph_mode.py" memory extract 2>/dev/null || true
}

# Minimal fallback context (no Python dependency)
_build_context_fallback() {
    local iteration=$(get_iteration)
    local max_iter=$(get_max_iterations)
    local promise=$(get_promise)
    local prompt=$(get_prompt)
    local mode=$(get_state "mode")

    local context="# Ralph Mode — Iteration $iteration"
    [[ "$max_iter" -gt 0 ]] && context="$context / $max_iter"
    context="$context

## Task
$prompt

## Rules
1. **Continue from where you left off** — do NOT restart.
2. Make real file changes visible in \`git diff\`.
3. Focus ONLY on files listed in the task scope.
4. If already satisfied, verify and complete — don't redo.

## Repository State
\`\`\`
$(git status --short 2>/dev/null | head -40 || echo '<clean>')
\`\`\`

## Recent Commits
\`\`\`
$(git log --oneline -5 2>/dev/null || echo '<none>')
\`\`\`
"

    if [[ -f "$OUTPUT_FILE" ]]; then
        context="$context
## Last Output (tail)
\`\`\`
$(tail -n 80 "$OUTPUT_FILE" 2>/dev/null || echo '<none>')
\`\`\`
"
    fi

    if [[ -n "$promise" ]]; then
        context="$context
## Completion
When ALL acceptance criteria are met, output exactly:
\`\`\`
<promise>$promise</promise>
\`\`\`
⚠️ ONLY when genuinely complete. Never lie.
"
    fi

    if [[ "$mode" == "batch" ]]; then
        local task_num=$(get_state "current_task_index")
        local task_total=$(get_state "tasks_total")
        local task_id=$(get_state "current_task_id")
        task_num=$((task_num + 1))
        context="$context
## Batch Mode
Task $task_num of $task_total: $task_id
"
    fi

    if is_auto_agents_enabled; then
        context="$context
## Auto-Agents (enabled)
Create sub-agents in \`.github/agents/\` and invoke with \`@agent-name <task>\`.
"
    fi

    echo "$context"
}

# ═══════════════════════════════════════════════════════════════
# End Advanced Context System
# ═══════════════════════════════════════════════════════════════

# Run single iteration with Copilot CLI
run_single() {
    local dry_run="${1:-false}"
    local verbose="${2:-false}"
    local agent="${3:-}"
    local network_check="${4:-true}"

    resolve_project_root
    check_active
    init_logging
    ensure_process_limits
    setup_copilot_env
    validate_task_prompt
    copilot_preflight

    local iteration=$(get_iteration)
    local max_iter=$(get_max_iterations)
    local promise=$(get_promise)
    local model=$(get_model)
    local fallback=$(get_fallback_model)
    local copilot_opts=$(build_copilot_opts)
    local mode=$(get_state "mode")
    local task_id=$(get_state "current_task_id")

    # Export environment variables for hooks
    export RALPH_ITERATION="$iteration"
    export RALPH_MAX_ITERATIONS="$max_iter"
    export RALPH_TASK_ID="$task_id"
    export RALPH_MODE="$mode"

    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║          🔄 Ralph Iteration $iteration                              ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo -e "${CYAN}Model: $model (fallback: $fallback)${NC}"
    log_line "INFO" "iteration=$iteration model=$model fallback=$fallback"
    if [[ -n "$agent" ]]; then
        echo -e "${CYAN}Agent: $agent${NC}"
    fi

    # Network check before starting
    if [[ "$network_check" == "true" ]]; then
        if ! check_internet; then
            echo -e "${YELLOW}⚠️ Network check: No connection detected${NC}"
            wait_for_internet
        fi
    fi

    # Run pre-iteration hook
    run_hook "pre-iteration"

    # ── Memory Bank: clear working memory for fresh iteration ──
    python3 "$SCRIPT_DIR/ralph_mode.py" memory clear-working 2>/dev/null || true

    # Build context/prompt
    local context=$(build_context)

    if [[ "$verbose" == "true" ]]; then
        echo -e "${YELLOW}📝 Context:${NC}"
        echo "$context"
        echo ""
    fi

    # Build model options
    local model_opts=""
    if [[ "$model" != "auto" && -n "$model" ]]; then
        model_opts="--model $model"
    fi

    # Build agent options
    local agent_opts=""
    if [[ -n "$agent" ]]; then
        agent_opts="--agent=$agent"
    fi

    # Run Copilot CLI
    echo -e "${BLUE}🤖 Running GitHub Copilot CLI...${NC}"
    log_line "INFO" "copilot_cmd=$COPILOT_CMD"

    local cmd="$COPILOT_ENV_PREFIX $COPILOT_CMD -p \"$context\" $copilot_opts $model_opts $agent_opts"

    if [[ "$dry_run" == "true" ]]; then
        echo -e "${YELLOW}[DRY RUN] Would execute:${NC}"
        echo "$cmd"
        log_line "INFO" "dry_run_cmd=$cmd"
        return 0
    fi

    # Execute and capture output
    mkdir -p "$RALPH_DIR"

    # Save checkpoint before execution
    save_checkpoint "iteration_started"
    log_snapshot

    # Try with primary model, fallback if needed
    local exit_code=0
    local max_network_retries=3
    local network_retry_count=0
    local promise_detected=false

    while [[ $network_retry_count -lt $max_network_retries ]]; do
        if timeout 600 $COPILOT_ENV_PREFIX $COPILOT_CMD -p "$context" $copilot_opts $model_opts $agent_opts 2>&1 | tee "$OUTPUT_FILE"; then
            echo ""
            exit_code=0
            break
        else
            exit_code=$?

            # Check if it's a network error
            if [[ $exit_code -eq 6 || $exit_code -eq 7 || $exit_code -eq 28 || $exit_code -eq 56 ]] || \
               grep -qi "network\|connection\|timeout\|unreachable\|resolve" "$OUTPUT_FILE" 2>/dev/null; then
                echo -e "${YELLOW}⚠️ Network error detected (exit code: $exit_code)${NC}"

                if [[ "$network_check" == "true" ]]; then
                    save_checkpoint "network_error"
                    wait_for_internet
                    network_retry_count=$((network_retry_count + 1))
                    echo -e "${CYAN}🔄 Retrying iteration... (attempt $((network_retry_count + 1))/$max_network_retries)${NC}"
                    continue
                fi
            fi

            # Check if model not available error
            if grep -q "model.*not available\|invalid model\|Model.*not found" "$OUTPUT_FILE" 2>/dev/null; then
                echo -e "${YELLOW}⚠️ Model '$model' not available, trying fallback '$fallback'...${NC}"
                if [[ "$fallback" == "auto" ]]; then
                    model_opts=""
                else
                    model_opts="--model $fallback"
                fi
                if timeout 600 $COPILOT_ENV_PREFIX $COPILOT_CMD -p "$context" $copilot_opts $model_opts $agent_opts 2>&1 | tee "$OUTPUT_FILE"; then
                    echo ""
                    exit_code=0
                fi
            else
                echo -e "${YELLOW}⚠️ Copilot CLI exited with non-zero status${NC}"
            fi
            break
        fi
    done

    if [[ -f "$OUTPUT_FILE" ]]; then
        printf '\n----- OUTPUT (iteration %s) -----\n' "$iteration" >> "$LOG_FILE"
        cat "$OUTPUT_FILE" >> "$LOG_FILE" || true
        printf '\n----- END OUTPUT (iteration %s) -----\n' "$iteration" >> "$LOG_FILE"
    fi

    # Detect completion promise early (robust to whitespace/newlines).
    log_line "DEBUG" "promise='$promise' OUTPUT_FILE='$OUTPUT_FILE'"
    if output_has_promise "$promise" "$OUTPUT_FILE"; then
        log_line "INFO" "promise_detected=true promise='$promise'"
        promise_detected=true
    else
        log_line "DEBUG" "promise_not_detected promise='$promise'"
    fi

    # If Copilot signaled completion, prefer that over the change-check heuristic.
    # (Some tasks may legitimately be satisfied with no net new changes.)
    if [[ "$SKIP_CHANGE_CHECK" != "1" && $exit_code -eq 0 && "$promise_detected" != "true" ]]; then
        if ! detect_changes; then
            echo -e "${YELLOW}⚠️ No file changes detected. Marking iteration as failed.${NC}"
            log_line "WARN" "no_changes_detected=true"
            exit_code=2
        fi
    fi
    log_line "INFO" "exit_code=$exit_code"

    # Write summary report
    python3 "$SCRIPT_DIR/ralph_mode.py" context report --exit-code "$exit_code" 2>/dev/null || true

    # Clear checkpoint on success
    if [[ $exit_code -eq 0 ]]; then
        clear_checkpoint
    else
        save_checkpoint "iteration_failed"
    fi

    # Export exit code for post-iteration hook
    export RALPH_EXIT_CODE="$exit_code"

    # ── Advanced Contexting: save iteration memory ──
    echo -e "${BLUE}📝 Saving iteration memory...${NC}"
    save_iteration_memory "$iteration" "exit_code=$exit_code"

    # ── Memory Bank: extract memories from iteration output ──
    echo -e "${BLUE}🧠 Extracting memories from iteration output...${NC}"
    extract_iteration_memories "$iteration"

    # ── Memory Bank: extract semantic facts from output ──
    echo -e "${BLUE}🔍 Extracting semantic facts...${NC}"
    python3 "$SCRIPT_DIR/ralph_mode.py" memory extract-facts 2>/dev/null || true

    # ── Memory Bank: decay old memory scores ──
    python3 "$SCRIPT_DIR/ralph_mode.py" memory decay 2>/dev/null || true

    # ── Memory Bank: promote frequently-accessed episodic → semantic ──
    python3 "$SCRIPT_DIR/ralph_mode.py" memory promote 2>/dev/null || true

    # Run post-iteration hook
    run_hook "post-iteration"

    # ── Advanced Contexting: pre-build context for next iteration ──
    write_context_file

    # Save session info for resume capability
    echo "{\"last_iteration\": $iteration, \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > "$SESSION_FILE"

    # Check for completion promise in output
    log_line "DEBUG" "checking_complete promise='$promise' promise_detected='$promise_detected'"
    if [[ -n "$promise" && "$promise_detected" == "true" ]]; then
        log_line "INFO" "promise_complete_block_entered=true"
        echo ""
        echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}✅ COMPLETION PROMISE DETECTED!${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"

        # Export for completion hook
        export RALPH_PROMISE="$promise"

        # Run completion hook
        run_hook "on-completion"

        # Complete the task
        # Avoid argv length limits and preserve output as-is.
        python3 "$SCRIPT_DIR/ralph_mode.py" complete < "$OUTPUT_FILE" || true
        return 0
    fi

    # Increment iteration
    python3 "$SCRIPT_DIR/ralph_mode.py" iterate || {
        echo -e "${YELLOW}⚠️ Max iterations reached or error${NC}"
        return 1
    }

    return 0
}

# Run verification-only (no Copilot execution)
run_verification() {
    resolve_project_root
    check_active
    init_logging
    ensure_process_limits
    validate_task_prompt

    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║          ✅ Verification Only                            ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"

    if python3 "$SCRIPT_DIR/ralph_mode.py" verify run; then
        echo -e "${GREEN}✅ Verification passed${NC}"
        return 0
    fi

    echo -e "${RED}❌ Verification failed${NC}"
    return 1
}

# Run the continuous loop
run_loop() {
    local dry_run="${1:-false}"
    local verbose="${2:-false}"
    local sleep_time="${3:-$SLEEP_BETWEEN}"
    local agent="${4:-}"
    local network_check="${5:-true}"

    resolve_project_root
    check_active
    init_logging
    log_line "INFO" "loop_start"
    log_snapshot
    trap 'log_line "ERROR" "loop_exit code=$?"' EXIT
    ensure_process_limits

    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              🔄 RALPH LOOP STARTING                      ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}Press Ctrl+C to stop the loop${NC}"
    echo -e "${CYAN}Copilot CLI features available: /context, /compact, /usage, /review${NC}"
    if [[ "$network_check" == "true" ]]; then
        echo -e "${CYAN}Network resilience: ENABLED (auto-retry on connection loss)${NC}"
    fi
    echo ""

    # Check for checkpoint from previous interrupted session
    if check_checkpoint; then
        echo -e "${YELLOW}📌 Resuming from checkpoint...${NC}"
    fi

    # Initial network check
    if [[ "$network_check" == "true" ]]; then
        echo -e "${BLUE}🌐 Checking network connectivity...${NC}"
        if check_internet; then
            echo -e "${GREEN}✅ Network connection verified${NC}"
        else
            echo -e "${YELLOW}⚠️ No network connection${NC}"
            wait_for_internet
        fi
        echo ""
    fi

    local iteration=1
    local max_iter=$(get_max_iterations)
    local consecutive_failures=0

    while true; do
        # Check if still active
        if [[ ! -f "$STATE_FILE" ]]; then
            echo -e "${GREEN}✅ Ralph mode completed or disabled${NC}"
            clear_checkpoint
            break
        fi

        iteration=$(get_iteration)

        # Check max iterations
        if [[ "$max_iter" -gt 0 ]] && [[ "$iteration" -gt "$max_iter" ]]; then
            echo -e "${YELLOW}⚠️ Max iterations ($max_iter) reached${NC}"
            clear_checkpoint
            break
        fi

        # Run single iteration with network check
        if run_single "$dry_run" "$verbose" "$agent" "$network_check"; then
            consecutive_failures=0
            clear_checkpoint
        else
            consecutive_failures=$((consecutive_failures + 1))
            echo -e "${YELLOW}⚠️ Iteration failed (consecutive failures: $consecutive_failures/$MAX_CONSECUTIVE_FAILURES)${NC}"

            if [[ $consecutive_failures -ge $MAX_CONSECUTIVE_FAILURES ]]; then
                echo -e "${RED}❌ Too many consecutive failures. Stopping loop.${NC}"
                echo -e "${CYAN}💡 You can resume later with: ./ralph-loop.sh resume${NC}"
                save_checkpoint "max_failures_reached"
                break
            fi

            # Check network before retrying
            if [[ "$network_check" == "true" ]] && ! check_internet; then
                wait_for_internet
            fi
        fi

        # Sleep between iterations
        if [[ -f "$STATE_FILE" ]]; then
            echo -e "${BLUE}💤 Sleeping $sleep_time seconds before next iteration...${NC}"
            sleep "$sleep_time"
        fi
    done

    echo ""
    echo -e "${GREEN}🏁 Ralph loop finished${NC}"
}

# Resume previous session
run_resume() {
    local verbose="${1:-false}"
    local network_check="${2:-true}"

    resolve_project_root

    # First check for checkpoint
    if [[ -f "$CHECKPOINT_FILE" ]]; then
        echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║       🔄 RESUMING FROM CHECKPOINT                        ║${NC}"
        echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
        echo ""

        local checkpoint_status=$(jq -r '.status // "unknown"' "$CHECKPOINT_FILE" 2>/dev/null || echo "unknown")
        local checkpoint_iter=$(jq -r '.iteration // 0' "$CHECKPOINT_FILE" 2>/dev/null || echo "0")
        local checkpoint_time=$(jq -r '.timestamp // "unknown"' "$CHECKPOINT_FILE" 2>/dev/null || echo "unknown")

        echo -e "${CYAN}Checkpoint status: $checkpoint_status${NC}"
        echo -e "${CYAN}Iteration: $checkpoint_iter${NC}"
        echo -e "${CYAN}Timestamp: $checkpoint_time${NC}"
        echo ""

        # If it was a network error, wait for network first
        if [[ "$checkpoint_status" == "network_disconnected" || "$checkpoint_status" == "network_error" ]]; then
            if [[ "$network_check" == "true" ]] && ! check_internet; then
                wait_for_internet
            fi
        fi

        # Continue the loop
        run_loop "false" "$verbose" "$SLEEP_BETWEEN" "" "$network_check"
        return $?
    fi

    if [[ ! -f "$SESSION_FILE" ]]; then
        echo -e "${YELLOW}⚠️ No previous session found to resume${NC}"
        echo "Start a new session with: ./ralph-loop.sh run"
        return 1
    fi

    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           🔄 RESUMING RALPH SESSION                      ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    local last_iteration=$(jq -r '.last_iteration // 0' "$SESSION_FILE" 2>/dev/null || echo "0")
    local last_timestamp=$(jq -r '.timestamp // "unknown"' "$SESSION_FILE" 2>/dev/null || echo "unknown")

    echo -e "${CYAN}Last iteration: $last_iteration${NC}"
    echo -e "${CYAN}Last active: $last_timestamp${NC}"
    echo ""

    # Continue the loop
    run_loop "false" "$verbose" "$SLEEP_BETWEEN" "" "$network_check"
}

# Check network command
check_network_cmd() {
    echo -e "${BLUE}🌐 Checking network connectivity...${NC}"
    echo ""

    for host in "${NETWORK_CHECK_HOSTS[@]}"; do
        echo -n "  Testing $host... "
        if ping -c 1 -W "$NETWORK_CHECK_TIMEOUT" "$host" &>/dev/null 2>&1; then
            echo -e "${GREEN}✅ OK (ping)${NC}"
        elif curl -s --connect-timeout "$NETWORK_CHECK_TIMEOUT" --head "https://$host" &>/dev/null 2>&1; then
            echo -e "${GREEN}✅ OK (https)${NC}"
        else
            echo -e "${RED}❌ FAILED${NC}"
        fi
    done

    echo ""
    if check_internet; then
        echo -e "${GREEN}✅ Network is available${NC}"
        return 0
    else
        echo -e "${RED}❌ Network is NOT available${NC}"
        return 1
    fi
}

# Parse arguments
main() {
    local cmd="${1:-help}"
    shift || true

    local dry_run=false
    local verbose=false
    local sleep_time=$SLEEP_BETWEEN
    local agent=""
    local model_override=""
    local network_check=true

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                dry_run=true
                shift
                ;;
            --verbose|-v)
                verbose=true
                shift
                ;;
            --sleep)
                sleep_time="$2"
                shift 2
                ;;
            --agent)
                agent="$2"
                shift 2
                ;;
            --model)
                model_override="$2"
                shift 2
                ;;
            --allow-all|--yolo)
                ALLOW_ALL_TOOLS=true
                ALLOW_ALL_PATHS=true
                ALLOW_ALL_URLS=true
                shift
                ;;
            --allow-url)
                ALLOWED_URLS="$ALLOWED_URLS $2"
                shift 2
                ;;
            --allow-tool)
                ALLOWED_TOOLS_EXTRA="$ALLOWED_TOOLS_EXTRA $2"
                shift 2
                ;;
            --deny-tool)
                DENIED_TOOLS="$DENIED_TOOLS $2"
                shift 2
                ;;
            --no-allow-tools)
                ALLOW_ALL_TOOLS=false
                shift
                ;;
            --no-allow-paths)
                ALLOW_ALL_PATHS=false
                shift
                ;;
            --no-network-check)
                network_check=false
                shift
                ;;
            --network-retry)
                NETWORK_RETRY_INITIAL="$2"
                shift 2
                ;;
            --network-max)
                NETWORK_RETRY_MAX="$2"
                shift 2
                ;;
            --copilot-opts)
                # Legacy support - parse into new flags
                echo -e "${YELLOW}⚠️ --copilot-opts is deprecated, use individual flags instead${NC}"
                shift 2
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                exit 1
                ;;
        esac
    done

    case "$cmd" in
        run|loop)
            ensure_copilot_cli || exit 1
            run_loop "$dry_run" "$verbose" "$sleep_time" "$agent" "$network_check"
            ;;
        single|once)
            ensure_copilot_cli || exit 1
            run_single "$dry_run" "$verbose" "$agent" "$network_check"
            ;;
        verify)
            run_verification
            ;;
        resume|continue)
            run_resume "$verbose" "$network_check"
            ;;
        check-network|network)
            check_network_cmd
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo -e "${RED}Unknown command: $cmd${NC}"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
