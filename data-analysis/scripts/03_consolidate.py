#!/usr/bin/env python3
"""
03_consolidate.py - Merge k6 and JFR metrics into a single unified dataset.
"""

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "processed-data"
FINAL_FILE = PROCESSED_DIR / "dataset_final.csv"

STRATEGIES = ["hibernate", "hibernate-dto", "jdbc"]


def main():
    consolidated_frames = []

    for strategy in STRATEGIES:
        strat_dir = PROCESSED_DIR / strategy
        k6_file = strat_dir / "k6_metrics.csv"
        jfr_file = strat_dir / "jfr_metrics.csv"

        if not k6_file.exists() or not jfr_file.exists():
            print(f"[-] Missing processed files for '{strategy}' (skipping)")
            continue

        k6_df = pd.read_csv(k6_file)
        jfr_df = pd.read_csv(jfr_file)

        # Merge side-by-side using 'run' as key
        merged = pd.merge(k6_df, jfr_df, on="run", how="inner")
        merged.insert(0, "strategy", strategy)
        consolidated_frames.append(merged)
        print(f"[+] Consolidated {len(merged)} runs for '{strategy}'")

    if not consolidated_frames:
        print("[!] No data available to consolidate. Run parse scripts first.")
        return

    final_df = pd.concat(consolidated_frames, ignore_index=True)
    final_df.to_csv(FINAL_FILE, index=False)

    print(f"\n==> Consolidated dataset ready: {FINAL_FILE.relative_to(BASE_DIR)}")
    print(f"  - Total records: {len(final_df)} rows")
    print("\nPreview:")
    print(final_df[["strategy", "run", "throughput_rps", "latency_p95_ms", "gc_total_pause_ms", "cpu_jvm_avg_pct"]].to_string(index=False))


if __name__ == "__main__":
    main()
