#!/usr/bin/env python3
"""
04_generate_figures.py - Generates per-strategy stability charts, cross-scenario
comparative visualizations, and internal mechanism diagnostics (300 DPI) with
Portuguese labels for academic publication.

Publication Standards & Visual Design:
- Conforms to IEEE/ACM guidelines for academic figures (300 DPI raster clarity).
- Preserves a consistent, colorblind-friendly palette across all persistence strategies:
  * Hibernate (Entidades): #4C72B0 (Steel Blue)
  * Hibernate (Projeção DTO): #55A868 (Muted Green)
  * JDBC Nativo: #DD8452 (Terracotta Orange)
- Stability plots evaluate run-to-run stationarity, proving the absence of thermal
  throttling, background operating system jitter, or resource leakage.
- Diagnostic figures illustrate internal connection pool retention (HikariCP) and
  database container CPU saturation (cgroup v2) collected during interleaved runs.
"""

import sys
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_FILE = BASE_DIR / "processed-data" / "dataset_final.csv"
DIAG_FILE = BASE_DIR / "processed-data" / "diagnostics_dataset.csv"
FIGURES_DIR = BASE_DIR / "figures"

# Configure standardized typography and layout for academic publication
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

STRATEGY_LABELS = {
    "hibernate": "Hibernate (Entidades)",
    "hibernate-dto": "Hibernate (Projeção DTO)",
    "jdbc": "JDBC Nativo",
}

SCENARIO_LABELS = {
    "nominal": "Nominal (300 RPS)",
    "saturation": "Saturação (1.200 RPS)",
}

PALETTE_PT = {
    "Hibernate (Entidades)": "#4C72B0",
    "Hibernate (Projeção DTO)": "#55A868",
    "JDBC Nativo": "#DD8452",
}


def plot_stability(df_subset: pd.DataFrame, scenario: str, strategy: str, out_dir: Path) -> None:
    """
    Render run-by-run stability figures for a given strategy and workload scenario,
    validating stationarity and absence of transient noise across iterations.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    scen_pt = SCENARIO_LABELS.get(scenario, scenario)
    strat_pt = STRATEGY_LABELS.get(strategy, strategy)

    # 1. p95 tail latency per iteration (validates warmup vs. steady state)
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    sns.barplot(data=df_subset, x="run", y="latency_p95_ms", color="#4C72B0", ax=ax)
    ax.set_title(f"Estabilidade da Latência p95 [{scen_pt} - {strat_pt}]")
    ax.set_xlabel("Execução")
    ax.set_ylabel("Latência p95 (ms)")
    ax.set_ylim(bottom=0)
    plt.xticks(rotation=45)
    plt.tight_layout()
    fig.savefig(out_dir / "01_latency_stability.png")
    plt.close(fig)

    # 2. Sustained throughput per iteration (ensures consistent traffic injection)
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    sns.lineplot(data=df_subset, x="run", y="throughput_rps", marker="o", color="#55A868", ax=ax)
    ax.set_title(f"Vazão Sustentada [{scen_pt} - {strat_pt}]")
    ax.set_xlabel("Execução")
    ax.set_ylabel("Vazão (RPS)")
    ax.set_ylim(bottom=0)
    plt.xticks(rotation=45)
    plt.tight_layout()
    fig.savefig(out_dir / "02_throughput_stability.png")
    plt.close(fig)

    # 3. JVM telemetry: accumulated GC pause times and mean CPU load
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), dpi=300)
    sns.barplot(data=df_subset, x="run", y="gc_total_pause_ms", color="#C44E52", ax=axes[0])
    axes[0].set_title("Tempo Acumulado de Pausas de GC (ms)")
    axes[0].set_xlabel("Execução")
    axes[0].set_ylabel("Pausa Acumulada (ms)")
    axes[0].set_ylim(bottom=0)
    axes[0].tick_params(axis="x", rotation=45)

    sns.lineplot(data=df_subset, x="run", y="cpu_jvm_avg_pct", marker="s", color="#8172B3", ax=axes[1])
    axes[1].set_title("Utilização Média de CPU da JVM (%)")
    axes[1].set_xlabel("Execução")
    axes[1].set_ylabel("Uso de CPU (%)")
    axes[1].set_ylim(0, 100)
    axes[1].tick_params(axis="x", rotation=45)

    plt.tight_layout()
    fig.savefig(out_dir / "03_jvm_telemetry.png")
    plt.close(fig)


def plot_global_comparisons(df: pd.DataFrame, out_dir: Path) -> None:
    """
    Render cross-strategy grouped comparative figures across Nominal and Saturation scenarios.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_df = df.copy()
    plot_df["Estratégia"] = plot_df["strategy"].map(STRATEGY_LABELS)
    plot_df["Cenário"] = plot_df["scenario"].map(SCENARIO_LABELS)

    # 1. Unified scale boxplot retained for macroscopic overview;
    # decoupled dual-axis boxplot is generated in 05_statistical_tests.py
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    sns.boxplot(
        data=plot_df, x="Cenário", y="latency_p95_ms", hue="Estratégia",
        palette=PALETTE_PT, ax=ax, width=0.5
    )
    ax.set_title("Distribuição da Latência de Cauda (p95) entre Cenários")
    ax.set_xlabel("Cenário de Carga")
    ax.set_ylabel("Latência p95 (ms)")
    ax.set_ylim(bottom=0)
    plt.tight_layout()
    fig.savefig(out_dir / "distribution_latency_p95.png")
    plt.close(fig)

    # 2. Grouped bar charts with standard deviation (SD) error bars
    bar_specs = [
        (
            "latency_p95_ms",
            "Latência de Cauda (p95): Nominal vs. Saturação",
            "Latência p95 (ms)",
            "comparison_latency_p95.png",
            None,
        ),
        (
            "throughput_rps",
            "Vazão Sustentada por Cenário de Carga",
            "Vazão (RPS)",
            "comparison_throughput.png",
            None,
        ),
        (
            "gc_total_pause_ms",
            "Pausas Acumuladas de Coleta de Lixo (GC)",
            "Tempo Total de Pausa GC (ms)",
            "comparison_gc_pause.png",
            None,
        ),
        (
            "cpu_jvm_avg_pct",
            "Utilização Média de CPU da JVM por Cenário",
            "Utilização de CPU (%)",
            "comparison_cpu_usage.png",
            (0, 100),
        ),
    ]

    for col, title, ylabel, fname, ylim in bar_specs:
        fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
        sns.barplot(
            data=plot_df, x="Cenário", y=col, hue="Estratégia",
            palette=PALETTE_PT, errorbar="sd", capsize=0.08, ax=ax
        )
        ax.set_title(title)
        ax.set_xlabel("Cenário de Carga")
        ax.set_ylabel(ylabel)
        if ylim:
            ax.set_ylim(*ylim)
        else:
            ax.set_ylim(bottom=0)
        plt.tight_layout()
        fig.savefig(out_dir / fname)
        plt.close(fig)


def plot_diagnostics_mechanisms(diag_df: pd.DataFrame, out_dir: Path) -> None:
    """
    Render dual-panel diagnostic chart exposing internal bottlenecks under interleaved
    saturation (1,200 RPS): HikariCP connection hold duration and PostgreSQL cgroup CPU quota.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_df = diag_df.copy()
    plot_df["Estratégia"] = plot_df["strategy"].map(STRATEGY_LABELS)
    order_pt = [STRATEGY_LABELS[s] for s in ["hibernate", "hibernate-dto", "jdbc"] if s in diag_df["strategy"].unique()]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), dpi=300)

    # Panel A: Mean connection retention time inside HikariCP pool
    sns.barplot(
        data=plot_df, x="Estratégia", y="hikari_usage_mean_ms", hue="Estratégia",
        order=order_pt, palette=PALETTE_PT, legend=False, errorbar="sd", capsize=0.08, ax=axes[0]
    )
    axes[0].set_title("Retenção Média de Conexão no HikariCP")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Tempo de Uso da Conexão (ms)")
    axes[0].set_ylim(bottom=0)
    axes[0].tick_params(axis="x", rotation=10)

    # Panel B: PostgreSQL container CPU utilization relative to its 2.0-core Docker limit
    sns.barplot(
        data=plot_df, x="Estratégia", y="pg_cpu_limit_pct", hue="Estratégia",
        order=order_pt, palette=PALETTE_PT, legend=False, errorbar="sd", capsize=0.08, ax=axes[1]
    )
    axes[1].set_title("Consumo de CPU do PostgreSQL (% dos 2 Núcleos)")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Uso da Cota de CPU (%)")
    axes[1].set_ylim(0, 110)
    axes[1].tick_params(axis="x", rotation=10)

    plt.suptitle("Diagnóstico Interno sob Saturação Intercalada (1.200 RPS)", fontsize=13, fontweight="bold", y=0.98)
    plt.tight_layout()
    fig.savefig(out_dir / "diagnostics_mechanisms.png")
    plt.close(fig)


def main():
    """Validate dataset existence and render all individual, comparative, and diagnostic charts."""
    if not PROCESSED_FILE.exists():
        print(f"[-] Consolidated file not found: {PROCESSED_FILE}")
        sys.exit(1)

    df = pd.read_csv(PROCESSED_FILE)
    if df.empty:
        print("[-] Consolidated dataset is empty.")
        sys.exit(0)

    # Generate individual stability figures for each primary experimental cell
    for scenario in df["scenario"].unique():
        for strategy in df["strategy"].unique():
            df_subset = df[(df["scenario"] == scenario) & (df["strategy"] == strategy)]
            if not df_subset.empty:
                out_dir = FIGURES_DIR / scenario / strategy
                print(f"[+] Generating stability charts for [{scenario} | {strategy}]...")
                plot_stability(df_subset, scenario, strategy, out_dir)

    # Generate cross-strategy comparative charts
    comp_dir = FIGURES_DIR / "comparisons"
    if len(df["strategy"].unique()) > 1:
        print(f"[+] Generating global comparative figures in {comp_dir.relative_to(BASE_DIR)}...")
        plot_global_comparisons(df, comp_dir)

    # Generate internal mechanism chart if diagnostic telemetry has been consolidated
    if DIAG_FILE.exists():
        diag_df = pd.read_csv(DIAG_FILE)
        if not diag_df.empty and "hikari_usage_mean_ms" in diag_df.columns:
            print("[+] Generating diagnostic mechanisms figure...")
            plot_diagnostics_mechanisms(diag_df, comp_dir)

    print("==> Figure generation finished successfully.")


if __name__ == "__main__":
    main()
