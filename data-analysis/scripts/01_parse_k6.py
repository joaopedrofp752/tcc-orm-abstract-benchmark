#!/usr/bin/env python3
"""
01_parse_k6.py - Extract latency percentiles and throughput from raw k6 CSVs
supporting both 'nominal' and 'saturation' scenarios.
"""

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "raw-data"
PROCESSED_DIR = BASE_DIR / "processed-data"

SCENARIOS = ["nominal", "saturation"]
STRATEGIES = ["hibernate", "hibernate-dto", "jdbc"]


def process_k6_run(file_path: Path) -> dict:
    run_id = file_path.stem
    usecols = ["metric_name", "metric_value", "timestamp"]

    try:
        df = pd.read_csv(file_path, usecols=usecols)
    except Exception as e:
        print(f"  ! Error reading {file_path.name}: {e}")
        return None

    latencies = df.loc[df["metric_name"] == "http_req_duration", "metric_value"]
    total_reqs = len(latencies)

    if total_reqs == 0:
        print(f"  ! Warning: No http_req_duration samples in {file_path.name}")
        return None

    timestamps = df["timestamp"]
    duration_sec = max(timestamps.max() - timestamps.min(), 1.0)
    throughput_rps = total_reqs / duration_sec

    return {
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
    }


def process_scenario_strategy(scenario: str, strategy: str) -> None:
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
    for scenario in SCENARIOS:
        for strategy in STRATEGIES:
            process_scenario_strategy(scenario, strategy)


if __name__ == "__main__":
    main()
