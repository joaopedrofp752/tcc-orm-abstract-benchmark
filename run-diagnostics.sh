#!/usr/bin/env bash
# Enforce strict execution mode: exit on error (-e), undefined vars (-u), or pipeline failures (-o pipefail)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INITIAL_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
OUT_BASE="$ROOT_DIR/data-analysis/raw-data/diagnostics"
K6_SCRIPT="$ROOT_DIR/load-tests/k6-benchmark.js"
PID_FILE="$ROOT_DIR/.backend.pid"
LOG_FILE="$ROOT_DIR/diagnostics.log"

# Experimental execution parameters:
# - 10 interleaved rounds neutralize sequence and cumulative thermal effects
# - 30s warm-up primes HotSpot C2 JIT compilation before telemetry capture
# - 90s saturation window (1,200 RPS) stresses the 10-connection HikariCP pool
TOTAL_ROUNDS="${TOTAL_ROUNDS:-10}"
WARMUP_DURATION=30
TEST_DURATION=90
COOLDOWN_TIME="${COOLDOWN_TIME:-15}"

# Balanced Latin-square-inspired strategy permutations across rounds
# to eliminate order bias and residual thermal throttling between variants
ROUND_ORDERS=(
    "hibernate hibernate-dto jdbc"
    "hibernate-dto jdbc hibernate"
    "jdbc hibernate hibernate-dto"
    "hibernate jdbc hibernate-dto"
    "hibernate-dto hibernate jdbc"
    "jdbc hibernate-dto hibernate"
    "hibernate hibernate-dto jdbc"
    "hibernate-dto jdbc hibernate"
    "jdbc hibernate hibernate-dto"
    "hibernate jdbc hibernate-dto"
)

# Universal exit trap: ensure clean environment teardown and Git branch restoration on any abnormal exit
cleanup_on_exit() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        echo ""
        echo "  ! Abnormal termination detected (exit code $exit_code)."
        echo "  ! Cleaning up lab environment and restoring branch [$INITIAL_BRANCH]..."
        "$ROOT_DIR/down-lab.sh" > /dev/null 2>&1 || true
        git switch "$INITIAL_BRANCH" > /dev/null 2>&1 || true
        echo "  ! Environment safely restored to branch [$INITIAL_BRANCH]."
    fi
}
trap cleanup_on_exit EXIT

echo "Diagnostic benchmark orchestrator initialized"
echo "Workload profile: saturation (1,200 RPS) | Interleaved rounds: $TOTAL_ROUNDS"

# Abort if tracked files have uncommitted modifications to prevent branch checkout conflicts
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "  ! Error: Tracked files have uncommitted changes." >&2
    echo "  ! Hint: Commit or stash changes before running diagnostics." >&2
    exit 1
fi

# Validate presence of all required CLI utilities for load injection, JVM profiling, and telemetry parsing
for cmd in k6 jcmd docker curl python3; do
    if ! command -v "$cmd" > /dev/null 2>&1; then
        echo "  ! Error: Required command '$cmd' is not installed or not in PATH." >&2
        exit 1
    fi
done

# Reset diagnostic raw storage while preserving primary nominal/saturation datasets
echo "  - Resetting raw telemetry storage for [diagnostics]..."
rm -rf "$OUT_BASE"
mkdir -p "$OUT_BASE"

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Diagnostic battery initialized | Rounds: $TOTAL_ROUNDS" >> "$LOG_FILE"
START_EPOCH=$(date +%s)

for round in $(seq 1 "$TOTAL_ROUNDS"); do
    RUN_NUM=$(printf "%02d" "$round")
    STRATEGY_SEQ="${ROUND_ORDERS[$(( (round - 1) % ${#ROUND_ORDERS[@]} ))]}"

    echo ""
    echo "Starting diagnostic round [$round/$TOTAL_ROUNDS] | Order: $STRATEGY_SEQ"

    for strategy in $STRATEGY_SEQ; do
        # Partition output directories by strategy and telemetry source (k6, JFR, Actuator/cgroup JSON)
        STRAT_DIR="$OUT_BASE/$strategy"
        mkdir -p "$STRAT_DIR/k6" "$STRAT_DIR/jfr" "$STRAT_DIR/telemetry"

        echo ""
        echo "  [Round $RUN_NUM | $strategy] Provisioning environment..."
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] Round $RUN_NUM/$TOTAL_ROUNDS | Strategy: $strategy" >> "$LOG_FILE"

        # Checkout target persistence branch and spin up clean PostgreSQL + JVM instances
        git switch "$strategy" > /dev/null 2>&1
        if ! "$ROOT_DIR/up-lab.sh" >> "$LOG_FILE" 2>&1; then
            echo "  ! Error: Failed to initialize lab for [$strategy]. Check diagnostics.log." >&2
            exit 1
        fi
        BACKEND_PID=$(cat "$PID_FILE")
        echo "  - Lab ready (JVM PID $BACKEND_PID)"

        # Execute warm-up phase to trigger HotSpot C2 compilation and populate HikariCP connections
        WARMUP=true k6 run "$K6_SCRIPT" >> "$LOG_FILE" 2>&1 &
        WARMUP_PID=$!
        for ((sec=WARMUP_DURATION; sec>0; sec--)); do
            if ! kill -0 "$WARMUP_PID" 2>/dev/null; then
                break
            fi
            printf "\r  - JIT warm-up progress: %2ds remaining..." "$sec"
            sleep 1
        done
        wait "$WARMUP_PID" 2>/dev/null || true
        printf "\r  - JIT warm-up completed. Settling GC for 5s...              \n"
        sleep 5

        # Capture pre-test baseline snapshots (t0) for cumulative counter and timer deltas:
        # 1. HikariCP connection usage, acquisition wait times, and timeout counters via Spring Actuator
        HIKARI_USAGE_T0=$(curl -s http://localhost:8080/actuator/metrics/hikaricp.connections.usage || echo "{}")
        HIKARI_ACQ_T0=$(curl -s http://localhost:8080/actuator/metrics/hikaricp.connections.acquire || echo "{}")
        HIKARI_TO_T0=$(curl -s http://localhost:8080/actuator/metrics/hikaricp.connections.timeout || echo "{}")

        # 2. PostgreSQL container cgroup v2 CPU accounting (usage_usec and throttling counters)
        PG_CPU_T0=$(docker exec tcc_postgres cat /sys/fs/cgroup/cpu.stat)

        # 3. PostgreSQL shared buffer cache hit/read block counters for benchmark_payload
        PG_IO_T0=$(docker exec tcc_postgres psql -U postgres -d tcc_benchmark -t -A -c "SELECT COALESCE(heap_blks_read,0), COALESCE(heap_blks_hit,0), COALESCE(idx_blks_read,0), COALESCE(idx_blks_hit,0) FROM pg_statio_user_tables WHERE relname='benchmark_payload';")

        # 4. Process-level user + kernel CPU jiffies (/proc/<pid>/stat fields 14 and 15) and wall-clock timestamp
        JVM_TICKS_T0=$(awk '{print $14+$15}' "/proc/$BACKEND_PID/stat")
        WALL_T0=$(date +%s%N)

        JFR_FILE="$STRAT_DIR/jfr/run_${RUN_NUM}.jfr"
        CSV_FILE="$STRAT_DIR/k6/run_${RUN_NUM}.csv"

        # Start low-overhead JDK Flight Recorder profiling for GC and heap telemetry
        jcmd "$BACKEND_PID" JFR.start name="diag_${RUN_NUM}" settings=profile filename="$JFR_FILE" >> "$LOG_FILE" 2>&1

        # Launch k6 under open-model saturation (1,200 RPS) and capture initial load generator CPU ticks
        SCENARIO="saturation" k6 run --out "csv=$CSV_FILE" "$K6_SCRIPT" >> "$LOG_FILE" 2>&1 &
        K6_PID=$!
        sleep 0.2
        K6_TICKS_T0=$(awk '{print $14+$15}' "/proc/$K6_PID/stat" 2>/dev/null || echo 0)
        K6_TICKS_LAST="$K6_TICKS_T0"

        PENDING_SAMPLES=""
        ACTIVE_SAMPLES=""

        # Sample instantaneous HikariCP queue depth (pending/active gauges) and k6 CPU ticks at 1 Hz
        for ((sec=TEST_DURATION; sec>0; sec--)); do
            if ! kill -0 "$K6_PID" 2>/dev/null; then
                break
            fi

            # Continuously cache the latest k6 /proc ticks before the process exits and disappears from /proc
            K6_NOW=$(awk '{print $14+$15}' "/proc/$K6_PID/stat" 2>/dev/null || echo "")
            [[ -n "$K6_NOW" ]] && K6_TICKS_LAST="$K6_NOW"

            # Query current waiting threads and leased connections from Micrometer/Actuator gauges
            P_VAL=$(curl -s http://localhost:8080/actuator/metrics/hikaricp.connections.pending | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['measurements'][0]['value'])" 2>/dev/null || echo 0)
            A_VAL=$(curl -s http://localhost:8080/actuator/metrics/hikaricp.connections.active | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['measurements'][0]['value'])" 2>/dev/null || echo 0)
            PENDING_SAMPLES="${PENDING_SAMPLES}${P_VAL},"
            ACTIVE_SAMPLES="${ACTIVE_SAMPLES}${A_VAL},"

            printf "\r  - Injecting saturation load & polling telemetry: %2ds remaining..." "$sec"
            sleep 1
        done
        wait "$K6_PID" 2>/dev/null || true
        printf "\r  - Saturation load and telemetry capture completed.                \n"

        # Capture post-test terminal snapshots (t1) immediately after traffic stops
        WALL_T1=$(date +%s%N)
        JVM_TICKS_T1=$(awk '{print $14+$15}' "/proc/$BACKEND_PID/stat")
        HIKARI_USAGE_T1=$(curl -s http://localhost:8080/actuator/metrics/hikaricp.connections.usage || echo "{}")
        HIKARI_ACQ_T1=$(curl -s http://localhost:8080/actuator/metrics/hikaricp.connections.acquire || echo "{}")
        HIKARI_TO_T1=$(curl -s http://localhost:8080/actuator/metrics/hikaricp.connections.timeout || echo "{}")
        PG_CPU_T1=$(docker exec tcc_postgres cat /sys/fs/cgroup/cpu.stat)
        PG_IO_T1=$(docker exec tcc_postgres psql -U postgres -d tcc_benchmark -t -A -c "SELECT COALESCE(heap_blks_read,0), COALESCE(heap_blks_hit,0), COALESCE(idx_blks_read,0), COALESCE(idx_blks_hit,0) FROM pg_statio_user_tables WHERE relname='benchmark_payload';")

        # Flush JFR binary recording buffers to disk
        jcmd "$BACKEND_PID" JFR.stop name="diag_${RUN_NUM}" >> "$LOG_FILE" 2>&1

        # Compute interval deltas across t0 -> t1 and serialize structured telemetry to JSON
        ROUND="$round" STRATEGY="$strategy" \
        WALL_T0="$WALL_T0" WALL_T1="$WALL_T1" \
        JVM_TICKS_T0="$JVM_TICKS_T0" JVM_TICKS_T1="$JVM_TICKS_T1" \
        K6_TICKS_T0="$K6_TICKS_T0" K6_TICKS_LAST="$K6_TICKS_LAST" \
        HIKARI_USAGE_T0="$HIKARI_USAGE_T0" HIKARI_USAGE_T1="$HIKARI_USAGE_T1" \
        HIKARI_ACQ_T0="$HIKARI_ACQ_T0" HIKARI_ACQ_T1="$HIKARI_ACQ_T1" \
        HIKARI_TO_T0="$HIKARI_TO_T0" HIKARI_TO_T1="$HIKARI_TO_T1" \
        PG_CPU_T0="$PG_CPU_T0" PG_CPU_T1="$PG_CPU_T1" \
        PG_IO_T0="$PG_IO_T0" PG_IO_T1="$PG_IO_T1" \
        PENDING_SAMPLES="$PENDING_SAMPLES" ACTIVE_SAMPLES="$ACTIVE_SAMPLES" \
        python3 - << 'PYEOF' > "$STRAT_DIR/telemetry/run_${RUN_NUM}.json"
import json
import os


def parse_timer(raw: str) -> tuple[float, float, float]:
    """Extract COUNT, TOTAL_TIME (seconds), and MAX (seconds) from a Micrometer Timer JSON payload."""
    try:
        data = json.loads(raw)
        meas = {x["statistic"]: float(x["value"]) for x in data.get("measurements", [])}
        return meas.get("COUNT", 0.0), meas.get("TOTAL_TIME", 0.0), meas.get("MAX", 0.0)
    except Exception:
        return 0.0, 0.0, 0.0


def parse_counter(raw: str) -> float:
    """Extract scalar value from a Micrometer Counter or Gauge JSON payload."""
    try:
        data = json.loads(raw)
        return float(data.get("measurements", [{"value": 0.0}])[0]["value"])
    except Exception:
        return 0.0


def parse_cgroup_stat(raw: str) -> dict[str, int]:
    """Parse Linux cgroup v2 cpu.stat key-value lines into an integer dictionary."""
    out = {}
    for line in raw.strip().splitlines():
        parts = line.split()
        if len(parts) == 2:
            out[parts[0]] = int(parts[1])
    return out


# Parse HikariCP timer and timeout deltas between t0 and t1
u_c0, u_t0, _ = parse_timer(os.environ.get("HIKARI_USAGE_T0", "{}"))
u_c1, u_t1, u_max = parse_timer(os.environ.get("HIKARI_USAGE_T1", "{}"))
a_c0, a_t0, _ = parse_timer(os.environ.get("HIKARI_ACQ_T0", "{}"))
a_c1, a_t1, a_max = parse_timer(os.environ.get("HIKARI_ACQ_T1", "{}"))
to0 = parse_counter(os.environ.get("HIKARI_TO_T0", "{}"))
to1 = parse_counter(os.environ.get("HIKARI_TO_T1", "{}"))

# Parse PostgreSQL cgroup v2 CPU usage and CFS bandwidth throttling counters
pg0 = parse_cgroup_stat(os.environ.get("PG_CPU_T0", ""))
pg1 = parse_cgroup_stat(os.environ.get("PG_CPU_T1", ""))

# Normalize elapsed wall-clock duration and Linux kernel clock ticks (USER_HZ)
wall_sec = max((int(os.environ["WALL_T1"]) - int(os.environ["WALL_T0"])) / 1e9, 0.001)
wall_usec = max((int(os.environ["WALL_T1"]) - int(os.environ["WALL_T0"])) / 1e3, 1.0)
clk_tck = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
host_cpus = os.cpu_count() or 4

# Compute isolated CPU utilization for JVM backend and k6 load generator
# (expressed both as percentage of a single core and normalized to total host capacity)
jvm_core_pct = ((int(os.environ["JVM_TICKS_T1"]) - int(os.environ["JVM_TICKS_T0"])) / clk_tck) / wall_sec * 100.0
k6_core_pct = ((int(os.environ["K6_TICKS_LAST"]) - int(os.environ["K6_TICKS_T0"])) / clk_tck) / wall_sec * 100.0

# Compute PostgreSQL effective cores consumed and percentage of its 2.0-core Docker quota
pg_cores_used = (pg1.get("usage_usec", 0) - pg0.get("usage_usec", 0)) / wall_usec
pg_throttled_pct = (pg1.get("throttled_usec", 0) - pg0.get("throttled_usec", 0)) / wall_usec * 100.0

# Compute PostgreSQL shared buffer cache hit ratio across heap and index blocks
io0 = [int(x) for x in os.environ.get("PG_IO_T0", "").split("|") if x.strip()] or [0, 0, 0, 0]
io1 = [int(x) for x in os.environ.get("PG_IO_T1", "").split("|") if x.strip()] or [0, 0, 0, 0]
d_read = (io1[0] - io0[0]) + (io1[2] - io0[2])
d_hit = (io1[1] - io0[1]) + (io1[3] - io0[3])
cache_hit_pct = (d_hit / (d_hit + d_read) * 100.0) if (d_hit + d_read) > 0 else 100.0

# Aggregate 1 Hz instantaneous HikariCP queue depth samples
pend = [float(x) for x in os.environ.get("PENDING_SAMPLES", "").split(",") if x.strip()]
act = [float(x) for x in os.environ.get("ACTIVE_SAMPLES", "").split(",") if x.strip()]

u_cnt = max(u_c1 - u_c0, 1.0)
a_cnt = max(a_c1 - a_c0, 1.0)

result = {
    "round": int(os.environ["ROUND"]),
    "strategy": os.environ["STRATEGY"],
    "hikari_usage_mean_ms": round(((u_t1 - u_t0) / u_cnt) * 1000.0, 3),
    "hikari_usage_max_ms": round(u_max * 1000.0, 3),
    "hikari_acquire_mean_ms": round(((a_t1 - a_t0) / a_cnt) * 1000.0, 3),
    "hikari_acquire_max_ms": round(a_max * 1000.0, 3),
    "hikari_pending_mean": round(sum(pend) / len(pend), 2) if pend else 0.0,
    "hikari_pending_max": max(pend) if pend else 0.0,
    "hikari_active_mean": round(sum(act) / len(act), 2) if act else 0.0,
    "hikari_timeouts": int(to1 - to0),
    "pg_cores_used": round(pg_cores_used, 3),
    "pg_cpu_limit_pct": round((pg_cores_used / 2.0) * 100.0, 2),
    "pg_nr_throttled": pg1.get("nr_throttled", 0) - pg0.get("nr_throttled", 0),
    "pg_throttled_time_pct": round(pg_throttled_pct, 2),
    "pg_cache_hit_pct": round(cache_hit_pct, 4),
    "jvm_cpu_one_core_pct": round(jvm_core_pct, 2),
    "jvm_cpu_host_pct": round(jvm_core_pct / host_cpus, 2),
    "k6_cpu_one_core_pct": round(k6_core_pct, 2),
    "k6_cpu_host_pct": round(k6_core_pct / host_cpus, 2),
}
print(json.dumps(result, indent=2))
PYEOF

        # Tear down JVM and destroy PostgreSQL container/volumes to ensure clean state for next strategy
        "$ROOT_DIR/down-lab.sh" >> "$LOG_FILE" 2>&1
        echo "  - Telemetry saved -> data-analysis/raw-data/diagnostics/$strategy/telemetry/run_${RUN_NUM}.json"

        # Thermal settling pause between persistence variants
        for ((sec=COOLDOWN_TIME; sec>0; sec--)); do
            printf "\r  - Inter-strategy cooldown: %2ds remaining..." "$sec"
            sleep 1
        done
        printf "\r  - Cooldown completed.                                        \n"
    done
done

# Restore repository to the original Git branch active prior to execution
echo ""
echo "Restoring initial branch [$INITIAL_BRANCH]..."
git switch "$INITIAL_BRANCH" > /dev/null 2>&1

ELAPSED_MIN=$(( ($(date +%s) - START_EPOCH) / 60 ))
echo ""
echo "Diagnostic battery completed successfully in ${ELAPSED_MIN} minutes."
echo "  - Telemetry Output : data-analysis/raw-data/diagnostics/"
echo "  - Execution Log    : diagnostics.log"
