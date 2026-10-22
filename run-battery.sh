#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT_DIR/.backend.pid"
LOG_FILE="$ROOT_DIR/load-tests.log"
K6_SCRIPT="$ROOT_DIR/load-tests/k6-benchmark.js"

# Resolve target strategy (argument or current active git branch)
TARGET="${1:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")}"

if [[ "$TARGET" != "hibernate" && "$TARGET" != "hibernate-dto" && "$TARGET" != "jdbc" ]]; then
    echo "Usage: $0 <hibernate|hibernate-dto|jdbc>"
    echo "Or execute directly from within one of the study branches."
    exit 1
fi

TOTAL_RUNS="${TOTAL_RUNS:-10}"
TEST_DURATION="${TEST_DURATION:-90}"
COOLDOWN_TIME="${COOLDOWN_TIME:-30}"
WARMUP_DURATION=60

K6_RESULTS_DIR="$ROOT_DIR/data-analysis/raw-data/$TARGET/k6"
JFR_RESULTS_DIR="$ROOT_DIR/data-analysis/raw-data/$TARGET/jfr"

# --- 1. Pre-flight Validation ---
echo "Validating lab state for target [$TARGET]..."

if [[ ! -f "$PID_FILE" ]]; then
    echo "  ! Error: '$PID_FILE' not found. Run ./up-lab.sh first."
    exit 1
fi

BACKEND_PID=$(cat "$PID_FILE")
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "  ! Error: Backend process (PID $BACKEND_PID) is not running."
    exit 1
fi
echo "  - Backend process verified (PID $BACKEND_PID)"

if ! curl -s -f http://localhost:8080/actuator/health | grep -q '"status":"UP"'; then
    echo "  ! Error: Actuator health check failed on port 8080."
    exit 1
fi
echo "  - Actuator health check confirmed UP"

for cmd in k6 jcmd; do
    if ! command -v "$cmd" > /dev/null 2>&1; then
        echo "  ! Error: Required command '$cmd' is not installed or not in PATH."
        exit 1
    fi
done
echo "  - Telemetry tooling confirmed (k6, jcmd)"

mkdir -p "$K6_RESULTS_DIR" "$JFR_RESULTS_DIR"

# Initialize fresh log file for this battery execution
echo "Benchmark Battery Initialized [$(date +'%Y-%m-%d %H:%M:%S')] | Target: $TARGET ===" > "$LOG_FILE"

# --- 2. JIT & Connection Warm-up ---
echo ""
echo "Executing JVM warm-up phase (30s)..."
echo "  - Priming JIT C2 compiler and HikariCP connection pool..."
echo "--- Warm-up Phase ---" >> "$LOG_FILE"

k6 run --duration "${WARMUP_DURATION}s" --vus 5 "$K6_SCRIPT" >> "$LOG_FILE" 2>&1 &
WARMUP_PID=$!

for ((sec=WARMUP_DURATION; sec>0; sec--)); do
    if ! kill -0 "$WARMUP_PID" 2>/dev/null; then
        break
    fi
    printf "\r  - Warm-up progress: %2ds remaining..." "$sec"
    sleep 1
done
wait "$WARMUP_PID" 2>/dev/null || true
printf "\r  - Warm-up completed. Settling GC for 10s...                \n"
sleep 10

# --- 3. Experimental Battery Execution ---
echo ""
echo "Starting benchmark battery [$TARGET] | Runs: $TOTAL_RUNS"

for i in $(seq 1 "$TOTAL_RUNS"); do
    RUN_NUM=$(printf "%02d" "$i")
    CSV_FILE="$K6_RESULTS_DIR/run_${RUN_NUM}.csv"
    JFR_FILE="$JFR_RESULTS_DIR/run_${RUN_NUM}.jfr"

    echo ""
    echo "[Run $RUN_NUM/$TOTAL_RUNS] Recording telemetry..."
    echo "--- Run $RUN_NUM/$TOTAL_RUNS [$TARGET] ---" >> "$LOG_FILE"

    # Start Java Flight Recorder profiling on the active JVM
    jcmd "$BACKEND_PID" JFR.start name="run_${RUN_NUM}" settings=profile filename="$JFR_FILE" >> "$LOG_FILE" 2>&1
    echo "  - JFR profiling started -> data-analysis/raw-data/$TARGET/jfr/run_${RUN_NUM}.jfr"

    # Inject load in background and stream logs into load-tests.log
    k6 run --out "csv=$CSV_FILE" "$K6_SCRIPT" >> "$LOG_FILE" 2>&1 &
    K6_PID=$!

    for ((sec=TEST_DURATION; sec>0; sec--)); do
        if ! kill -0 "$K6_PID" 2>/dev/null; then
            break
        fi
        printf "\r  - Injecting load via k6: %2ds remaining..." "$sec"
        sleep 1
    done
    wait "$K6_PID"
    printf "\r  - Load test completed -> data-analysis/raw-data/$TARGET/k6/run_${RUN_NUM}.csv\n"

    # Stop JFR session and flush binary buffer
    jcmd "$BACKEND_PID" JFR.stop name="run_${RUN_NUM}" >> "$LOG_FILE" 2>&1
    echo "  - JFR profiling stopped and flushed"

    if [[ "$i" -lt "$TOTAL_RUNS" ]]; then
        for ((sec=COOLDOWN_TIME; sec>0; sec--)); do
            printf "\r  - Cooldown: %2ds remaining (GC & thermal settling)..." "$sec"
            sleep 1
        done
        printf "\r  - Cooldown completed.                                        \n"
    fi
done

echo ""
echo "Battery completed successfully for [$TARGET]."
echo "  - k6 Latency CSVs : $K6_RESULTS_DIR/"
echo "  - JFR Recordings  : $JFR_RESULTS_DIR/"
echo "  - Full Execution Log: $LOG_FILE"
