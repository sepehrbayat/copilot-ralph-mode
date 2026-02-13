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
DEFAULT_MODEL="claude-sonnet-4.5"
FALLBACK_MODEL="auto"

# Minimum iterations before accepting completion promise
MIN_ITERATIONS="${RALPH_MIN_ITERATIONS:-2}"

# Maximum total wait time for network (seconds). 0=unlimited.
# Prevents Ralph from waiting forever when network is down.
MAX_NETWORK_WAIT_TOTAL="${RALPH_MAX_NETWORK_WAIT:-1800}"  # 30 minutes default

# Auto-commit after each task completion (prevents data loss)
AUTO_COMMIT_ON_TASK="${RALPH_AUTO_COMMIT:-true}"

# Compilation check command (language-specific, auto-detected or override)
# Set to empty string to disable compilation gate
COMPILE_CHECK_CMD="${RALPH_COMPILE_CHECK_CMD:-}"

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

# Add copilot and Flutter/Dart to PATH if needed
export PATH="/opt/flutter/bin:$HOME/.local/bin:$PATH"

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
# Respects MAX_NETWORK_WAIT_TOTAL to prevent infinite waits
wait_for_internet() {
    local wait_time=$NETWORK_RETRY_INITIAL
    local total_waited=0
    local attempt=1
    local max_wait=${MAX_NETWORK_WAIT_TOTAL:-0}

    echo -e "\n${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}🔌 Network connection lost - waiting for reconnection...${NC}"
    if [[ "$max_wait" -gt 0 ]]; then
        echo -e "${YELLOW}   Max wait: ${max_wait}s ($(( max_wait / 60 )) minutes)${NC}"
    fi
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}\n"

    # Save checkpoint before waiting
    save_checkpoint "network_disconnected"

    while ! check_internet; do
        # ── Timeout guard: don't wait forever ──
        if [[ "$max_wait" -gt 0 && "$total_waited" -ge "$max_wait" ]]; then
            echo -e "\n${RED}❌ Network wait timeout exceeded (${total_waited}s >= ${max_wait}s)${NC}"
            echo -e "${RED}   Skipping current task and moving to next...${NC}"
            log_line "WARN" "network_wait_timeout total_waited=${total_waited}s max=${max_wait}s"
            save_checkpoint "network_timeout"
            return 1  # Signal timeout to caller
        fi

        local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        local remaining=""
        if [[ "$max_wait" -gt 0 ]]; then
            remaining=" | timeout in $(( max_wait - total_waited ))s"
        fi
        echo -e "${MAGENTA}[$timestamp]${NC} Attempt $attempt: Waiting ${wait_time}s for network... (total: ${total_waited}s${remaining})"

        sleep "$wait_time"
        total_waited=$((total_waited + wait_time))
        attempt=$((attempt + 1))

        # Exponential backoff with max limit
        wait_time=$((wait_time * NETWORK_RETRY_MULTIPLIER))
        if [[ $wait_time -gt $NETWORK_RETRY_MAX ]]; then
            wait_time=$NETWORK_RETRY_MAX
        fi

        # Cap wait_time so we don't overshoot the total max
        if [[ "$max_wait" -gt 0 ]]; then
            local remaining_time=$(( max_wait - total_waited ))
            if [[ "$wait_time" -gt "$remaining_time" && "$remaining_time" -gt 0 ]]; then
                wait_time=$remaining_time
            fi
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

    # ── MCP Server Configuration ──
    # Load MCP servers from config file if present
    local mcp_config=".ralph-mode-config/mcp-config.json"
    if [[ -f "$mcp_config" ]]; then
        local mcp_servers
        mcp_servers=$(jq -r '.mcpServers | keys[]' "$mcp_config" 2>/dev/null || true)
        if [[ -n "$mcp_servers" ]]; then
            opts="$opts --mcp-config $mcp_config"
        fi
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

# ═══════════════════════════════════════════════════════════════
# Multi-Agent Verification (Doer → Compile Gate → Critic → Arbiter)
# ═══════════════════════════════════════════════════════════════

# ── Auto-detect compilation/analysis command for the project ──
# Returns the command to check for compile errors, or empty if none found.
detect_compile_check_cmd() {
    # If user explicitly set it, use that
    if [[ -n "$COMPILE_CHECK_CMD" ]]; then
        echo "$COMPILE_CHECK_CMD"
        return 0
    fi

    # Auto-detect based on project files
    if [[ -f "pubspec.yaml" ]]; then
        # Flutter/Dart project
        local flutter_bin=$(command -v flutter 2>/dev/null || echo "")
        if [[ -z "$flutter_bin" && -x "/opt/flutter/bin/flutter" ]]; then
            flutter_bin="/opt/flutter/bin/flutter"
        fi
        if [[ -n "$flutter_bin" ]]; then
            local dart_bin="${flutter_bin%flutter}dart"
            if [[ -x "$dart_bin" ]]; then
                echo "$dart_bin analyze lib/"
                return 0
            fi
        fi
        local dart_bin=$(command -v dart 2>/dev/null || echo "")
        if [[ -n "$dart_bin" ]]; then
            echo "$dart_bin analyze lib/"
            return 0
        fi
    elif [[ -f "tsconfig.json" ]]; then
        # TypeScript project
        if command -v npx &>/dev/null; then
            echo "npx tsc --noEmit"
            return 0
        fi
    elif [[ -f "Cargo.toml" ]]; then
        # Rust project
        if command -v cargo &>/dev/null; then
            echo "cargo check 2>&1"
            return 0
        fi
    elif [[ -f "go.mod" ]]; then
        # Go project
        if command -v go &>/dev/null; then
            echo "go build ./... 2>&1"
            return 0
        fi
    elif [[ -f "setup.py" || -f "pyproject.toml" ]]; then
        # Python project — use flake8 or pyflakes if available
        if command -v flake8 &>/dev/null; then
            echo "flake8 --select=E9,F63,F7,F82 --show-source --statistics ."
            return 0
        fi
    fi

    echo ""
    return 1
}

# ── Quality Gate 0: Compilation/Static Analysis Check ──
# Runs language-specific compilation check BEFORE calling the critic.
# Returns 0 if clean (or no checker found), 1 if errors detected.
run_compilation_gate() {
    local compile_cmd
    compile_cmd=$(detect_compile_check_cmd)

    if [[ -z "$compile_cmd" ]]; then
        log_line "DEBUG" "compilation_gate_skip reason=no_checker_found"
        return 0  # No checker — pass through
    fi

    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     🔨 QUALITY GATE 0: Compilation Check                 ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    log_line "INFO" "compilation_gate_start cmd='$compile_cmd'"

    local compile_output_file="${RALPH_DIR}/compile-output.txt"

    # Run the compile check with a timeout
    if eval "timeout 120 $compile_cmd" > "$compile_output_file" 2>&1; then
        echo -e "${GREEN}✅ Compilation check passed — no errors${NC}"
        log_line "INFO" "compilation_gate_pass"
        rm -f "$compile_output_file"
        return 0
    else
        local exit_code=$?

        # Count errors (language-specific parsing)
        local error_count=0
        if grep -qE "error -|error\[" "$compile_output_file" 2>/dev/null; then
            # Dart / Rust style
            error_count=$(grep -cE "error -|error\[" "$compile_output_file" 2>/dev/null || true)
        elif grep -qE "^error TS|error:" "$compile_output_file" 2>/dev/null; then
            # TypeScript / generic
            error_count=$(grep -cE "^error TS|error:" "$compile_output_file" 2>/dev/null || true)
        elif grep -qE "^E[0-9]|^F[0-9]|SyntaxError" "$compile_output_file" 2>/dev/null; then
            # Python
            error_count=$(grep -cE "^E[0-9]|^F[0-9]|SyntaxError" "$compile_output_file" 2>/dev/null || true)
        else
            # Fallback: count lines that look like actual errors (not info/warnings)
            error_count=$(grep -ciE "^error|: error" "$compile_output_file" 2>/dev/null || true)
        fi

        # If no actual errors found despite non-zero exit, treat as pass
        # (e.g., dart analyze returns non-zero for info-level issues too)
        if [[ "$error_count" -eq 0 ]]; then
            echo -e "${GREEN}✅ Compilation check passed — no errors (info/warnings only)${NC}"
            log_line "INFO" "compilation_gate_pass_info_only"
            rm -f "$compile_output_file"
            return 0
        fi

        echo -e "${RED}❌ Compilation gate FAILED — $error_count error(s) detected${NC}"
        log_line "INFO" "compilation_gate_fail error_count=$error_count"

        # Write errors as review issues so the doer sees them
        {
            echo "## 🔨 COMPILATION ERRORS — Fix these before claiming completion!"
            echo ""
            echo "The following compile/analysis errors were detected. Fix ALL of them:"
            echo ""
            echo '```'
            # Show up to 60 error lines, not the full output
            grep -E "error|Error|ERROR" "$compile_output_file" 2>/dev/null | head -60
            echo '```'
            echo ""
            echo "**Total errors: $error_count**"
            echo ""
            echo "Run \`$compile_cmd\` to verify your fixes."
        } > "${RALPH_DIR}/review-issues.txt"

        return 1
    fi
}

# ── Auto-commit after task completion ──
# Commits all staged/unstaged changes with a descriptive message.
# Prevents data loss and gives the critic accurate diffs.
auto_commit_task() {
    local task_id="${1:-unknown}"
    local iteration="${2:-0}"

    if [[ "$AUTO_COMMIT_ON_TASK" != "true" ]]; then
        log_line "DEBUG" "auto_commit_skip reason=disabled"
        return 0
    fi

    # Check if there are changes to commit
    if git diff --quiet 2>/dev/null && git diff --cached --quiet 2>/dev/null; then
        log_line "DEBUG" "auto_commit_skip reason=no_changes"
        return 0
    fi

    echo -e "${BLUE}📦 Auto-committing task completion...${NC}"
    log_line "INFO" "auto_commit_start task=$task_id iteration=$iteration"

    # Stage all changes
    git add -A 2>/dev/null || {
        log_line "WARN" "auto_commit_add_failed"
        return 1
    }

    # Commit with descriptive message
    local commit_msg="feat(ralph): complete task $task_id [iteration $iteration]

Automated commit by Ralph Mode after task completion.
Task: $task_id
Iteration: $iteration
Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

    if git commit -m "$commit_msg" --no-verify 2>/dev/null; then
        local commit_hash=$(git rev-parse --short HEAD 2>/dev/null || echo "???")
        echo -e "${GREEN}✅ Committed: $commit_hash — $task_id${NC}"
        log_line "INFO" "auto_commit_success hash=$commit_hash task=$task_id"
    else
        echo -e "${YELLOW}⚠️ Auto-commit failed (maybe no changes?)${NC}"
        log_line "WARN" "auto_commit_failed task=$task_id"
    fi

    return 0
}

# ── Auto-commit after iteration (incremental safety) ──
# Lighter commit after each iteration to prevent data loss during long tasks.
auto_commit_iteration() {
    local iteration="${1:-0}"
    local task_id="${2:-unknown}"

    if [[ "$AUTO_COMMIT_ON_TASK" != "true" ]]; then
        return 0
    fi

    # Only commit if there are meaningful changes (more than 3 files changed)
    local changed_count=$(git diff --name-only 2>/dev/null | wc -l || echo "0")
    if [[ "$changed_count" -lt 3 ]]; then
        return 0
    fi

    git add -A 2>/dev/null || return 0
    git commit -m "wip(ralph): iteration $iteration progress on $task_id [auto-save]" --no-verify 2>/dev/null || true
    log_line "DEBUG" "auto_commit_iteration iteration=$iteration files=$changed_count"
}

# Run verification review using critic/code-review agent.
# Returns 0 if APPROVED, 1 if REJECTED.
run_verification_review() {
    local iteration="$1"
    local promise="$2"
    local output_file="$3"
    local model=$(get_model)
    local fallback=$(get_fallback_model)
    local copilot_opts=$(build_copilot_opts)

    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     🔍 VERIFICATION REVIEW (Critic Agent)                ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    log_line "INFO" "verification_review_start iteration=$iteration"

    # ── Gather evidence for the critic ──
    # Use `git diff` (unstaged) not `git diff HEAD~1` (which breaks without commits)
    # Use `git diff --cached` for staged changes too
    local task_prompt=$(get_prompt | head -100)
    local git_diff_unstaged=$(git diff 2>/dev/null | head -300 || echo "<no unstaged diff>")
    local git_diff_staged=$(git diff --cached 2>/dev/null | head -100 || echo "<no staged diff>")
    local git_status=$(git status --short 2>/dev/null | head -50 || echo "<clean>")
    local last_output=$(tail -100 "$output_file" 2>/dev/null || echo "<no output>")
    local files_changed=$(git diff --name-only 2>/dev/null | head -30 || echo "<none>")
    local files_staged=$(git diff --cached --name-only 2>/dev/null | head -20 || echo "<none>")

    # Run compile check and include results if available
    local compile_results=""
    local compile_cmd
    compile_cmd=$(detect_compile_check_cmd)
    if [[ -n "$compile_cmd" ]]; then
        local compile_out
        compile_out=$(eval "timeout 60 $compile_cmd" 2>&1 || true)
        local error_lines=$(echo "$compile_out" | grep -ciE "error" 2>/dev/null || true)
        if [[ "$error_lines" -gt 0 ]]; then
            compile_results="
## ⚠️ Compilation/Analysis Results ($error_lines error lines detected)
\`\`\`
$(echo "$compile_out" | grep -iE "error" | head -40)
\`\`\`
"
        else
            compile_results="
## ✅ Compilation Check: PASSED (no errors)
"
        fi
    fi

    # Include Memory Bank context for critic awareness
    local critic_memory=""
    local memory_out
    memory_out=$(python3 "$SCRIPT_DIR/ralph_mode.py" memory show --limit 5 2>/dev/null || echo "")
    if [[ -n "$memory_out" ]]; then
        critic_memory="
## Memory Bank — Previous Learnings
$memory_out
"
    fi

    # Run task-specific verification commands if available
    local verification_results=""
    local verify_out
    verify_out=$(python3 "$SCRIPT_DIR/ralph_mode.py" verify run 2>/dev/null || echo "")
    if [[ -n "$verify_out" ]]; then
        verification_results="
## Task Verification Results
\`\`\`
$(echo "$verify_out" | tail -30)
\`\`\`
"
    fi

    # Build the review prompt and write to file to avoid "Argument list too long"
    local review_prompt_file="${RALPH_DIR}/review-prompt.txt"
    cat > "$review_prompt_file" <<REVIEW_EOF
# Critical Review — Iteration $iteration

You are a **STRICT CODE REVIEWER / CRITIC**. Verify whether the task has GENUINELY been completed with working, compilable code.

## Original Task (summary)
$task_prompt

## Files Changed (unstaged)
$files_changed

## Files Changed (staged)
$files_staged

## Current File Status (git status)
$git_status

## Changes Made (git diff, truncated to 300 lines)
$git_diff_unstaged

## Staged Changes (git diff --cached, truncated)
$git_diff_staged
$compile_results
$critic_memory
$verification_results
## Doer's Last Output (tail)
$last_output

## Your Review Instructions — BE STRICT
1. **Verify acceptance criteria** — run commands to check files exist and have correct content
2. **Look for placeholders** — TODO comments, empty functions, stub implementations = REJECT
3. **Check compilation** — if compile results above show errors, you MUST REJECT
4. **Check imports** — undefined classes, missing imports = REJECT
5. **Check type safety** — type mismatches, dynamic casts = REJECT
6. **Assess completeness** — is the task fully done, not just scaffolded?
7. **Verify structure** — does code follow the architecture described in the task?

## Critical: Compile Errors = Automatic REJECT
If the compilation/analysis results above show ANY errors, you MUST reject.
Code that doesn't compile is NOT complete, regardless of other criteria.

## Your Verdict
If complete with REAL, WORKING, COMPILABLE code: \`<verdict>APPROVED</verdict>\`
If ANY issues exist: \`<verdict>REJECTED</verdict>\` followed by \`<issues>detailed list of problems</issues>\`

⚠️ Be STRICT. Only approve when ALL acceptance criteria are met AND code compiles.
⚠️ Do NOT approve placeholder/skeleton code.
⚠️ Do NOT approve code with undefined references or import errors.
REVIEW_EOF

    # Build model options
    local model_opts=""
    if [[ "$model" != "auto" && -n "$model" ]]; then
        model_opts="--model $model"
    fi

    local review_output_file="${RALPH_DIR}/review-output.txt"

    # Run Copilot CLI for critic review — use critic agent for structured review
    local critic_agent_opts=""
    if [[ -f ".github/agents/critic.md" ]]; then
        critic_agent_opts="--agent=critic"
    fi
    echo -e "${BLUE}🤖 Running critic review...${NC}"
    if cat "$review_prompt_file" | timeout 300 $COPILOT_ENV_PREFIX $COPILOT_CMD $copilot_opts $model_opts $critic_agent_opts 2>&1 | tee "$review_output_file"; then
        echo ""
    else
        echo -e "${YELLOW}⚠️ Review agent failed to run, defaulting to REJECTED (iterate more)${NC}"
        log_line "WARN" "critic_agent_failed"
        return 1
    fi

    # Parse verdict
    if grep -q "<verdict>APPROVED</verdict>" "$review_output_file" 2>/dev/null; then
        echo -e "${GREEN}✅ Critic APPROVED the completion${NC}"
        log_line "INFO" "critic_verdict=APPROVED"
        # Clean up review issues from previous rejections
        rm -f "${RALPH_DIR}/review-issues.txt"
        return 0
    elif grep -q "<verdict>REJECTED</verdict>" "$review_output_file" 2>/dev/null; then
        echo -e "${RED}❌ Critic REJECTED the completion${NC}"
        log_line "INFO" "critic_verdict=REJECTED"

        # Extract issues for next iteration context
        local issues=$(sed -n '/<issues>/,/<\/issues>/p' "$review_output_file" 2>/dev/null || echo "")
        if [[ -n "$issues" ]]; then
            echo -e "${YELLOW}Issues found:${NC}"
            echo "$issues"
            # Save issues so the next iteration context includes them
            echo "$issues" > "${RALPH_DIR}/review-issues.txt"
        fi
        return 1
    else
        echo -e "${YELLOW}⚠️ No clear verdict from critic — defaulting to REJECTED${NC}"
        log_line "INFO" "critic_verdict=UNCLEAR_REJECTED"
        # Save the full review output as issues
        tail -40 "$review_output_file" > "${RALPH_DIR}/review-issues.txt" 2>/dev/null || true
        return 1
    fi
}

# ═══════════════════════════════════════════════════════════════
# End Multi-Agent Verification
# ═══════════════════════════════════════════════════════════════

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

    # ── CRITICAL: Review issues go FIRST so the doer cannot ignore them ──
    if [[ -f "${RALPH_DIR}/review-issues.txt" ]]; then
        context="$context

## 🚨🚨🚨 MANDATORY FIX — PREVIOUS COMPLETION WAS REJECTED 🚨🚨🚨
Your LAST completion claim was **REJECTED** by the critic agent. You MUST fix ALL of the following issues before doing anything else. Do NOT just grep for keywords — actually READ the files and FIX the problems.

$(cat "${RALPH_DIR}/review-issues.txt" 2>/dev/null)

**INSTRUCTIONS:**
1. Fix EVERY issue listed above by making actual file edits
2. After fixing, RE-READ each file to verify the fix is applied
3. Do NOT output the completion promise until ALL issues are resolved
4. Running grep and claiming 'everything is fine' will be REJECTED again
"
    fi

    context="$context

## Task
$prompt

## Rules
1. **Continue from where you left off** — do NOT restart.
2. Make real file changes visible in \`git diff\`.
3. Focus ONLY on files listed in the task scope.
4. If already satisfied, verify and complete — don't redo.
5. **Do NOT claim completion prematurely.** Your work will be reviewed by a critic agent.
6. **Verify ALL acceptance criteria** before outputting the completion promise.
7. Create REAL, working code — not skeletons, placeholders, or TODOs.
8. **If review issues exist above, FIX THEM FIRST.** Do not ignore critic feedback.

## Repository State
\`\`\`
$(git status --short 2>/dev/null | head -40 || echo '<clean>')
\`\`\`

## Recent Changes (diff stat)
\`\`\`
$(git diff --stat 2>/dev/null | tail -20 || echo '<no changes>')
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

    # Include environment notes if available
    if [[ -f "${RALPH_DIR}/environment-notes.md" ]]; then
        context="$context
## Environment & Available Resources
$(cat "${RALPH_DIR}/environment-notes.md" 2>/dev/null)
"
    fi

    # Include Memory Bank context for long-term awareness across iterations
    local memory_context
    memory_context=$(python3 "$SCRIPT_DIR/ralph_mode.py" memory show --limit 10 2>/dev/null || echo "")
    if [[ -n "$memory_context" ]]; then
        context="$context
## Memory Bank (key learnings from previous iterations)
$memory_context
"
    fi

    # Include relevant semantic memories (patterns, decisions, dependencies)
    local semantic_memories
    semantic_memories=$(python3 "$SCRIPT_DIR/ralph_mode.py" memory search "current task" --memory-type semantic --limit 5 2>/dev/null || echo "")
    if [[ -n "$semantic_memories" ]]; then
        context="$context
## Remembered Patterns & Decisions
$semantic_memories
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
⚠️ Your output will be reviewed by a COMPILATION CHECK and then a CRITIC AGENT.
⚠️ If compilation fails (e.g. \`dart analyze\` shows errors), completion is auto-rejected.
⚠️ Skeleton code, placeholders, or incomplete implementations will be REJECTED.
⚠️ Minimum $MIN_ITERATIONS iterations required before completion is accepted.
⚠️ If there were review issues listed above, you MUST have fixed ALL of them with actual file edits before claiming completion. Running grep to 'verify' without fixing is not acceptable.
⚠️ ALWAYS run a compilation/analysis check before claiming completion.
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

    # Build context/prompt and write to file (avoid ARG_MAX limits)
    local context_file="${RALPH_DIR}/iteration-context.txt"
    build_context > "$context_file"

    if [[ "$verbose" == "true" ]]; then
        echo -e "${YELLOW}📝 Context:${NC}"
        cat "$context_file"
        echo ""
    fi

    # Build model options
    local model_opts=""
    if [[ "$model" != "auto" && -n "$model" ]]; then
        model_opts="--model $model"
    fi

    # Build agent options — default to 'ralph' agent for structured iterations
    local agent_opts=""
    if [[ -n "$agent" ]]; then
        agent_opts="--agent=$agent"
    elif [[ -f ".github/agents/ralph.md" ]]; then
        agent_opts="--agent=ralph"
        log_line "DEBUG" "using_default_agent=ralph"
    fi

    # Run Copilot CLI
    echo -e "${BLUE}🤖 Running GitHub Copilot CLI...${NC}"
    log_line "INFO" "copilot_cmd=$COPILOT_CMD"

    local cmd="cat $context_file | $COPILOT_ENV_PREFIX $COPILOT_CMD $copilot_opts $model_opts $agent_opts"

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
        if cat "$context_file" | timeout 600 $COPILOT_ENV_PREFIX $COPILOT_CMD $copilot_opts $model_opts $agent_opts 2>&1 | tee "$OUTPUT_FILE"; then
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
                    if ! wait_for_internet; then
                        echo -e "${RED}❌ Network wait timed out during iteration${NC}"
                        log_line "WARN" "network_timeout_during_iteration"
                        exit_code=28  # timeout
                        break
                    fi
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
                if cat "$context_file" | timeout 600 $COPILOT_ENV_PREFIX $COPILOT_CMD $copilot_opts $model_opts $agent_opts 2>&1 | tee "$OUTPUT_FILE"; then
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

    # ── Auto-commit iteration progress ──
    auto_commit_iteration "$iteration"

    # ── Advanced Contexting: pre-build context for next iteration ──
    write_context_file

    # Save session info for resume capability
    echo "{\"last_iteration\": $iteration, \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > "$SESSION_FILE"

    # Check for completion promise in output
    log_line "DEBUG" "checking_complete promise='$promise' promise_detected='$promise_detected'"
    if [[ -n "$promise" && "$promise_detected" == "true" ]]; then
        log_line "INFO" "promise_complete_block_entered=true"
        echo ""
        echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
        echo -e "${CYAN}🔔 COMPLETION PROMISE DETECTED — Starting verification...${NC}"
        echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"

        # ── Quality Gate 1: Minimum iterations check ──
        if [[ "$iteration" -lt "$MIN_ITERATIONS" ]]; then
            echo -e "${YELLOW}⚠️ Minimum iterations not met ($iteration < $MIN_ITERATIONS). Rejecting early completion.${NC}"
            log_line "INFO" "min_iterations_reject iteration=$iteration min=$MIN_ITERATIONS"

            # ── Give ACTIONABLE feedback, not just "iterate more" ──
            # Run compilation check and include results as feedback
            local early_compile_feedback=""
            local early_compile_cmd
            early_compile_cmd=$(detect_compile_check_cmd)
            if [[ -n "$early_compile_cmd" ]]; then
                local early_compile_out
                early_compile_out=$(eval "timeout 60 $early_compile_cmd" 2>&1 || true)
                local early_error_count=$(echo "$early_compile_out" | grep -ciE "error" 2>/dev/null || true)
                if [[ "$early_error_count" -gt 0 ]]; then
                    early_compile_feedback="

## 🔨 Compilation Errors Found ($early_error_count)
Fix these errors in this iteration:
\`\`\`
$(echo "$early_compile_out" | grep -iE "error" | head -30)
\`\`\`
"
                fi
            fi

            # Save constructive feedback for the next iteration
            cat > "${RALPH_DIR}/review-issues.txt" <<EARLY_EOF
Your completion claim was rejected because the minimum iteration threshold ($MIN_ITERATIONS) has not been reached (you are on iteration $iteration).

**In this iteration, you MUST:**
1. Re-read ALL files you created/modified and verify they are correct
2. Fix any compilation errors listed below
3. Check for TODO/FIXME/placeholder comments and replace them with real code
4. Verify all imports resolve correctly
5. Ensure all acceptance criteria from the task are genuinely met
6. Only then claim completion again
${early_compile_feedback}
EARLY_EOF
        else
            # ── Pre-Gate: Run task-specific verification commands ──
            local verify_result
            verify_result=$(python3 "$SCRIPT_DIR/ralph_mode.py" verify run 2>/dev/null || echo "")
            if [[ -n "$verify_result" ]]; then
                echo -e "${CYAN}📋 Task verification results available${NC}"
                log_line "INFO" "verification_ran"
            fi

            # ── Quality Gate 0: Compilation/Analysis Check ──
            # Block critic entirely if code doesn't compile
            if ! run_compilation_gate; then
                echo -e "${YELLOW}⚠️ Compilation gate FAILED — skipping critic, forcing fix iteration${NC}"
                log_line "INFO" "compilation_gate_blocked_critic"
                # review-issues.txt already written by run_compilation_gate
            else
                # ── Quality Gate 2: Critic verification review ──
                if run_verification_review "$iteration" "$promise" "$OUTPUT_FILE"; then
                    echo ""
                    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
                    echo -e "${GREEN}✅ VERIFIED AND APPROVED BY CRITIC!${NC}"
                    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"

                    # ── Auto-commit the completed task ──
                    local task_id=$(get_state "current_task_id")
                    auto_commit_task "${task_id:-unknown}" "$iteration"

                    # Export for completion hook
                    export RALPH_PROMISE="$promise"

                    # Run completion hook
                    run_hook "on-completion"

                    # Complete the task
                    python3 "$SCRIPT_DIR/ralph_mode.py" complete < "$OUTPUT_FILE" || true
                    return 0
                else
                    echo -e "${YELLOW}⚠️ Critic REJECTED completion. Continuing iterations...${NC}"
                    log_line "INFO" "critic_rejected_continuing"
                fi
            fi
        fi
    fi

    # ── Auto-save iteration progress (incremental safety) ──
    local task_id_save=$(get_state "current_task_id")
    auto_commit_iteration "$iteration" "${task_id_save:-unknown}"

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
                if ! wait_for_internet; then
                    # Network timeout exceeded — skip to next task in batch mode
                    local mode=$(get_state "mode")
                    if [[ "$mode" == "batch" ]]; then
                        echo -e "${YELLOW}⚠️ Network timeout — skipping to next task...${NC}"
                        log_line "WARN" "network_timeout_skip_task"
                        python3 "$SCRIPT_DIR/ralph_mode.py" next-task 2>/dev/null || true
                        consecutive_failures=0
                        continue
                    else
                        echo -e "${RED}❌ Network timeout in single mode. Stopping.${NC}"
                        save_checkpoint "network_timeout"
                        break
                    fi
                fi
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
