#!/usr/bin/env python3
"""
05_statistical_tests.py - Perform Shapiro-Wilk normality assessment, Mann-Whitney U
hypothesis testing with Holm-Bonferroni multiplicity correction, non-parametric
effect sizes (median difference and Cliff's delta with 95% bootstrap CIs), and
render decoupled split-scale distribution boxplots in Portuguese.

Inferential Statistics Methodology:
1. Normality Assessment (Shapiro-Wilk):
   - Evaluates empirical distributions against normality (alpha = 0.05), justifying
     rank-based non-parametric inference when skewness or warmup outliers occur.
2. Independent Rank-Sum Testing (Mann-Whitney U) & Holm Correction:
   - Compares independent strategy samples (n = 10 per cell) without assuming pairing
     across separate Git branch runs, controlling family-wise error rate per scenario
     via the step-down Holm-Bonferroni procedure.
3. Non-Parametric Effect Size (Cliff's Delta & Median Difference):
   - Quantifies practical magnitude alongside p-values using Cliff's delta (Romano et al.
     thresholds: <0.147 negligible, <0.33 small, <0.474 medium, >=0.474 large) and
     stratified bootstrap 95% confidence intervals (5,000 resamples).
4. Decoupled Dual-Axis Visualization:
   - Implements a small-multiples layout separating Nominal (2.5 - 8.5 ms) and
     Saturation (665 - 750 ms) scales so quartile structure remains legible.
"""

import sys
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "processed-data"
FIGURES_DIR = BASE_DIR / "figures" / "comparisons"
DATASET_PATH = PROCESSED_DIR / "dataset_final.csv"
DIAG_PATH = PROCESSED_DIR / "diagnostics_dataset.csv"

SCENARIOS = ["nominal", "saturation"]
STRATEGIES = ["hibernate", "hibernate-dto", "jdbc"]

# Exclude nominal throughput_rps from pairwise hypothesis testing because open-model
# constant-arrival-rate injection clamps all strategies at ~300.00 RPS by design
METRICS_BY_SCENARIO = {
    "nominal": ["latency_p95_ms", "gc_total_pause_ms", "cpu_jvm_avg_pct"],
    "saturation": ["latency_p95_ms", "throughput_rps", "gc_total_pause_ms", "cpu_jvm_avg_pct"],
}

COMPARISONS = [
    ("hibernate", "jdbc"),
    ("hibernate", "hibernate-dto"),
    ("hibernate-dto", "jdbc"),
]

STRATEGY_TICK_LABELS = {
    "hibernate": "Hibernate\n(Entidades)",
    "hibernate-dto": "Hibernate\n(Projeção DTO)",
    "jdbc": "JDBC\nNativo",
}

PALETTE = {"hibernate": "#4C72B0", "hibernate-dto": "#55A868", "jdbc": "#DD8452"}

# Standardized visual styling matching 04_generate_figures.py
sns.set_theme(style="whitegrid", font="sans-serif")
plt.rcParams.update({
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.titlesize": 14,
})


def holm_bonferroni(p_values: list[float]) -> list[float]:
    """
    Apply step-down Holm-Bonferroni adjustment to a family of raw p-values,
    enforcing monotonicity across ordered hypotheses.
    """
    m = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [0.0] * m
    running_max = 0.0

    for rank, (orig_idx, p_val) in enumerate(indexed):
        corrected = min(1.0, (m - rank) * p_val)
        running_max = max(running_max, corrected)
        adjusted[orig_idx] = running_max

    return adjusted


def cliffs_delta_and_bootstrap_ci(
    x: np.ndarray, y: np.ndarray, n_boot: int = 5000, seed: int = 42
) -> tuple[float, float, tuple[float, float], float, tuple[float, float], str]:
    """
    Compute Mann-Whitney U statistic, exact Cliff's delta, median difference,
    and 95% percentile bootstrap confidence intervals for both effect estimates.
    """
    u_stat, _ = stats.mannwhitneyu(x, y, alternative="two-sided")
    n1, n2 = len(x), len(y)

    # Exact relation between Mann-Whitney U and Cliff's delta: delta = (2U / (n1*n2)) - 1
    delta = (2.0 * u_stat) / (n1 * n2) - 1.0
    med_diff = float(np.median(x) - np.median(y))

    # Vectorized non-parametric bootstrap resampling (5,000 iterations)
    rng = np.random.default_rng(seed)
    bx = x[rng.integers(0, n1, size=(n_boot, n1))]
    by = y[rng.integers(0, n2, size=(n_boot, n2))]

    boot_med_diffs = np.median(bx, axis=1) - np.median(by, axis=1)
    gt_counts = (bx[:, :, None] > by[:, None, :]).sum(axis=(1, 2))
    lt_counts = (bx[:, :, None] < by[:, None, :]).sum(axis=(1, 2))
    boot_deltas = (gt_counts - lt_counts) / (n1 * n2)

    med_ci = (float(np.percentile(boot_med_diffs, 2.5)), float(np.percentile(boot_med_diffs, 97.5)))
    delta_ci = (float(np.percentile(boot_deltas, 2.5)), float(np.percentile(boot_deltas, 97.5)))

    # Classify magnitude according to Romano et al. (2006) thresholds
    abs_d = abs(delta)
    if abs_d < 0.147:
        magnitude = "desprezível"
    elif abs_d < 0.33:
        magnitude = "pequeno"
    elif abs_d < 0.474:
        magnitude = "médio"
    else:
        magnitude = "grande"

    return float(u_stat), med_diff, med_ci, float(delta), delta_ci, magnitude


def run_shapiro_wilk(df: pd.DataFrame) -> pd.DataFrame:
    """
    Perform the Shapiro-Wilk test of normality across all experimental cells.
    """
    print("[+] Running Shapiro-Wilk normality tests (alpha = 0.05)...")
    records = []
    candidate_metrics = ["latency_p95_ms", "throughput_rps", "gc_total_pause_ms", "cpu_jvm_avg_pct", "heap_used_peak_mb"]

    for scenario in SCENARIOS:
        for strategy in STRATEGIES:
            subset = df[(df["scenario"] == scenario) & (df["strategy"] == strategy)]
            if subset.empty:
                continue

            for metric in candidate_metrics:
                if metric not in subset.columns:
                    continue
                stat, p_val = stats.shapiro(subset[metric])
                records.append({
                    "scenario": scenario,
                    "strategy": strategy,
                    "metric": metric,
                    "statistic_w": round(float(stat), 4),
                    "p_value": round(float(p_val), 5),
                    "is_normal": "Sim" if p_val >= 0.05 else "Não",
                })

    result_df = pd.DataFrame(records)
    out_file = PROCESSED_DIR / "shapiro_wilk_results.csv"
    result_df.to_csv(out_file, index=False)
    print(f"  -> Saved Shapiro-Wilk results to: {out_file.relative_to(BASE_DIR)}")
    return result_df


def run_hypothesis_tests(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute two-sided Mann-Whitney U tests, Holm-Bonferroni adjusted p-values,
    median differences, and Cliff's delta effect sizes across strategy pairs.
    """
    print("[+] Running Mann-Whitney U tests with Holm correction and Cliff's delta...")
    records = []

    for scenario in SCENARIOS:
        scenario_records = []
        for strat1, strat2 in COMPARISONS:
            data1 = df[(df["scenario"] == scenario) & (df["strategy"] == strat1)]
            data2 = df[(df["scenario"] == scenario) & (df["strategy"] == strat2)]

            if data1.empty or data2.empty:
                continue

            for metric in METRICS_BY_SCENARIO[scenario]:
                x = data1[metric].to_numpy(dtype=float)
                y = data2[metric].to_numpy(dtype=float)

                _, p_raw = stats.mannwhitneyu(x, y, alternative="two-sided")
                u_stat, med_diff, med_ci, delta, delta_ci, magnitude = cliffs_delta_and_bootstrap_ci(x, y)

                scenario_records.append({
                    "scenario": scenario,
                    "comparison": f"{strat1} vs. {strat2}",
                    "metric": metric,
                    "median_1": round(float(np.median(x)), 2),
                    "median_2": round(float(np.median(y)), 2),
                    "median_diff": round(med_diff, 2),
                    "median_diff_ci95_low": round(med_ci[0], 2),
                    "median_diff_ci95_high": round(med_ci[1], 2),
                    "mann_whitney_u": round(u_stat, 2),
                    "p_raw": float(p_raw),
                    "cliffs_delta": round(delta, 3),
                    "cliffs_delta_ci95_low": round(delta_ci[0], 3),
                    "cliffs_delta_ci95_high": round(delta_ci[1], 3),
                    "effect_magnitude": magnitude,
                })

        # Apply Holm-Bonferroni correction within each scenario family
        if scenario_records:
            adjusted_ps = holm_bonferroni([r["p_raw"] for r in scenario_records])
            for rec, p_adj in zip(scenario_records, adjusted_ps):
                rec["p_holm"] = round(p_adj, 5)
                rec["p_raw"] = round(rec["p_raw"], 5)
                rec["significant_holm_005"] = "Sim" if p_adj < 0.05 else "Não"
            records.extend(scenario_records)

    result_df = pd.DataFrame(records)
    out_file = PROCESSED_DIR / "mann_whitney_comparisons.csv"
    result_df.to_csv(out_file, index=False)
    print(f"  -> Saved inferential comparison table to: {out_file.relative_to(BASE_DIR)}")

    summary_cols = [
        "scenario", "comparison", "metric", "median_diff",
        "mann_whitney_u", "p_holm", "cliffs_delta", "effect_magnitude"
    ]
    print(result_df[summary_cols].to_string(index=False))
    return result_df


def summarize_diagnostics() -> None:
    """
    Print median telemetry summary for the interleaved saturation diagnostic runs
    (HikariCP retention/queueing, PostgreSQL cgroup CPU/throttling, and isolated CPU).
    """
    if not DIAG_PATH.exists():
        return

    diag_df = pd.read_csv(DIAG_PATH)
    if diag_df.empty:
        return

    target_cols = [
        "throughput_rps", "latency_p95_ms", "dropped_iterations",
        "hikari_usage_mean_ms", "hikari_acquire_mean_ms", "hikari_pending_mean",
        "pg_cores_used", "pg_cpu_limit_pct", "pg_nr_throttled", "pg_cache_hit_pct",
        "jvm_cpu_one_core_pct", "k6_cpu_one_core_pct"
    ]
    available_cols = [c for c in target_cols if c in diag_df.columns]

    print("[+] Interleaved saturation diagnostics medians (1,200 RPS):")
    print(diag_df.groupby("strategy")[available_cols].median().round(3).to_string())


def plot_split_latency_distribution(df: pd.DataFrame, out_dir: Path) -> None:
    """
    Render decoupled dual-axis subplots for p95 tail latency distribution in Portuguese,
    isolating Nominal (2.5 - 8.5 ms) and Saturation (665 - 750 ms) vertical scales.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "distribution_latency_p95_split.png"

    print("[+] Rendering decoupled p95 tail latency distribution boxplot...")
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 5.5), dpi=300, sharey=False)

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

    subplot_specs = [
        ("nominal", "Cenário Nominal (300 RPS)", (2.5, 8.5)),
        ("saturation", "Cenário de Saturação (1.200 RPS)", (665, 750)),
    ]

    for idx, (scen_key, title_pt, y_limits) in enumerate(subplot_specs):
        sub_df = df[df["scenario"] == scen_key]
        sns.boxplot(
            data=sub_df,
            x="strategy",
            y="latency_p95_ms",
            hue="strategy",
            order=STRATEGIES,
            palette=PALETTE,
            legend=False,
            ax=axes[idx],
            **box_kwargs,
        )
        axes[idx].set_title(title_pt, fontsize=12, fontweight="bold")
        axes[idx].set_ylabel("Latência de Cauda p95 (ms)", fontsize=11)
        axes[idx].set_xlabel("")
        axes[idx].set_xticks(range(len(STRATEGIES)))
        axes[idx].set_xticklabels([STRATEGY_TICK_LABELS[s] for s in STRATEGIES])
        axes[idx].set_ylim(*y_limits)

    plt.suptitle("Distribuição da Latência de Cauda (p95) por Estratégia de Persistência", fontsize=13, fontweight="bold", y=0.98)
    plt.tight_layout()
    fig.savefig(out_file)
    plt.close(fig)

    print(f"  -> Saved split distribution figure to: {out_file.relative_to(BASE_DIR)}")


def main():
    """Execute complete statistical validation pipeline and decoupled figure generation."""
    if not DATASET_PATH.exists():
        print(f"[-] Consolidated dataset not found: {DATASET_PATH}")
        sys.exit(1)

    df = pd.read_csv(DATASET_PATH)
    if df.empty:
        print("[-] Consolidated dataset is empty.")
        sys.exit(0)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    run_shapiro_wilk(df)
    run_hypothesis_tests(df)
    summarize_diagnostics()
    plot_split_latency_distribution(df, FIGURES_DIR)

    print("==> Statistical validation and figure generation completed successfully.")


if __name__ == "__main__":
    main()
