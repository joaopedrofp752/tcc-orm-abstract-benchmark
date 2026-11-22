#!/usr/bin/env python3
"""
01_parse_k6.py - Extract latency percentiles, sustained throughput, dropped iterations,
and HTTP failure counts from raw k6 CSV logs across 'nominal' (300 RPS),
'saturation' (1,200 RPS), and 'diagnostics' (1,200 RPS interleaved) profiles.

Architecture & Telemetry Notes:
- Reads high-volume CSV logs produced by k6 load test executions.
- Isolates end-to-end client-perceived duration (http_req_duration), covering
  TCP socket acquisition, HTTP processing, database query, and response transfer.
- Computes non-parametric percentiles (p50, p90, p95, p99) to accurately evaluate
  tail latencies under queuing contention, where arithmetic means mask degradation.
- Tracks open-model arrival-rate drops (dropped_iterations) and HTTP error counts
  (http_req_failed) to verify zero-error saturation behavior under VU pool limits.
"""

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "raw-data"
PROCESSED_DIR = BASE_DIR / "processed-data"

SCENARIOS = ["nominal", "saturation", "diagnostics"]
STRATEGIES = ["hibernate", "hibernate-dto", "jdbc"]


def process_k6_run(file_path: Path) -> dict | None:
    """
    Parse an individual k6 execution CSV log, extracting request timing samples
    and aggregating primary performance indicators.

    Memory Optimization:
    - Only reads 'metric_name', 'metric_value', and 'timestamp' via `usecols`
      to prevent parsing overhead on multi-hundred-megabyte CSV files.
    """
    run_id = file_path.stem
    usecols = ["metric_name", "metric_value", "timestamp"]

    try:
        df = pd.read_csv(file_path, usecols=usecols)
    except Exception as e:
        print(f"  ! Error reading {file_path.name}: {e}")
        return None

    # Filter strictly for end-to-end HTTP request duration samples (in milliseconds).
    # In k6, http_req_duration represents the total round-trip time:
    # http_req_sending + http_req_waiting (TTFB) + http_req_receiving.
    latencies = df.loc[df["metric_name"] == "http_req_duration", "metric_value"]
    total_reqs = len(latencies)

    if total_reqs == 0:
        print(f"  ! Warning: No http_req_duration samples in {file_path.name}")
        return None

    # Aggregate open-model dropped iterations (when all maxVUs are saturated)
    # and failed HTTP responses (non-2xx status codes or client timeouts).
    dropped_iterations = int(df.loc[df["metric_name"] == "dropped_iterations", "metric_value"].sum())
    http_req_failed = int(df.loc[df["metric_name"] == "http_req_failed", "metric_value"].sum())

    # Derive sustained throughput (RPS) based on the boundary timestamps of the run.
    # A 1.0-second clamp avoids division by zero in degraded or truncated runs.
    timestamps = df["timestamp"]
    duration_sec = max(timestamps.max() - timestamps.min(), 1.0)
    throughput_rps = total_reqs / duration_sec

    # Return key statistical indicators for performance evaluation:
    # - p50 (Median): Typical user experience unaffected by outliers.
    # - p90/p95/p99: Tail latencies capturing connection pool contention in HikariCP.
    return {
        "run": run_id,
        "http_reqs_total": int(total_reqs),
        "dropped_iterations": dropped_iterations,
        "http_req_failed": http_req_failed,
        "throughput_rps": round(throughput_rps, 2),
        "latency_avg_ms": round(latencies.mean(), 2),
        "latency_min_ms": round(latencies.min(), 2),
        "latency_p50_ms": round(latencies.quantile(0.50), 2),
        "latency_p90_ms": round(latencies.quantile(0.90), 2),
        "latency_p95_ms": round(latencies.quantile(0.95), 2),
        "latency_p99_ms": round(latencies.quantile(0.99), 2),
        "latency_max_ms": round(latencies.max(), 2),
    }


def process_scenario_strategy(scenario: str, strategy: str) -> None:
    """
    Process all k6 execution CSVs for a specific scenario and persistence strategy,
    persisting summary metrics into an intermediate CSV dataset.
    """
    k6_dir = RAW_DIR / scenario / strategy / "k6"
    if not k6_dir.exists():
        return

    csv_files = sorted(k6_dir.glob("run_*.csv"))
    if not csv_files:
        return

    print(f"[+] Processing {len(csv_files)} k6 runs for [{scenario} | {strategy}]...")
    records = []

    for file_path in csv_files:
        metric = process_k6_run(file_path)
        if metric:
            records.append(metric)

    if records:
        out_dir = PROCESSED_DIR / scenario / strategy
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "k6_metrics.csv"

        result_df = pd.DataFrame(records)
        result_df.to_csv(out_file, index=False)
        print(f"  -> Saved k6 metrics to: {out_file.relative_to(BASE_DIR)}")


def main():
    """Iterate through all experimental permutations and generate intermediate metrics."""
    for scenario in SCENARIOS:
        for strategy in STRATEGIES:
            process_scenario_strategy(scenario, strategy)


if __name__ == "__main__":
    main()
