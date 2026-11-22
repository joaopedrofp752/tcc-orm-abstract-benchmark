#!/usr/bin/env python3
"""
03_consolidate.py - Merge k6, JFR, and diagnostic telemetry across scenarios and
strategies into unified tidy datasets:
- processed-data/dataset_final.csv (60 primary clean runs: nominal & saturation)
- processed-data/diagnostics_dataset.csv (30 interleaved saturation diagnostic runs)

Data Modeling & Tidy Data Notes:
- Conforms to Hadley Wickham's 'Tidy Data' principles:
  1. Each variable forms a column (e.g., latency_p95_ms, throughput_rps, hikari_usage_mean_ms).
  2. Each observation forms a row (a distinct benchmark execution run).
  3. Each type of observational unit forms a table, keeping primary macro-benchmarks
     decoupled from active Actuator-polled diagnostic runs to prevent observer bias.
- Performs deterministic inner joins on the execution run key ('run') to guarantee
  that network-level measurements (k6) are paired precisely with internal JVM (JFR)
  and connection pool / cgroup telemetry.
"""

import json
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "raw-data"
PROCESSED_DIR = BASE_DIR / "processed-data"
FINAL_FILE = PROCESSED_DIR / "dataset_final.csv"
DIAG_FILE = PROCESSED_DIR / "diagnostics_dataset.csv"

PRIMARY_SCENARIOS = ["nominal", "saturation"]
STRATEGIES = ["hibernate", "hibernate-dto", "jdbc"]


def load_telemetry_df(scenario: str, strategy: str) -> pd.DataFrame:
    """
    Load per-run JSON telemetry snapshots (HikariCP timers/gauges, PostgreSQL cgroup v2
    CPU accounting, buffer cache hit rates, and isolated process CPU utilization).
    """
    tel_dir = RAW_DIR / scenario / strategy / "telemetry"
    if not tel_dir.exists():
        return pd.DataFrame()

    records = []
    for json_file in sorted(tel_dir.glob("run_*.json")):
        with open(json_file, encoding="utf-8") as fp:
            data = json.load(fp)
        data["run"] = json_file.stem
        # Drop duplicate strategy key prior to inner join on 'run'
        data.pop("strategy", None)
        records.append(data)

    return pd.DataFrame(records)


def consolidate_primary_dataset() -> None:
    """
    Join k6 and JFR intermediate CSVs for the primary clean experiments
    (nominal 300 RPS and saturation 1,200 RPS) into dataset_final.csv.
    """
    consolidated_frames = []

    for scenario in PRIMARY_SCENARIOS:
        for strategy in STRATEGIES:
            strat_dir = PROCESSED_DIR / scenario / strategy
            k6_file = strat_dir / "k6_metrics.csv"
            jfr_file = strat_dir / "jfr_metrics.csv"

            if not k6_file.exists() or not jfr_file.exists():
                continue

            k6_df = pd.read_csv(k6_file)
            jfr_df = pd.read_csv(jfr_file)

            # Deterministic inner join on iteration identifier ('run')
            merged = pd.merge(k6_df, jfr_df, on="run", how="inner")

            # Inject categorical experimental factors for statistical grouping
            merged.insert(0, "strategy", strategy)
            merged.insert(0, "scenario", scenario)

            consolidated_frames.append(merged)
            print(f"[+] Consolidated {len(merged)} primary runs for [{scenario} | {strategy}]")

    if not consolidated_frames:
        print("[!] No primary data available to consolidate. Run 01_parse_k6 and 02_parse_jfr first.")
        return

    final_df = pd.concat(consolidated_frames, ignore_index=True)
    final_df.to_csv(FINAL_FILE, index=False)

    print(f"==> Consolidated primary dataset ready: {FINAL_FILE.relative_to(BASE_DIR)} ({len(final_df)} rows)")
    preview_cols = [
        "scenario", "strategy", "run", "throughput_rps",
        "latency_p95_ms", "gc_total_pause_ms", "cpu_jvm_avg_pct"
    ]
    print(final_df[preview_cols].head(6).to_string(index=False))


def consolidate_diagnostics_dataset() -> None:
    """
    Join k6, JFR, and internal Actuator/cgroup telemetry for the interleaved
    saturation diagnostic runs into diagnostics_dataset.csv.
    """
    diag_frames = []

    for strategy in STRATEGIES:
        strat_dir = PROCESSED_DIR / "diagnostics" / strategy
        k6_file = strat_dir / "k6_metrics.csv"
        jfr_file = strat_dir / "jfr_metrics.csv"

        if not k6_file.exists() or not jfr_file.exists():
            continue

        merged = pd.merge(pd.read_csv(k6_file), pd.read_csv(jfr_file), on="run", how="inner")

        # Attach HikariCP, PostgreSQL cgroup, and isolated CPU metrics when available
        tel_df = load_telemetry_df("diagnostics", strategy)
        if not tel_df.empty:
            merged = pd.merge(merged, tel_df, on="run", how="inner")

        merged.insert(0, "strategy", strategy)
        diag_frames.append(merged)
        print(f"[+] Consolidated {len(merged)} diagnostic runs for [diagnostics | {strategy}]")

    if not diag_frames:
        print("[!] No diagnostic runs found yet (skipping diagnostics_dataset.csv).")
        return

    diag_df = pd.concat(diag_frames, ignore_index=True)
    diag_df.to_csv(DIAG_FILE, index=False)
    print(f"==> Consolidated diagnostics dataset ready: {DIAG_FILE.relative_to(BASE_DIR)} ({len(diag_df)} rows)")


def main():
    """Execute consolidation for both primary and diagnostic telemetry datasets."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    consolidate_primary_dataset()
    consolidate_diagnostics_dataset()


if __name__ == "__main__":
    main()
