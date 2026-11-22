#!/usr/bin/env bash
# Enforce strict execution mode: exit on error (-e), undefined vars (-u), or pipeline failures (-o pipefail)
set -euo pipefail

# Resolve repository root dynamically to ensure portability regardless of the cloned directory name
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_NAME="orm-benchmark"

# Verify tmux availability before attempting session management
if ! command -v tmux > /dev/null 2>&1; then
    echo "  ! Error: 'tmux' is not installed or not in PATH." >&2
    exit 1
fi

# Idempotent session handling: reattach if an active benchmark session exists,
# otherwise initialize a new persistent session anchored at the repository root
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Attaching to existing tmux session [$SESSION_NAME]..."
    exec tmux attach-session -t "$SESSION_NAME"
else
    echo "Initializing persistent tmux session [$SESSION_NAME] at $ROOT_DIR..."
    exec tmux new-session -s "$SESSION_NAME" -c "$ROOT_DIR"
fi
