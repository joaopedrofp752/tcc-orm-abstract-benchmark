import sys
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_FILE = BASE_DIR / "processed-data" / "dataset_final.csv"
FIGURES_DIR = BASE_DIR / "figures"

# Configuração visual padronizada para artigos e monografia
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

def plot_single_strategy_stability(df_strat: pd.DataFrame, strategy: str, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Latência p95 por rodada
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    sns.barplot(data=df_strat, x="run", y="latency_p95_ms", color="#4C72B0", ax=ax)
    ax.set_title(f"p95 Latency Stability Across Iterations [{strategy}]")
    ax.set_xlabel("Run")
    ax.set_ylabel("p95 Latency (ms)")
    ax.set_ylim(bottom=0)
    plt.xticks(rotation=45)
    plt.tight_layout()
    fig.savefig(out_dir / "01_latency_stability.png")
    plt.close(fig)

    # 2. Throughput por rodada
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    sns.lineplot(data=df_strat, x="run", y="throughput_rps", marker="o", color="#55A868", ax=ax)
    ax.set_title(f"Sustained Throughput Across Iterations [{strategy}]")
    ax.set_xlabel("Run")
    ax.set_ylabel("Throughput (RPS)")
    ax.set_ylim(bottom=0)
    plt.xticks(rotation=45)
    plt.tight_layout()
    fig.savefig(out_dir / "02_throughput_stability.png")
    plt.close(fig)

    # 3. Telemetria da JVM (GC e CPU)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), dpi=300)
    sns.barplot(data=df_strat, x="run", y="gc_total_pause_ms", color="#C44E52", ax=axes[0])
    axes[0].set_title("Total GC Pause Time (ms)")
    axes[0].set_xlabel("Run")
    axes[0].set_ylabel("Accumulated Pause (ms)")
    axes[0].set_ylim(bottom=0)
    axes[0].tick_params(axis="x", rotation=45)

    sns.lineplot(data=df_strat, x="run", y="cpu_jvm_avg_pct", marker="s", color="#8172B3", ax=axes[1])
    axes[1].set_title("Average JVM CPU Utilization (%)")
    axes[1].set_xlabel("Run")
    axes[1].set_ylabel("CPU Usage (%)")
    axes[1].set_ylim(0, 100)
    axes[1].tick_params(axis="x", rotation=45)

    plt.tight_layout()
    fig.savefig(out_dir / "03_jvm_telemetry.png")
    plt.close(fig)


def plot_comparative_figures(df: pd.DataFrame, out_dir: Path):
    palette = {"hibernate": "#4C72B0", "hibernate-dto": "#55A868", "jdbc": "#DD8452"}

    # 1. Comparação de Latência (Boxplot com distribuição das 10 rodadas)
    fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
    sns.boxplot(data=df, x="strategy", y="latency_p95_ms", palette=palette, ax=ax, width=0.4)
    sns.stripplot(data=df, x="strategy", y="latency_p95_ms", color="black", alpha=0.6, jitter=0.1, ax=ax)
    ax.set_title("Tail Latency (p95) Comparison Across Persistence Strategies")
    ax.set_xlabel("Persistence Strategy")
    ax.set_ylabel("p95 Latency (ms)")
    ax.set_ylim(bottom=0)
    plt.tight_layout()
    fig.savefig(out_dir / "comparison_latency_p95.png")
    plt.close(fig)

    # 2. Comparação de Throughput
    fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
    sns.barplot(data=df, x="strategy", y="throughput_rps", palette=palette, ax=ax, errorbar="sd", capsize=0.1)
    ax.set_title("Sustained Throughput Comparison (Mean ± Std Dev)")
    ax.set_xlabel("Persistence Strategy")
    ax.set_ylabel("Throughput (RPS)")
    ax.set_ylim(bottom=0)
    plt.tight_layout()
    fig.savefig(out_dir / "comparison_throughput.png")
    plt.close(fig)

    # 3. Comparação de Recursos JVM (GC Pause e CPU)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=300)
    sns.barplot(data=df, x="strategy", y="gc_total_pause_ms", palette=palette, ax=axes[0], errorbar="sd", capsize=0.1)
    axes[0].set_title("Accumulated GC Pause Time Comparison")
    axes[0].set_xlabel("Persistence Strategy")
    axes[0].set_ylabel("Total Pause Time (ms)")
    axes[0].set_ylim(bottom=0)

    sns.barplot(data=df, x="strategy", y="cpu_jvm_avg_pct", palette=palette, ax=axes[1], errorbar="sd", capsize=0.1)
    axes[1].set_title("Average JVM CPU Utilization Comparison")
    axes[1].set_xlabel("Persistence Strategy")
    axes[1].set_ylabel("CPU Usage (%)")
    axes[1].set_ylim(0, 100)

    plt.tight_layout()
    fig.savefig(out_dir / "comparison_jvm_telemetry.png")
    plt.close(fig)


def main():
    if not PROCESSED_FILE.exists():
        print(f"[-] Consolidated file not found: {PROCESSED_FILE}")
        sys.exit(1)

    df = pd.read_csv(PROCESSED_FILE)
    if df.empty:
        print("[-] Consolidated dataset is empty. Skipping figures.")
        sys.exit(0)

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    strategies = df["strategy"].unique()

    # Gera os gráficos individuais de cada estratégia em sua própria pasta
    for strat in strategies:
        df_strat = df[df["strategy"] == strat].copy()
        strat_dir = FIGURES_DIR / strat
        print(f"[+] Generating stability figures for '{strat}' in figures/{strat}/...")
        plot_single_strategy_stability(df_strat, strat, strat_dir)

    # Se houver mais de uma estratégia coletada, gera os gráficos comparativos na raiz
    if len(strategies) > 1:
        print(f"[+] Generating cross-strategy comparative figures in figures/...")
        plot_comparative_figures(df, FIGURES_DIR)
    else:
        print("[i] Only 1 strategy available. Comparative charts will be generated once other strategies are executed.")

    print(f"==> Figures successfully organized in: {FIGURES_DIR.name}/")

if __name__ == "__main__":
    main()
