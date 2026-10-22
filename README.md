# Persistence Layer Benchmark (Spring Boot & Java 21)

A reproducible benchmark harness evaluating latency, throughput, and JVM resource consumption across three persistence approaches: **Hibernate ORM**, **Hibernate DTO projections**, and **Native JDBC**.

---

## Prerequisites

Ensure the following tools are installed and accessible in your `$PATH`:

* **JDK 21+** (must include the native `jfr` CLI tool)
* **Docker & Docker Compose** (for PostgreSQL)
* **k6** (HTTP load testing engine)
* **Python 3.10+** (with `venv` support)

---

## Project Structure

```text
.
├── backend/            # Spring Boot 3 / Java 21 application
├── database/           # PostgreSQL configuration and compose file
├── load-tests/         # k6 load testing scenarios
├── data-analysis/      # Data pipeline, telemetry parsers, and figure generators
│   ├── scripts/        # Python ETL scripts (k6, JFR, consolidation, visualization)
│   ├── raw-data/       # Collected raw metrics (.csv and .jfr) [ignored]
│   ├── processed-data/ # Cleaned datasets and dataset_final.csv [ignored]
│   └── figures/        # Rendered benchmark charts [ignored]
├── up-lab.sh           # Starts PostgreSQL and launches backend with JFR attached
├── run-battery.sh      # Runs 10 benchmark iterations for the active branch
├── down-lab.sh         # Shuts down the backend and terminates database containers
├── run-analysis.sh     # Orchestrates the Python data analysis pipeline
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

Execute the battery for each strategy sequentially:

### 1. Hibernate (Managed Entities)
```bash
git switch hibernate
./up-lab.sh
./run-battery.sh
./down-lab.sh
```

*(Allow 2–3 minutes for thermal cooldown before proceeding)*

### 2. Hibernate DTO (Projections)
```bash
git switch hibernate-dto
./up-lab.sh
./run-battery.sh
./down-lab.sh
```

*(Allow 2–3 minutes for thermal cooldown)*

### 3. Native JDBC
```bash
git switch jdbc
./up-lab.sh
./run-battery.sh
./down-lab.sh
```

---

## Data Analysis

Once all benchmark iterations are completed across the branches, run the unified pipeline from any branch:

```bash
./run-analysis.sh
```

The script will automatically parse the raw metrics, correlate JFR runtime events with k6 latency percentiles, and output:

* **Consolidated Dataset:** `data-analysis/processed-data/dataset_final.csv`
* **Generated Figures:** `data-analysis/figures/` (latency percentiles, throughput, and JVM telemetry charts)