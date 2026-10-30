#!/usr/bin/env bash
# Enforce strict execution mode
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYSIS_DIR="$ROOT_DIR/data-analysis"
SCRIPTS_DIR="$ANALYSIS_DIR/scripts"
VENV_ACTIVATE="$ANALYSIS_DIR/venv/bin/activate"
ANALYSIS_LOG="$ROOT_DIR/data-analysis.log"

PROCESSED_DIR="$ANALYSIS_DIR/processed-data"
FIGURES_DIR="$ANALYSIS_DIR/figures"

# Enforce active virtual environment or load project-local venv
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    if [[ -f "$VENV_ACTIVATE" ]]; then
        source "$VENV_ACTIVATE"
    else
        echo "Error: Virtual environment not found at $VENV_ACTIVATE" >&2
        echo "Activate it or create it with 'python3 -m venv data-analysis/venv' first." >&2
        exit 1
    fi
fi

# Duplicate all stdout and stderr streams to both terminal and cumulative log file
exec > >(tee -a "$ANALYSIS_LOG") 2>&1

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Data analysis pipeline initialized"
echo "Running data analysis pipeline..."

# Purge previously generated outputs to prevent stale or orphaned artifacts
echo "  - Resetting processed-data and figures directories..."
rm -rf "$PROCESSED_DIR" "$FIGURES_DIR"
mkdir -p "$PROCESSED_DIR" "$FIGURES_DIR"

# Stage 1: Parse raw k6 CSV latency and throughput samples
echo "  - [1/4] Processing k6 metrics..."
python3 "$SCRIPTS_DIR/01_parse_k6.py"

# Stage 2: Extract GC pauses, CPU utilization, and heap telemetry from JFR files
echo "  - [2/4] Extracting JFR telemetry..."
python3 "$SCRIPTS_DIR/02_parse_jfr.py"

# Stage 3: Consolidate parsed telemetry into single unified dataset
echo "  - [3/4] Consolidating dataset..."
python3 "$SCRIPTS_DIR/03_consolidate.py"

# Stage 4: Render stability plots and multi-scenario comparative figures (300 DPI)
echo "  - [4/5] Generating figures..."
python3 "$SCRIPTS_DIR/04_generate_figures.py"

# Stage 5: Statistical validation (Shapiro-Wilk normality & Wilcoxon/Mann-Whitney)
echo "  - [5/5] Running statistical validation tests..."
python3 "$SCRIPTS_DIR/05_statistical_tests.py"

echo "Analysis complete."
echo "  - Dataset:             data-analysis/processed-data/dataset_final.csv"
echo "  - Statistical Results: data-analysis/processed-data/"
echo "  - Figures:             data-analysis/figures/"
