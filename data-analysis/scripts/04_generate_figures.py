#!/usr/bin/env python3
"""
04_generate_figures.py - Generate publication-quality figures for TCC monography.
"""

from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "processed-data" / "dataset_final.csv"
FIGURES_DIR = BASE_DIR / "figures"

# Matplotlib & Seaborn styling
sns.set_theme(style="whitegrid", palette="deep")
plt.rcParams.update({
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.titlesize": 14,
    "figure.dpi": 300
})


def plot_latency(df: pd.DataFrame) -> None:
    plt.figure(figsize=(9, 5))
    num_strategies = df["strategy"].nunique()

    if num_strategies > 1:
        # Grouped bar chart comparing percentiles across strategies
        melted = df.melt(
            id_vars=["strategy"],
            value_vars=["latency_p50_ms", "latency_p95_ms", "latency_p99_ms"],
            var_name="percentile",
            value_name="latency_ms"
        )
        melted["percentile"] = melted["percentile"].str.replace("latency_", "").str.replace("_ms", "").str.upper()

        ax = sns.barplot(data=melted, x="percentile", y="latency_ms", hue="strategy", errorbar="sd")
        ax.set_title("Latency Distribution Across Persistence Strategies (Mean ± SD)")
        ax.set_ylabel("Latency (ms)")
        ax.set_xlabel("Percentile")
    else:
        # Single strategy: show run stability
        ax = sns.barplot(data=df, x="run", y="latency_p95_ms", color="#4C72B0")
        ax.set_title(f"p95 Latency Stability Across Iterations [{df['strategy'].iloc[0]}]")
        ax.set_ylabel("p95 Latency (ms)")
        ax.set_xlabel("Run")
        plt.xticks(rotation=45)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "01_latency_analysis.png")
    plt.close()


def plot_throughput(df: pd.DataFrame) -> None:
    plt.figure(figsize=(9, 5))
    num_strategies = df["strategy"].nunique()

    if num_strategies > 1:
        ax = sns.barplot(data=df, x="strategy", y="throughput_rps", errorbar="sd", palette="viridis")
        ax.set_title("Throughput Comparison (Requests per Second - Mean ± SD)")
    else:
        ax = sns.lineplot(data=df, x="run", y="throughput_rps", marker="o", color="#55A868")
        ax.set_title(f"Sustained Throughput Across Iterations [{df['strategy'].iloc[0]}]")
        plt.xticks(rotation=45)

    ax.set_ylabel("Throughput (RPS)")
    ax.set_xlabel("Persistence Strategy" if num_strategies > 1 else "Run")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "02_throughput_analysis.png")
    plt.close()


def plot_jvm_telemetry(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    num_strategies = df["strategy"].nunique()

    # Left plot: GC pause time
    if num_strategies > 1:
        sns.barplot(ax=axes[0], data=df, x="strategy", y="gc_total_pause_ms", errorbar="sd", palette="mako")
    else:
        sns.barplot(ax=axes[0], data=df, x="run", y="gc_total_pause_ms", color="#C44E52")
        axes[0].tick_params(axis="x", rotation=45)

    axes[0].set_title("Total GC Pause Time (ms)")
    axes[0].set_ylabel("Accumulated Pause (ms)")
    axes[0].set_xlabel("Strategy" if num_strategies > 1 else "Run")

    # Right plot: JVM CPU Load
    if num_strategies > 1:
        sns.barplot(ax=axes[1], data=df, x="strategy", y="cpu_jvm_avg_pct", errorbar="sd", palette="rocket")
    else:
        sns.lineplot(ax=axes[1], data=df, x="run", y="cpu_jvm_avg_pct", marker="s", color="#8172B3")
        axes[1].tick_params(axis="x", rotation=45)

    axes[1].set_title("Average JVM CPU Utilization (%)")
    axes[1].set_ylabel("CPU Usage (%)")
    axes[1].set_xlabel("Strategy" if num_strategies > 1 else "Run")

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "03_jvm_telemetry_analysis.png")
    plt.close()


def main():
    if not DATA_FILE.exists():
        print(f"[!] Consolidated data not found at {DATA_FILE}. Run 03_consolidate.py first.")
        return

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA_FILE)

    print(f"[+] Generating figures from {len(df)} records...")
    plot_latency(df)
    plot_throughput(df)
    plot_jvm_telemetry(df)

    print(f"==> Figures successfully saved to: {FIGURES_DIR.relative_to(BASE_DIR)}/")


if __name__ == "__main__":
    main()
