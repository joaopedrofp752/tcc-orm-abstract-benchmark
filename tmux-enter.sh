#!/usr/bin/env bash
# Enforce strict execution mode
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_NAME="orm-benchmark"
INHIBIT_PID_FILE="$ROOT_DIR/.tmux-inhibit.pid"

# Verify tmux is available
if ! command -v tmux > /dev/null 2>&1; then
    echo "  ! Error: 'tmux' is not installed or not in PATH." >&2
    exit 1
fi

# Create a detached persistent session anchored at repository root if none exists
if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Creating persistent tmux session [$SESSION_NAME]..."
    tmux new-session -d -s "$SESSION_NAME" -c "$ROOT_DIR"
else
    echo "Reattaching to existing tmux session [$SESSION_NAME]..."
fi

# Start a background systemd-inhibit lock tied to the lifetime of the tmux session
# (stays active even if the client detaches with Ctrl+b d, and exits if closed manually)
if command -v systemd-inhibit > /dev/null 2>&1; then
    INHIBIT_ACTIVE=false
    if [[ -f "$INHIBIT_PID_FILE" ]]; then
        EXISTING_PID=$(cat "$INHIBIT_PID_FILE" 2>/dev/null || echo "")
        if [[ -n "$EXISTING_PID" ]] && kill -0 "$EXISTING_PID" 2>/dev/null; then
            INHIBIT_ACTIVE=true
        fi
    fi

    if [[ "$INHIBIT_ACTIVE" == false ]]; then
        nohup systemd-inhibit \
            --what=idle:sleep:handle-lid-switch \
            --who="ORM Benchmark" \
            --why="Active benchmark session [$SESSION_NAME]" \
            bash -c "while tmux has-session -t '$SESSION_NAME' 2>/dev/null; do sleep 5; done" \
            > /dev/null 2>&1 &
        echo $! > "$INHIBIT_PID_FILE"
        echo "  - System sleep/idle inhibitor enabled (PID $(cat "$INHIBIT_PID_FILE"))."
    fi
fi

# Attach or switch to the target session depending on whether we are already inside tmux
if [[ -n "${TMUX:-}" ]]; then
    exec tmux switch-client -t "$SESSION_NAME"
else
    exec tmux attach-session -t "$SESSION_NAME"
fi
