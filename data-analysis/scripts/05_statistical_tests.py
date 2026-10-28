#!/usr/bin/env python3
"""
05_statistical_tests.py - Perform Shapiro-Wilk normality and Wilcoxon/Mann-Whitney
hypothesis tests, and render split-scale distribution boxplots for academic reporting.
"""

import sys
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from scipy import stats

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "processed-data"
FIGURES_DIR = BASE_DIR / "figures" / "comparisons"
DATASET_PATH = PROCESSED_DIR / "dataset_final.csv"

SCENARIOS = ["nominal", "saturation"]
STRATEGIES = ["hibernate", "hibernate-dto", "jdbc"]
METRICS = ["latency_p95_ms", "throughput_rps", "gc_total_pause_ms", "cpu_jvm_avg_pct"]

COMPARISONS = [
    ("hibernate", "jdbc"),
    ("hibernate", "hibernate-dto"),
    ("hibernate-dto", "jdbc"),
]

PALETTE = {"hibernate": "#4C72B0", "hibernate-dto": "#55A868", "jdbc": "#DD8452"}

# Standardized visual styling matching 04_generate_figures.py
sns.set_theme(style="whitegrid", font="sans-serif")
plt.rcParams.update({
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 11,
    "figure.titlesize": 14,
})


def run_shapiro_wilk(df: pd.DataFrame) -> pd.DataFrame:
    """
    Perform the Shapiro-Wilk test of normality across all experimental cells
    to validate whether parametric assumptions hold for each measured metric.
    """
    print("[+] Running Shapiro-Wilk normality tests (alpha = 0.05)...")
    records = []

    for scenario in SCENARIOS:
        for strategy in STRATEGIES:
            subset = df[(df["scenario"] == scenario) & (df["strategy"] == strategy)]
            if subset.empty:
                continue

            for metric in METRICS:
                stat, p_val = stats.shapiro(subset[metric])
                records.append({
                    "scenario": scenario,
                    "strategy": strategy,
                    "metric": metric,
                    "statistic_w": round(stat, 4),
                    "p_value": round(p_val, 5),
                    "is_normal": "Yes" if p_val >= 0.05 else "No",
                })

    result_df = pd.DataFrame(records)
    out_file = PROCESSED_DIR / "shapiro_wilk_results.csv"
    result_df.to_csv(out_file, index=False)
    print(f"  -> Saved Shapiro-Wilk results to: {out_file.relative_to(BASE_DIR)}")
    return result_df


def run_hypothesis_tests(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute non-parametric pairwise hypothesis tests (Mann-Whitney U for independent samples
    and Wilcoxon Signed-Rank for paired runs) to evaluate statistical significance.
    """
    print("[+] Running non-parametric hypothesis tests (Mann-Whitney U & Wilcoxon)...")
    records = []

    for scenario in SCENARIOS:
        for strat1, strat2 in COMPARISONS:
            data1 = df[(df["scenario"] == scenario) & (df["strategy"] == strat1)]
            data2 = df[(df["scenario"] == scenario) & (df["strategy"] == strat2)]

            if data1.empty or data2.empty:
                continue

            for metric in METRICS:
                # Mann-Whitney U test (independent distribution comparison)
                stat_u, p_u = stats.mannwhitneyu(data1[metric], data2[metric], alternative="two-sided")

                # Wilcoxon signed-rank test (paired by execution iteration)
                try:
                    stat_w, p_w = stats.wilcoxon(data1[metric].values, data2[metric].values)
                except ValueError:
                    # Occurs if all paired differences are zero
                    stat_w, p_w = 0.0, 1.0

                records.append({
                    "scenario": scenario,
                    "comparison": f"{strat1}_vs_{strat2}",
                    "metric": metric,
                    "mann_whitney_u": round(stat_u, 4),
                    "mann_whitney_p": round(p_u, 5),
                    "wilcoxon_stat": round(stat_w, 4),
                    "wilcoxon_p": round(p_w, 5),
                    "statistically_significant": "Yes" if (p_u < 0.05 or p_w < 0.05) else "No",
                })

    result_df = pd.DataFrame(records)
    out_file = PROCESSED_DIR / "wilcoxon_comparisons.csv"
    result_df.to_csv(out_file, index=False)
    print(f"  -> Saved hypothesis test results to: {out_file.relative_to(BASE_DIR)}")
    return result_df


def plot_split_latency_distribution(df: pd.DataFrame, out_dir: Path) -> None:
    """
    Render decoupled dual-axis subplots for p95 tail latency distribution,
    optimizing aspect ratio and vertical focus on the active performance ranges.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "distribution_latency_p95_split.png"

    print("[+] Rendering improved p95 tail latency distribution boxplot...")
    # Adjust aspect ratio to 10x5.5 to avoid horizontal flattening and compression
    fig, axes = plt.subplots(1, 2, figsize=(10, 5.5), dpi=300, sharey=False)

    box_kwargs = {
        "width": 0.38,
        "fliersize": 5,
        "linewidth": 1.4,
        "showmeans": True,
        "meanprops": {
            "marker": "^",
            "markerfacecolor": "white",
            "markeredgecolor": "black",
            "markersize": 6,
        },
    }

    # 1. Subplot: Nominal Scenario (focused on the 2.5 ms - 8.5 ms range)
    df_nom = df[df["scenario"] == "nominal"]
    sns.boxplot(
        data=df_nom,
        x="strategy",
        y="latency_p95_ms",
        hue="strategy",
        palette=PALETTE,
        legend=False,
        ax=axes[0],
        **box_kwargs,
    )
    axes[0].set_title("Nominal Scenario (300 RPS)", fontsize=12, fontweight="bold")
    axes[0].set_ylabel("p95 Latency (ms)", fontsize=11)
    axes[0].set_xlabel("")
    # Eliminate idle space below 2.5 ms while preserving JIT warmup outliers
    axes[0].set_ylim(2.5, 8.5)

    # 2. Subplot: Saturation Scenario (focused strictly on the 665 ms - 750 ms bracket)
    df_sat = df[df["scenario"] == "saturation"]
    sns.boxplot(
        data=df_sat,
        x="strategy",
        y="latency_p95_ms",
        hue="strategy",
        palette=PALETTE,
        legend=False,
        ax=axes[1],
        **box_kwargs,
    )
    axes[1].set_title("Saturation Scenario (1,200 RPS)", fontsize=12, fontweight="bold")
    axes[1].set_ylabel("p95 Latency (ms)", fontsize=11)
    axes[1].set_xlabel("")
    # Span the vertical range across the observed architectural tiers (676, 708, and 739 ms)
    axes[1].set_ylim(665, 750)

    plt.suptitle("Tail Latency Distribution (p95) by Persistence Strategy", fontsize=13, fontweight="bold", y=0.98)
    plt.tight_layout()
    fig.savefig(out_file)
    plt.close(fig)

    print(f"  -> Saved split distribution figure to: {out_file.relative_to(BASE_DIR)}")


def main():
    if not DATASET_PATH.exists():
        print(f"[-] Consolidated dataset not found: {DATASET_PATH}")
        sys.exit(1)

    df = pd.read_csv(DATASET_PATH)
    if df.empty:
        print("[-] Consolidated dataset is empty.")
        sys.exit(0)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Normality assessment
    run_shapiro_wilk(df)

    # 2. Pairwise hypothesis comparisons
    run_hypothesis_tests(df)

    # 3. Decoupled boxplot figure generation
    plot_split_latency_distribution(df, FIGURES_DIR)

    print("==> Statistical validation and figure generation completed successfully.")


if __name__ == "__main__":
    main()
