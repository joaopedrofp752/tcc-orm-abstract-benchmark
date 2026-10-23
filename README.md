# Persistence Layer Benchmark (Spring Boot & Java 21)

A reproducible benchmark harness evaluating latency, throughput, and JVM resource consumption across three persistence approaches: **Hibernate ORM**, **Hibernate DTO projections**, and **Native JDBC** under two distinct workload profiles:
* **Nominal:** 300 RPS (30 pre-allocated VUs / 90 max VUs)
* **Saturation:** 1,200 RPS (120 pre-allocated VUs / 360 max VUs)

---

## Prerequisites

Ensure the following tools are installed and accessible in your `$PATH`:

* **JDK 21+** (must include the native `jfr` and `jcmd` CLI utilities)
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
│   ├── scripts/        # Python ETL scripts (01_parse_k6, 02_parse_jfr, 03_consolidate, 04_figures)
│   ├── raw-data/       # Collected telemetry partitioned by scenario/strategy [ignored]
│   │   ├── nominal/    # {hibernate, hibernate-dto, jdbc} / {k6, jfr}
│   │   └── saturation/ # {hibernate, hibernate-dto, jdbc} / {k6, jfr}
│   ├── processed-data/ # Extracted metrics and dataset_final.csv [ignored]
│   │   ├── nominal/
│   │   ├── saturation/
│   │   └── dataset_final.csv
│   └── figures/        # Rendered charts (300 DPI) [ignored]
│       ├── nominal/
│       ├── saturation/
│       └── comparisons/
├── up-lab.sh           # Starts PostgreSQL, attaches database logging, and boots backend
├── down-lab.sh         # Shuts down JVM runtime and tears down database containers
├── run-battery.sh      # Executes warm-up and 10 benchmark iterations (--nominal | --saturation)
├── run-analysis.sh     # Resets derived data and runs the 4-stage Python analysis pipeline
├── backend.log         # Cumulative JVM startup, health checks, and application logs [ignored]
├── database.log        # Cumulative PostgreSQL container logs [ignored]
├── load-tests.log      # Cumulative k6 execution and JFR profiling logs [ignored]
├── data-analysis.log   # Cumulative dataset parsing and figure generation logs [ignored]
└── README.md
```

---

## Environment Setup

Initialize the Python virtual environment and install analysis dependencies:

```bash
python3 -m venv data-analysis/venv
source data-analysis/venv/bin/activate
pip install -r data-analysis/requirements.txt
deactivate
```

---

## Benchmark Workflow

Each persistence strategy is isolated on its own Git branch: `hibernate`, `hibernate-dto`, and `jdbc`.

Execute both workload scenarios (`--nominal` and `--saturation`) sequentially for each branch:

### 1. Hibernate (Managed Entities)
```bash
git switch hibernate
./up-lab.sh
./run-battery.sh --nominal
./run-battery.sh --saturation
./down-lab.sh
```

*(Allow 2–3 minutes for thermal cooldown before proceeding)*

### 2. Hibernate DTO (Projections)
```bash
git switch hibernate-dto
./up-lab.sh
./run-battery.sh --nominal
./run-battery.sh --saturation
./down-lab.sh
```

*(Allow 2–3 minutes for thermal cooldown)*

### 3. Native JDBC
```bash
git switch jdbc
./up-lab.sh
./run-battery.sh --nominal
./run-battery.sh --saturation
./down-lab.sh
```

---

## Data Analysis

Once all benchmark iterations are completed across the three branches (totaling 60 experimental runs), execute the processing pipeline from any branch:

```bash
./run-analysis.sh
```

The automated pipeline performs the following steps:
1. Cleans and extracts latency percentiles from raw k6 CSVs into intermediate summaries.
2. Parses binary JFR recordings to calculate total GC pauses, heap peaks, and CPU utilization.
3. Consolidates all metrics into a single tidy dataset (`dataset_final.csv`) with explicit `scenario` and `strategy` columns.
4. Generates high-resolution publication charts:
   * **Individual Stability Plots:** `data-analysis/figures/{nominal,saturation}/{strategy}/`
   * **Global Comparative Charts:** `data-analysis/figures/comparisons/` (side-by-side grouped visualizations for latency, throughput, GC pause times, and CPU consumption).
