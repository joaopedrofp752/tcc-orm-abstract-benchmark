#!/usr/bin/env bash
# Enforce strict execution mode
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYSIS_DIR="$ROOT_DIR/data-analysis"
SCRIPTS_DIR="$ANALYSIS_DIR/scripts"
VENV_DIR="$ANALYSIS_DIR/venv"
VENV_ACTIVATE="$VENV_DIR/bin/activate"
CREATE_VENV_SCRIPT="$ANALYSIS_DIR/create-venv.sh"
ANALYSIS_LOG="$ROOT_DIR/data-analysis.log"

PROCESSED_DIR="$ANALYSIS_DIR/processed-data"
FIGURES_DIR="$ANALYSIS_DIR/figures"

# Provision or rebuild the isolated virtual environment if missing or broken
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    if [[ ! -f "$VENV_ACTIVATE" ]] || ! "$VENV_DIR/bin/python" -c "import pandas, numpy, scipy, matplotlib, seaborn" > /dev/null 2>&1; then
        echo "Virtual environment missing or broken. Rebuilding via create-venv.sh..."
        "$CREATE_VENV_SCRIPT"
    fi
    source "$VENV_ACTIVATE"
fi

# Duplicate all stdout and stderr streams to both terminal and cumulative log file
exec > >(tee -a "$ANALYSIS_LOG") 2>&1

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Data analysis pipeline initialized"
echo "Running data analysis pipeline..."

# Purge previously generated outputs to prevent stale or orphaned artifacts
echo "  - Resetting processed-data and figures directories..."
rm -rf "$PROCESSED_DIR" "$FIGURES_DIR"
mkdir -p "$PROCESSED_DIR" "$FIGURES_DIR"

# Stage 1: Parse raw k6 CSV latency, throughput, and drop samples
echo "  - [1/5] Processing k6 metrics..."
python3 "$SCRIPTS_DIR/01_parse_k6.py"

# Stage 2: Extract GC pauses, CPU utilization, and heap telemetry from JFR files
echo "  - [2/5] Extracting JFR telemetry..."
python3 "$SCRIPTS_DIR/02_parse_jfr.py"

# Stage 3: Consolidate parsed telemetry into unified primary and diagnostic datasets
echo "  - [3/5] Consolidating datasets..."
python3 "$SCRIPTS_DIR/03_consolidate.py"

# Stage 4: Render stability plots, cross-scenario charts, and diagnostic figures (300 DPI)
echo "  - [4/5] Generating figures..."
python3 "$SCRIPTS_DIR/04_generate_figures.py"

# Stage 5: Statistical validation (Shapiro-Wilk, Mann-Whitney U, Holm, and Cliff's delta)
echo "  - [5/5] Running statistical validation tests..."
python3 "$SCRIPTS_DIR/05_statistical_tests.py"

echo "Analysis complete."
echo "  - Primary Dataset:     data-analysis/processed-data/dataset_final.csv"
echo "  - Diagnostics Dataset: data-analysis/processed-data/diagnostics_dataset.csv"
echo "  - Statistical Results: data-analysis/processed-data/"
echo "  - Figures:             data-analysis/figures/"
