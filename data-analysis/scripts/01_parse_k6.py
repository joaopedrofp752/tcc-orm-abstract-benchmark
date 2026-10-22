#!/usr/bin/env python3
"""
01_parse_k6.py - Extract latency percentiles and throughput from raw k6 CSVs.
"""

from pathlib import Path
import pandas as pd

# Path configuration
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "raw-data"
PROCESSED_DIR = BASE_DIR / "processed-data"

STRATEGIES = ["hibernate", "hibernate-dto", "jdbc"]


def process_strategy_k6(strategy: str) -> None:
    k6_dir = RAW_DIR / strategy / "k6"
    if not k6_dir.exists():
        print(f"[-] Directory not found: {k6_dir} (skipping)")
        return

    csv_files = sorted(k6_dir.glob("run_*.csv"))
    if not csv_files:
        print(f"[-] No k6 CSV files found for strategy: {strategy} (skipping)")
        return

    print(f"[+] Processing {len(csv_files)} k6 runs for '{strategy}'...")
    records = []

    for file_path in csv_files:
        run_id = file_path.stem  # e.g., 'run_01'

        # Only read necessary columns to conserve memory
        usecols = ["metric_name", "metric_value", "timestamp"]
        try:
            df = pd.read_csv(file_path, usecols=usecols)
        except Exception as e:
            print(f"  ! Error reading {file_path.name}: {e}")
            continue

        # Filter latency metrics (http_req_duration in milliseconds)
        latencies = df.loc[df["metric_name"] == "http_req_duration", "metric_value"]

        # Filter total requests count and calculate total test duration
        req_rows = df.loc[df["metric_name"] == "http_reqs"]
        total_reqs = len(latencies)

        if total_reqs == 0:
            print(f"  ! Warning: No http_req_duration samples in {file_path.name}")
            continue

        # Effective duration in seconds based on timestamps
        timestamps = df["timestamp"]
        duration_sec = max(timestamps.max() - timestamps.min(), 1.0)
        throughput_rps = total_reqs / duration_sec

        records.append({
            "run": run_id,
            "http_reqs_total": int(total_reqs),
            "throughput_rps": round(throughput_rps, 2),
            "latency_avg_ms": round(latencies.mean(), 2),
            "latency_min_ms": round(latencies.min(), 2),
            "latency_p50_ms": round(latencies.quantile(0.50), 2),
            "latency_p90_ms": round(latencies.quantile(0.90), 2),
            "latency_p95_ms": round(latencies.quantile(0.95), 2),
            "latency_p99_ms": round(latencies.quantile(0.99), 2),
            "latency_max_ms": round(latencies.max(), 2),
        })

    if records:
        out_dir = PROCESSED_DIR / strategy
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "k6_metrics.csv"

        result_df = pd.DataFrame(records)
        result_df.to_csv(out_file, index=False)
        print(f"  -> Saved k6 metrics to: {out_file.relative_to(BASE_DIR)}")


def main():
    for strategy in STRATEGIES:
        process_strategy_k6(strategy)


if __name__ == "__main__":
    main()
