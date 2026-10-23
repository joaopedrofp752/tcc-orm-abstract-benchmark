#!/usr/bin/env bash
# Enforce strict execution mode
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT_DIR/.backend.pid"
LOG_FILE="$ROOT_DIR/load-tests.log"
K6_SCRIPT="$ROOT_DIR/load-tests/k6-benchmark.js"

# Default workload scenario and target persistence strategy
SCENARIO="nominal"
TARGET=""

# Parse positional and flagged command line arguments
for arg in "$@"; do
    case "$arg" in
        --nominal|nominal)
            SCENARIO="nominal"
            ;;
        --saturation|saturation)
            SCENARIO="saturation"
            ;;
        hibernate|hibernate-dto|jdbc)
            TARGET="$arg"
            ;;
        *)
            echo "Unknown option: $arg"
            echo "Usage: $0 [--nominal|--saturation] [hibernate|hibernate-dto|jdbc]"
            exit 1
            ;;
    esac
done

# If target is omitted, automatically detect the current active Git branch
if [[ -z "$TARGET" ]]; then
    TARGET="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
fi

if [[ "$TARGET" != "hibernate" && "$TARGET" != "hibernate-dto" && "$TARGET" != "jdbc" ]]; then
    echo "Error: Invalid target strategy [$TARGET]."
    echo "Usage: $0 [--nominal|--saturation] [hibernate|hibernate-dto|jdbc]"
    exit 1
fi

TOTAL_RUNS="${TOTAL_RUNS:-10}"
TEST_DURATION="${TEST_DURATION:-90}"
COOLDOWN_TIME="${COOLDOWN_TIME:-30}"
WARMUP_DURATION=60

# Telemetry directories partitioned hierarchically by scenario and persistence strategy
K6_RESULTS_DIR="$ROOT_DIR/data-analysis/raw-data/$SCENARIO/$TARGET/k6"
JFR_RESULTS_DIR="$ROOT_DIR/data-analysis/raw-data/$SCENARIO/$TARGET/jfr"

# Validate that the backend application is running and accessible before load testing
echo "Validating lab state for target [$TARGET] under scenario [$SCENARIO]..."

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

# Surgical purge: reset only the targeted scenario/strategy raw directory
echo "  - Resetting raw telemetry storage for [$SCENARIO | $TARGET]..."
rm -rf "$K6_RESULTS_DIR" "$JFR_RESULTS_DIR"
mkdir -p "$K6_RESULTS_DIR" "$JFR_RESULTS_DIR"

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Benchmark battery initialized | Target: $TARGET | Scenario: $SCENARIO" >> "$LOG_FILE"

# JIT warm-up phase primes HotSpot C2 compiler optimizations, class loading,
# and HikariCP connection pool acquisition without recording benchmark metrics
echo ""
echo "Executing JVM warm-up phase (60s)..."
echo "  - Priming JIT C2 compiler and HikariCP connection pool..."
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Warm-up phase started | Target: $TARGET | Scenario: $SCENARIO" >> "$LOG_FILE"

WARMUP=true k6 run "$K6_SCRIPT" >> "$LOG_FILE" 2>&1 &
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

# Execute repeated benchmark iterations for statistical significance
echo ""
echo "Starting benchmark battery [$TARGET | $SCENARIO] | Runs: $TOTAL_RUNS"

for i in $(seq 1 "$TOTAL_RUNS"); do
    RUN_NUM=$(printf "%02d" "$i")
    CSV_FILE="$K6_RESULTS_DIR/run_${RUN_NUM}.csv"
    JFR_FILE="$JFR_RESULTS_DIR/run_${RUN_NUM}.jfr"

    echo ""
    echo "[Run $RUN_NUM/$TOTAL_RUNS] Recording telemetry..."
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Run $RUN_NUM/$TOTAL_RUNS | Target: $TARGET | Scenario: $SCENARIO" >> "$LOG_FILE"

    # Start low-overhead JVM profiling via JDK Flight Recorder
    jcmd "$BACKEND_PID" JFR.start name="run_${RUN_NUM}" settings=profile filename="$JFR_FILE" >> "$LOG_FILE" 2>&1
    echo "  - JFR profiling started -> data-analysis/raw-data/$SCENARIO/$TARGET/jfr/run_${RUN_NUM}.jfr"

    # Inject load using k6 and stream latency samples to CSV
    SCENARIO="$SCENARIO" k6 run --out "csv=$CSV_FILE" "$K6_SCRIPT" >> "$LOG_FILE" 2>&1 &
    K6_PID=$!

    for ((sec=TEST_DURATION; sec>0; sec--)); do
        if ! kill -0 "$K6_PID" 2>/dev/null; then
            break
        fi
        printf "\r  - Injecting load ($SCENARIO): %2ds remaining..." "$sec"
        sleep 1
    done
    wait "$K6_PID"
    printf "\r  - Load test completed -> data-analysis/raw-data/$SCENARIO/$TARGET/k6/run_${RUN_NUM}.csv\n"

    # Stop JFR recording and flush memory buffers to disk
    jcmd "$BACKEND_PID" JFR.stop name="run_${RUN_NUM}" >> "$LOG_FILE" 2>&1
    echo "  - JFR profiling stopped and flushed"

    # Inter-run cooldown allows GC reclamation and thermal hardware stabilization
    if [[ "$i" -lt "$TOTAL_RUNS" ]]; then
        for ((sec=COOLDOWN_TIME; sec>0; sec--)); do
            printf "\r  - Cooldown: %2ds remaining (GC & thermal settling)..." "$sec"
            sleep 1
        done
        printf "\r  - Cooldown completed.                                        \n"
    fi
done

echo ""
echo "Battery completed successfully for [$TARGET] under [$SCENARIO]."
echo "  - k6 Latency CSVs : $K6_RESULTS_DIR/"
echo "  - JFR Recordings  : $JFR_RESULTS_DIR/"
echo "  - Full Execution Log: $LOG_FILE"
