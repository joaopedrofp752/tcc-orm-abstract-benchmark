#!/usr/bin/env python3
"""
04_generate_figures.py - Generates per-strategy stability charts and cross-scenario
comparative visualizations for academic reporting.
"""

import sys
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_FILE = BASE_DIR / "processed-data" / "dataset_final.csv"
FIGURES_DIR = BASE_DIR / "figures"

# Configuração visual padronizada
sns.set_theme(style="whitegrid", font="sans-serif")
plt.rcParams.update({
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 11,
    "figure.titlesize": 14
})

PALETTE = {"hibernate": "#4C72B0", "hibernate-dto": "#55A868", "jdbc": "#DD8452"}


def plot_stability(df_subset: pd.DataFrame, scenario: str, strategy: str, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Latência p95 por rodada
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    sns.barplot(data=df_subset, x="run", y="latency_p95_ms", color="#4C72B0", ax=ax)
    ax.set_title(f"p95 Latency Stability [{scenario.upper()} - {strategy}]")
    ax.set_xlabel("Run")
    ax.set_ylabel("p95 Latency (ms)")
    ax.set_ylim(bottom=0)
    plt.xticks(rotation=45)
    plt.tight_layout()
    fig.savefig(out_dir / "01_latency_stability.png")
    plt.close(fig)

    # 2. Throughput por rodada
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    sns.lineplot(data=df_subset, x="run", y="throughput_rps", marker="o", color="#55A868", ax=ax)
    ax.set_title(f"Sustained Throughput [{scenario.upper()} - {strategy}]")
    ax.set_xlabel("Run")
    ax.set_ylabel("Throughput (RPS)")
    ax.set_ylim(bottom=0)
    plt.xticks(rotation=45)
    plt.tight_layout()
    fig.savefig(out_dir / "02_throughput_stability.png")
    plt.close(fig)

    # 3. Telemetria JVM (GC e CPU)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), dpi=300)
    sns.barplot(data=df_subset, x="run", y="gc_total_pause_ms", color="#C44E52", ax=axes[0])
    axes[0].set_title("Total GC Pause Time (ms)")
    axes[0].set_xlabel("Run")
    axes[0].set_ylabel("Accumulated Pause (ms)")
    axes[0].set_ylim(bottom=0)
    axes[0].tick_params(axis="x", rotation=45)

    sns.lineplot(data=df_subset, x="run", y="cpu_jvm_avg_pct", marker="s", color="#8172B3", ax=axes[1])
    axes[1].set_title("Average JVM CPU Utilization (%)")
    axes[1].set_xlabel("Run")
    axes[1].set_ylabel("CPU Usage (%)")
    axes[1].set_ylim(0, 100)
    axes[1].tick_params(axis="x", rotation=45)

    plt.tight_layout()
    fig.savefig(out_dir / "03_jvm_telemetry.png")
    plt.close(fig)


def plot_global_comparisons(df: pd.DataFrame, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Comparação de Latência de Cauda (p95) lado a lado
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    sns.barplot(
        data=df, x="scenario", y="latency_p95_ms", hue="strategy",
        palette=PALETTE, errorbar="sd", capsize=0.08, ax=ax
    )
    ax.set_title("Tail Latency (p95): Nominal (300 RPS) vs Saturation (1200 RPS)")
    ax.set_xlabel("Workload Scenario")
    ax.set_ylabel("p95 Latency (ms)")
    ax.set_ylim(bottom=0)
    plt.tight_layout()
    fig.savefig(out_dir / "comparison_latency_p95.png")
    plt.close(fig)

    # 2. Distribuição da Cauda (Boxplot)
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    sns.boxplot(data=df, x="scenario", y="latency_p95_ms", hue="strategy", palette=PALETTE, ax=ax, width=0.5)
    ax.set_title("Tail Latency Distribution Across Scenarios")
    ax.set_xlabel("Workload Scenario")
    ax.set_ylabel("p95 Latency (ms)")
    ax.set_ylim(bottom=0)
    plt.tight_layout()
    fig.savefig(out_dir / "distribution_latency_p95.png")
    plt.close(fig)

    # 3. Comparação de Throughput
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    sns.barplot(
        data=df, x="scenario", y="throughput_rps", hue="strategy",
        palette=PALETTE, errorbar="sd", capsize=0.08, ax=ax
    )
    ax.set_title("Sustained Throughput Across Scenarios")
    ax.set_xlabel("Workload Scenario")
    ax.set_ylabel("Throughput (RPS)")
    ax.set_ylim(bottom=0)
    plt.tight_layout()
    fig.savefig(out_dir / "comparison_throughput.png")
    plt.close(fig)

    # 4. Pausas de GC Acumuladas
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    sns.barplot(
        data=df, x="scenario", y="gc_total_pause_ms", hue="strategy",
        palette=PALETTE, errorbar="sd", capsize=0.08, ax=ax
    )
    ax.set_title("Accumulated Garbage Collection Pauses Across Scenarios")
    ax.set_xlabel("Workload Scenario")
    ax.set_ylabel("Total GC Pause Time (ms)")
    ax.set_ylim(bottom=0)
    plt.tight_layout()
    fig.savefig(out_dir / "comparison_gc_pause.png")
    plt.close(fig)

    # 5. Utilização de CPU da JVM
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    sns.barplot(
        data=df, x="scenario", y="cpu_jvm_avg_pct", hue="strategy",
        palette=PALETTE, errorbar="sd", capsize=0.08, ax=ax
    )
    ax.set_title("Average JVM CPU Utilization Across Scenarios")
    ax.set_xlabel("Workload Scenario")
    ax.set_ylabel("CPU Utilization (%)")
    ax.set_ylim(0, 100)
    plt.tight_layout()
    fig.savefig(out_dir / "comparison_cpu_usage.png")
    plt.close(fig)


def main():
    if not PROCESSED_FILE.exists():
        print(f"[-] Consolidated file not found: {PROCESSED_FILE}")
        sys.exit(1)

    df = pd.read_csv(PROCESSED_FILE)
    if df.empty:
        print("[-] Consolidated dataset is empty.")
        sys.exit(0)

    # Gráficos individuais de estabilidade
    for scenario in df["scenario"].unique():
        for strategy in df["strategy"].unique():
            df_subset = df[(df["scenario"] == scenario) & (df["strategy"] == strategy)]
            if not df_subset.empty:
                out_dir = FIGURES_DIR / scenario / strategy
                print(f"[+] Generating stability charts for [{scenario} | {strategy}]...")
                plot_stability(df_subset, scenario, strategy, out_dir)

    # Gráficos comparativos globais
    if len(df["strategy"].unique()) > 1:
        comp_dir = FIGURES_DIR / "comparisons"
        print(f"[+] Generating global comparative figures in {comp_dir.relative_to(BASE_DIR)}...")
        plot_global_comparisons(df, comp_dir)

    print("==> Figure generation finished successfully.")


if __name__ == "__main__":
    main()
