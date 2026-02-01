#!/usr/bin/env bash
#
# ralph-loop.sh - The actual Ralph loop runner for gh copilot CLI
# 
# This script runs the continuous iteration loop with gh copilot.
# It's the "real Ralph" - a bash while loop that keeps running until done.
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
NC='\033[0m'

# Defaults
RALPH_DIR=".ralph-mode"
STATE_FILE="$RALPH_DIR/state.json"
PROMPT_FILE="$RALPH_DIR/prompt.md"
OUTPUT_FILE="$RALPH_DIR/output.txt"
HISTORY_FILE="$RALPH_DIR/history.jsonl"
SLEEP_BETWEEN=2
ALLOW_TOOLS="shell(git,npm,node,python3,cat,ls,grep,find,mkdir,cp,mv,rm,touch,echo,head,tail,wc)"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Help message
show_help() {
    cat << EOF
${GREEN}🔄 Ralph Loop Runner${NC}

Runs the actual Ralph loop with gh copilot CLI.

${YELLOW}USAGE:${NC}
    ralph-loop.sh run [options]          # Start the loop
    ralph-loop.sh single [options]       # Run single iteration
    ralph-loop.sh help                   # Show this help

${YELLOW}OPTIONS:${NC}
    --sleep <seconds>       Sleep between iterations (default: 2)
    --allow-tools <tools>   Tools to allow gh copilot to use
    --dry-run               Print commands without executing
    --verbose               Verbose output

${YELLOW}EXAMPLES:${NC}
    # First, enable Ralph mode
    python3 ralph_mode.py enable "Fix all linting errors" --max-iterations 10 --completion-promise "DONE"
    
    # Then run the loop
    ./ralph-loop.sh run
    
    # Or run single iteration manually
    ./ralph-loop.sh single

${YELLOW}REQUIREMENTS:${NC}
    - gh cli installed (https://cli.github.com)
    - gh copilot extension (gh extension install github/gh-copilot)
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

# Get prompt
get_prompt() {
    cat "$PROMPT_FILE" 2>/dev/null || echo ""
}

# Build the full context for gh copilot
build_context() {
    local iteration=$(get_iteration)
    local max_iter=$(get_max_iterations)
    local promise=$(get_promise)
    local prompt=$(get_prompt)
    local mode=$(get_state "mode")
    
    local context="# Ralph Mode - Iteration $iteration"
    [[ "$max_iter" -gt 0 ]] && context="$context / $max_iter"
    context="$context

## Your Task
$prompt

## Rules
1. Work on the task above
2. Make real changes to files using shell tools
3. Check your progress - are you getting closer to done?
4. If there are errors, fix them

## Current Directory
$(pwd)

## Key Files
- State: $STATE_FILE
- Prompt: $PROMPT_FILE
"
    
    if [[ -n "$promise" ]]; then
        context="$context
## Completion
When the task is GENUINELY COMPLETE, output exactly:
<promise>$promise</promise>

⚠️ ONLY output this when truly done. Don't lie to exit.
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
    
    echo "$context"
}

# Run single iteration with gh copilot
run_single() {
    local dry_run="${1:-false}"
    local verbose="${2:-false}"
    
    check_active
    
    local iteration=$(get_iteration)
    local max_iter=$(get_max_iterations)
    local promise=$(get_promise)
    
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║          🔄 Ralph Iteration $iteration                              ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    
    # Build context/prompt
    local context=$(build_context)
    
    if [[ "$verbose" == "true" ]]; then
        echo -e "${YELLOW}📝 Context:${NC}"
        echo "$context"
        echo ""
    fi
    
    # Run gh copilot
    echo -e "${BLUE}🤖 Running gh copilot...${NC}"
    
    local cmd="gh copilot -p \"$context\" --allow-tool \"$ALLOW_TOOLS\""
    
    if [[ "$dry_run" == "true" ]]; then
        echo -e "${YELLOW}[DRY RUN] Would execute:${NC}"
        echo "$cmd"
        return 0
    fi
    
    # Execute and capture output
    mkdir -p "$RALPH_DIR"
    
    # Use timeout to prevent infinite hangs
    if timeout 600 gh copilot -p "$context" --allow-tool "$ALLOW_TOOLS" 2>&1 | tee "$OUTPUT_FILE"; then
        echo ""
    else
        echo -e "${YELLOW}⚠️ gh copilot exited with non-zero status${NC}"
    fi
    
    # Check for completion promise in output
    if [[ -n "$promise" ]] && grep -q "<promise>$promise</promise>" "$OUTPUT_FILE" 2>/dev/null; then
        echo ""
        echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}✅ COMPLETION PROMISE DETECTED!${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
        
        # Complete the task
        python3 "$SCRIPT_DIR/ralph_mode.py" complete "$(cat "$OUTPUT_FILE")" || true
        return 0
    fi
    
    # Increment iteration
    python3 "$SCRIPT_DIR/ralph_mode.py" iterate || {
        echo -e "${YELLOW}⚠️ Max iterations reached or error${NC}"
        return 1
    }
    
    return 0
}

# Run the continuous loop
run_loop() {
    local dry_run="${1:-false}"
    local verbose="${2:-false}"
    local sleep_time="${3:-$SLEEP_BETWEEN}"
    
    check_active
    
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              🔄 RALPH LOOP STARTING                      ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}Press Ctrl+C to stop the loop${NC}"
    echo ""
    
    local iteration=1
    local max_iter=$(get_max_iterations)
    
    while true; do
        # Check if still active
        if [[ ! -f "$STATE_FILE" ]]; then
            echo -e "${GREEN}✅ Ralph mode completed or disabled${NC}"
            break
        fi
        
        iteration=$(get_iteration)
        
        # Check max iterations
        if [[ "$max_iter" -gt 0 ]] && [[ "$iteration" -gt "$max_iter" ]]; then
            echo -e "${YELLOW}⚠️ Max iterations ($max_iter) reached${NC}"
            break
        fi
        
        # Run single iteration
        if ! run_single "$dry_run" "$verbose"; then
            echo -e "${YELLOW}Loop stopped${NC}"
            break
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

# Parse arguments
main() {
    local cmd="${1:-help}"
    shift || true
    
    local dry_run=false
    local verbose=false
    local sleep_time=$SLEEP_BETWEEN
    
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
            --allow-tools)
                ALLOW_TOOLS="$2"
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
            run_loop "$dry_run" "$verbose" "$sleep_time"
            ;;
        single|once)
            run_single "$dry_run" "$verbose"
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
