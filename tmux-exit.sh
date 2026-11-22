#!/usr/bin/env bash
# Enforce strict execution mode: exit on error (-e), undefined vars (-u), or pipeline failures (-o pipefail)
set -euo pipefail

SESSION_NAME="orm-benchmark"

# Verify tmux availability
if ! command -v tmux > /dev/null 2>&1; then
    echo "  ! Error: 'tmux' is not installed or not in PATH." >&2
    exit 1
fi

# Terminate the persistent benchmark session cleanly if currently active
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    tmux kill-session -t "$SESSION_NAME"
    echo "Persistent tmux session [$SESSION_NAME] terminated."
else
    echo "No active tmux session named [$SESSION_NAME] found."
fi
