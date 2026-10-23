#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYSIS_DIR="$ROOT_DIR/data-analysis"
SCRIPTS_DIR="$ANALYSIS_DIR/scripts"
VENV_ACTIVATE="$ANALYSIS_DIR/venv/bin/activate"
ANALYSIS_LOG="$ROOT_DIR/data-analysis.log"

PROCESSED_DIR="$ANALYSIS_DIR/processed-data"
FIGURES_DIR="$ANALYSIS_DIR/figures"

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    if [[ -f "$VENV_ACTIVATE" ]]; then
        source "$VENV_ACTIVATE"
    else
        echo "Error: Virtual environment not found at $VENV_ACTIVATE" >&2
        echo "Activate it or create it with 'python3 -m venv data-analysis/venv' first." >&2
        exit 1
    fi
fi

exec > >(tee -a "$ANALYSIS_LOG") 2>&1

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Data Analysis Pipeline Initialized"
echo "Running data analysis pipeline..."

echo "  - Resetting processed-data and figures directories..."
rm -rf "$PROCESSED_DIR" "$FIGURES_DIR"
mkdir -p "$PROCESSED_DIR" "$FIGURES_DIR"

echo "  - [1/4] Processing k6 metrics..."
python3 "$SCRIPTS_DIR/01_parse_k6.py"

echo "  - [2/4] Extracting JFR telemetry..."
python3 "$SCRIPTS_DIR/02_parse_jfr.py"

echo "  - [3/4] Consolidating dataset..."
python3 "$SCRIPTS_DIR/03_consolidate.py"

echo "  - [4/4] Generating figures..."
python3 "$SCRIPTS_DIR/04_generate_figures.py"

echo "Analysis complete."
echo "  - Dataset: data-analysis/processed-data/dataset_final.csv"
echo "  - Figures: data-analysis/figures/"
