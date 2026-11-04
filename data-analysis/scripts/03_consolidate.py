#!/usr/bin/env python3
"""
03_consolidate.py - Merge k6 and JFR metrics across all scenarios and strategies
into a single unified tidy dataset (dataset_final.csv).

Data Modeling & Tidy Data Notes:
- Conforms to Hadley Wickham's 'Tidy Data' principles:
  1. Each variable forms a column (e.g., latency_p95_ms, throughput_rps, gc_total_pause_ms).
  2. Each observation forms a row (a distinct benchmark execution run).
  3. Each type of observational unit forms a table.
- Performs a deterministic inner join on the execution run key ('run') to guarantee
  that network-level measurements (k6) are paired precisely with their corresponding
  internal JVM telemetry (JFR).
- Injects categorical experimental factors ('scenario' and 'strategy') as primary keys
  for grouped statistical inference (Shapiro-Wilk, Mann-Whitney U, Wilcoxon).
"""

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "processed-data"
FINAL_FILE = PROCESSED_DIR / "dataset_final.csv"

SCENARIOS = ["nominal", "saturation"]
STRATEGIES = ["hibernate", "hibernate-dto", "jdbc"]


def main():
    consolidated_frames = []

    # Traverse all scenario and strategy intersections
    for scenario in SCENARIOS:
        for strategy in STRATEGIES:
            strat_dir = PROCESSED_DIR / scenario / strategy
            k6_file = strat_dir / "k6_metrics.csv"
            jfr_file = strat_dir / "jfr_metrics.csv"

            if not k6_file.exists() or not jfr_file.exists():
                continue

            k6_df = pd.read_csv(k6_file)
            jfr_df = pd.read_csv(jfr_file)

            # Perform deterministic inner join on the iteration key ('run')
            merged = pd.merge(k6_df, jfr_df, on="run", how="inner")

            # Inject categorical experimental factors for statistical grouping
            merged.insert(0, "strategy", strategy)
            merged.insert(0, "scenario", scenario)

            consolidated_frames.append(merged)
            print(f"[+] Consolidated {len(merged)} runs for [{scenario} | {strategy}]")

    if not consolidated_frames:
        print("[!] No data available to consolidate. Execute 01_parse_k6 and 02_parse_jfr first.")
        return

    # Concatenate all experimental cells into a unified tidy dataset
    final_df = pd.concat(consolidated_frames, ignore_index=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(FINAL_FILE, index=False)

    print(f"\n==> Consolidated dataset ready: {FINAL_FILE.relative_to(BASE_DIR)}")
    print(f"  - Total records: {len(final_df)} rows")
    print("\nPreview:")
    preview_cols = [
        "scenario", "strategy", "run", "throughput_rps",
        "latency_p95_ms", "gc_total_pause_ms", "cpu_jvm_avg_pct"
    ]
    print(final_df[preview_cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
