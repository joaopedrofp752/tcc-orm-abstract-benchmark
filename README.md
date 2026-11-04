# Persistence Layer Benchmark (Spring Boot & Java 21)

A reproducible benchmark harness evaluating latency, throughput, and JVM resource consumption across three persistence approaches: **Hibernate ORM**, **Hibernate DTO projections**, and **Native JDBC** under two distinct workload profiles:
* **Nominal:** 300 RPS (30 pre-allocated VUs / 90 max VUs)
* **Saturation:** 1,200 RPS (120 pre-allocated VUs / 360 max VUs)

---

## Prerequisites

Ensure the following tools are installed and accessible in your `$PATH`:

* **JDK 21+** (must include native `jfr` and `jcmd` CLI utilities)
* **Docker & Docker Compose** (for PostgreSQL)
* **k6** (HTTP load testing engine)
* **Python 3.10+** (with `venv` support)

---

## Project Structure

```text
.
├── backend/            # Spring Boot 3 / Java 21 application
├── database/           # PostgreSQL configuration, schemas, and compose file
├── load-tests/         # Parametrized k6 execution scripts (nominal / saturation / warmup)
├── data-analysis/      # Data pipeline, telemetry parsers, and figure generators
│   ├── scripts/        # Python ETL & statistics scripts (01 to 05)
│   │   ├── 01_parse_k6.py
│   │   ├── 02_parse_jfr.py
│   │   ├── 03_consolidate.py
│   │   ├── 04_generate_figures.py
│   │   └── 05_statistical_tests.py
│   ├── raw-data/       # Collected telemetry partitioned by scenario/strategy [ignored]
│   │   ├── nominal/    # {hibernate, hibernate-dto, jdbc} / {k6, jfr}
│   │   └── saturation/ # {hibernate, hibernate-dto, jdbc} / {k6, jfr}
│   ├── processed-data/ # Extracted metrics, consolidated datasets, and test results [ignored]
│   │   ├── dataset_final.csv
│   │   ├── shapiro_wilk_results.csv
│   │   └── wilcoxon_comparisons.csv
│   └── figures/        # Rendered publication charts (300 DPI) [ignored]
│       ├── nominal/    # Individual run-by-run stability charts
│       ├── saturation/ # Individual run-by-run stability charts
│       └── comparisons/# Cross-scenario comparative charts and split boxplots
├── up-lab.sh           # Starts PostgreSQL container, checks readiness, and boots backend
├── down-lab.sh         # Shuts down JVM runtime and tears down database containers
├── run-battery.sh      # Executes warm-up and 10 benchmark iterations (--nominal | --saturation)
├── run-analysis.sh     # Resets derived data and executes the 5-stage Python analysis pipeline
├── run-all.sh          # Master orchestrator managing branch checkouts, runs, cooldowns, and analysis
├── requirements.txt    # Python dependencies (pandas, seaborn, matplotlib, scipy)
├── backend.log         # Cumulative JVM startup, health checks, and application logs [ignored]
├── database.log        # Cumulative PostgreSQL container logs [ignored]
├── load-tests.log      # Cumulative k6 execution and JFR profiling logs [ignored]
├── data-analysis.log   # Cumulative dataset parsing and statistical logs [ignored]
└── README.md
```

---

## Environment Setup

Initialize the Python virtual environment and install analysis dependencies (including `scipy` for non-parametric inference):

```bash
python3 -m venv data-analysis/venv
source data-analysis/venv/bin/activate
pip install -r requirements.txt
deactivate
```

---

## Benchmark Workflow

Each persistence strategy is isolated on its dedicated Git branch: `hibernate`, `hibernate-dto`, and `jdbc`.

### Option A: Fully Automated Execution (Recommended)

Run the master orchestrator from any clean branch (e.g., `main`). It automatically manages Git checkouts, boots and tears down the test environment, runs warm-ups and dual-scenario batteries, enforces a 3-minute inter-strategy hardware thermal cooldown, and triggers the final data analysis:

```bash
chmod +x run-all.sh
./run-all.sh
```

---

### Option B: Manual Step-by-Step Execution

Alternatively, execute both workload scenarios (`--nominal` and `--saturation`) sequentially for each branch:

#### 1. Hibernate (Managed Entities)
```bash
git switch hibernate
./up-lab.sh
./run-battery.sh --nominal
./run-battery.sh --saturation
./down-lab.sh
```

*(Allow 2–3 minutes for thermal cooldown before proceeding)*

#### 2. Hibernate DTO (Projections)
```bash
git switch hibernate-dto
./up-lab.sh
./run-battery.sh --nominal
./run-battery.sh --saturation
./down-lab.sh
```

*(Allow 2–3 minutes for thermal cooldown)*

#### 3. Native JDBC
```bash
git switch jdbc
./up-lab.sh
./run-battery.sh --nominal
./run-battery.sh --saturation
./down-lab.sh
```

---

## Data Analysis & Statistical Validation

If executed manually via Option B, run the processing pipeline from any branch once all 60 benchmark iterations are completed:

```bash
./run-analysis.sh
```

The automated pipeline executes the following 5 stages:

1. **`01_parse_k6.py`:** Parses raw k6 execution CSVs, calculating sustained throughput (RPS) and latency percentiles (p50, p90, p95, p99).
2. **`02_parse_jfr.py`:** Invokes the JDK `jfr` CLI to extract HotSpot telemetry: Stop-the-World GC pause times, committed heap peak usage, and average JVM/host CPU load.
3. **`03_consolidate.py`:** Joins k6 and JFR metrics on the execution run key into a unified, tidy dataset (`data-analysis/processed-data/dataset_final.csv`).
4. **`04_generate_figures.py`:** Produces 300 DPI publication charts:
   * **Stability Plots (`figures/{nominal,saturation}/{strategy}/`):** Run-by-run stationarity across latency, throughput, GC pauses, and CPU load.
   * **Global Comparative Charts (`figures/comparisons/`):** Grouped bar charts comparing throughput, p95 tail latency, accumulated GC pauses, and CPU load across scenarios.
5. **`05_statistical_tests.py`:** Conducts formal inferential statistical analysis:
   * **Normality Testing:** Evaluates empirical distributions using the **Shapiro-Wilk** test, exporting results to `processed-data/shapiro_wilk_results.csv`.
   * **Hypothesis Testing:** Performs non-parametric pairwise comparisons via **Mann-Whitney U** (independent rank sums) and **Wilcoxon Signed-Rank** (paired iteration differences), exporting significance assessments to `processed-data/wilcoxon_comparisons.csv`.
   * **Decoupled Tail Latency Boxplot:** Renders `figures/comparisons/distribution_latency_p95_split.png`, isolating Nominal (2.5–8.5 ms) and Saturation (665–750 ms) scales to expose variance, JIT warmup outliers, and architectural performance tiers without visual compression.
