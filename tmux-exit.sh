#!/usr/bin/env bash
# Enforce strict execution mode
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_NAME="orm-benchmark"
INHIBIT_PID_FILE="$ROOT_DIR/.tmux-inhibit.pid"

# Terminate the persistent tmux session if running
if command -v tmux > /dev/null 2>&1 && tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    tmux kill-session -t "$SESSION_NAME"
    echo "Terminated tmux session [$SESSION_NAME]."
else
    echo "No active tmux session [$SESSION_NAME] found."
fi

# Release the background systemd-inhibit lock and clean up its PID file
if [[ -f "$INHIBIT_PID_FILE" ]]; then
    INHIBIT_PID=$(cat "$INHIBIT_PID_FILE" 2>/dev/null || echo "")
    if [[ -n "$INHIBIT_PID" ]] && kill -0 "$INHIBIT_PID" 2>/dev/null; then
        kill "$INHIBIT_PID" 2>/dev/null || true
        echo "  - Released system sleep/idle inhibitor (PID $INHIBIT_PID)."
    fi
    rm -f "$INHIBIT_PID_FILE"
fi
