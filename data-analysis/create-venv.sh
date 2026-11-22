#!/usr/bin/env bash
# Enforce strict execution mode: exit on error (-e), undefined vars (-u), or pipeline failures (-o pipefail)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

# Locate requirements.txt either inside data-analysis/ or at the repository root
if [[ -f "$SCRIPT_DIR/requirements.txt" ]]; then
    REQ_FILE="$SCRIPT_DIR/requirements.txt"
elif [[ -f "$SCRIPT_DIR/../requirements.txt" ]]; then
    REQ_FILE="$SCRIPT_DIR/../requirements.txt"
else
    echo "  ! Error: requirements.txt not found in $SCRIPT_DIR or repository root." >&2
    exit 1
fi

# Purge any stale or broken virtual environment (e.g., after system Python upgrades)
if [[ -d "$VENV_DIR" ]]; then
    echo "Removing existing virtual environment at $VENV_DIR..."
    rm -rf "$VENV_DIR"
fi

# Initialize a clean isolated Python virtual environment
echo "Creating fresh virtual environment at $VENV_DIR..."
python3 -m venv "$VENV_DIR"

# Activate environment, upgrade pip, and install pinned analysis dependencies
source "$VENV_DIR/bin/activate"
echo "Installing analysis dependencies from $(basename "$REQ_FILE")..."
pip install --upgrade pip -q
pip install -r "$REQ_FILE"

# Smoke-test core scientific libraries required by scripts 01 through 05
python3 -c "import pandas, numpy, scipy, matplotlib, seaborn; print('  - Core scientific packages verified successfully.')"
deactivate

echo "Virtual environment ready: $VENV_DIR"
