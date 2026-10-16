#!/bin/bash
set -euo pipefail

TARGET="${1:-}"

if [[ "$TARGET" != "hibernate" && "$TARGET" != "dto" && "$TARGET" != "jdbc" ]]; then
    echo "Usage: $0 <hibernate|dto|jdbc>"
    exit 1
fi

# Pre-flight check: ensure backend is alive before starting a 5-minute allocation cycle
if ! curl -sf "http://localhost:8080/api/benchmark/health" > /dev/null 2>&1; then
    echo "Error: Backend is unreachable on port 8080. Aborting battery."
    exit 1
fi

TOTAL_RUNS=10
PAUSE_TIME=60
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${BASE_DIR}/results/${TARGET}"

mkdir -p "$OUTPUT_DIR"

echo "Initializing Battery for [${TARGET}] | Runs: ${TOTAL_RUNS}..."

for i in $(seq 1 "$TOTAL_RUNS")
do
    RUN_NUM=$(printf "%02d" "$i")
    OUTPUT_FILE="${OUTPUT_DIR}/run_${RUN_NUM}.csv"

    echo "[$(date +'%H:%M:%S')] Starting run ${RUN_NUM}/${TOTAL_RUNS} for ${TARGET}..."
    
    # Injects target route dynamically matching the active strategy
    k6 run \
        -e TARGET_ENDPOINT="$TARGET" \
        --out "csv=${OUTPUT_FILE}" \
        "${BASE_DIR}/k6-benchmark.js"

    if [ "$i" -lt "$TOTAL_RUNS" ]; then
        echo "[$(date +'%H:%M:%S')] Run ${RUN_NUM} finished. Cooldown for ${PAUSE_TIME}s (GC/Thermal settling)..."
        sleep "$PAUSE_TIME"
    fi
done

echo "Battery for [${TARGET}] completed successfully!"
