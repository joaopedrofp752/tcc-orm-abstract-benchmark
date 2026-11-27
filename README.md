# Persistence Layer Benchmark (Spring Boot 4.1.1 & Java 21)

A reproducible benchmark harness evaluating tail latency, sustained throughput, JVM Garbage Collection overhead, and connection pool contention across three persistence approaches — **Hibernate ORM (Managed Entities)**, **Hibernate DTO Projections**, and **Native JDBC** — running on **Java 21**, **Spring Boot 4.1.1 (Hibernate 7)**, and **PostgreSQL 17-Alpine** under two workload profiles:

* **Nominal:** 300 RPS (30 pre-allocated VUs / 90 max VUs)
* **Saturation:** 1,200 RPS (120 pre-allocated VUs / 360 max VUs)

---

## Repository & Branch Architecture

To preserve experimental isolation (*ceteris paribus*) and prevent classpath contamination across strategies, the repository separates shared orchestration from concrete persistence implementations:

* **`main` (Release `v1.0` Base):** Sterile baseline containing the database setup, load-testing scripts, master orchestrators, Python statistical pipeline, and a persistence-agnostic Spring Boot skeleton (`BenchmarkController` + `BenchmarkService` contract).
* **`hibernate`:** Isolated implementation using managed JPA entities (`BenchmarkPayload`) inside `@Transactional(readOnly = true)` mapped to `PayloadDTO` (`HibernateBenchmarkService`).
* **`hibernate-dto`:** Isolated implementation using JPQL constructor projections (`SELECT new ...PayloadDTO(...)`) bypassing persistence context hydration (`HibernateDtoBenchmarkService`).
* **`jdbc`:** Isolated implementation using native SQL queries via `JdbcTemplate` and `RowMapper` (`JdbcBenchmarkService`).

---

## Prerequisites

Ensure the following tools are installed and accessible in your `$PATH`:

* **JDK 21+** (must include native `jfr` and `jcmd` CLI utilities)
* **Docker & Docker Compose** (with `cgroups v2` enabled for PostgreSQL 17-Alpine resource confinement)
* **k6** (HTTP load testing engine)
* **Python 3.10+** (with `venv` support)
* **tmux** (recommended for persistent headless execution; integrates with `systemd-inhibit` when available)

---

## Project Structure

```text
.
├── backend/            # Spring Boot 4.1.1 (Hibernate 7) / Java 21 application
├── database/           # PostgreSQL 17-Alpine configuration, schemas, and compose file
├── load-tests/         # Parametrized k6 execution scripts (nominal / saturation / warmup)
├── data-analysis/      # Data pipeline, telemetry parsers, and figure generators
│   ├── scripts/        # Python ETL & inferential statistics scripts (01 to 05)
│   │   ├── create-venv.sh
│   │   ├── 01_parse_k6.py
│   │   ├── 02_parse_jfr.py
│   │   ├── 03_consolidate.py
│   │   ├── 04_generate_figures.py
│   │   └── 05_statistical_tests.py
│   ├── raw-data/       # Collected telemetry partitioned by scenario/strategy [ignored]
│   │   ├── nominal/    # {hibernate, hibernate-dto, jdbc} / {k6, jfr}
│   │   ├── saturation/ # {hibernate, hibernate-dto, jdbc} / {k6, jfr}
│   │   └── diagnostics/# Interleaved 1,200 RPS runs / {k6, jfr, telemetry}
│   ├── processed-data/ # Extracted metrics, consolidated datasets, and test results [ignored]
│   │   ├── dataset_final.csv
│   │   ├── diagnostics_dataset.csv
│   │   ├── shapiro_wilk_results.csv
│   │   └── mann_whitney_comparisons.csv
│   └── figures/        # Rendered publication charts (300 DPI, Portuguese labels) [ignored]
│       ├── nominal/    # Individual run-by-run stability charts
│       ├── saturation/ # Individual run-by-run stability charts
│       └── comparisons/# Cross-scenario comparative charts, split boxplots, and diagnostics
├── up-lab.sh           # Starts PostgreSQL 17-Alpine container, checks readiness, and boots backend
├── down-lab.sh         # Shuts down JVM runtime and tears down database containers/volumes
├── run-battery.sh      # Executes JIT warm-up and 10 benchmark iterations (--nominal | --saturation)
├── run-all.sh          # Stage 1 master orchestrator (60 primary black-box runs + analysis)
├── run-diagnostics.sh  # Stage 2 white-box orchestrator (30 interleaved saturation runs)
├── run-analysis.sh     # Validates Python venv, resets derived data, and runs the 5-stage pipeline
├── tmux-enter.sh       # Creates/attaches persistent tmux session with systemd-inhibit sleep lock
├── tmux-exit.sh        # Terminates tmux session and releases the system sleep/idle inhibitor
├── requirements.txt    # Python dependencies (pandas, seaborn, matplotlib, scipy)
├── backend.log         # Cumulative JVM startup, health checks, and application logs [ignored]
├── database.log        # Cumulative PostgreSQL container logs [ignored]
├── load-tests.log      # Cumulative k6 execution and JFR profiling logs [ignored]
├── diagnostics.log     # Cumulative interleaved diagnostic battery logs [ignored]
├── data-analysis.log   # Cumulative dataset parsing and statistical test logs [ignored]
├── LICENSE             # MIT License
└── README.md
```

---

## Environment Setup

`./run-analysis.sh` automatically checks and provisions the Python virtual environment via `data-analysis/scripts/create-venv.sh`. To initialize it manually beforehand:

```bash
./data-analysis/scripts/create-venv.sh
```

---

## Benchmark Workflow

For reproducible results on Linux workstations, switch to a multi-user TTY (`sudo systemctl isolate multi-user.target`), set the CPU governor to `performance` (`powerprofilesctl set performance`), and run inside the managed `tmux` session (`./tmux-enter.sh`).

### Stage 1: Primary Black-Box Benchmark (60 Runs)

#### Option A: Fully Automated Execution (Recommended)

Run the master orchestrator from any clean branch (e.g., `main`). It automatically manages Git checkouts across `hibernate`, `hibernate-dto`, and `jdbc`, boots and tears down the lab environment, runs JIT warm-ups and dual-scenario batteries (10 nominal + 10 saturation runs per strategy), enforces a 3-minute inter-strategy thermal cooldown, and triggers the data analysis pipeline:

```bash
./tmux-enter.sh
./run-all.sh
```

#### Option B: Manual Step-by-Step Execution

Alternatively, execute both workload scenarios (`--nominal` and `--saturation`) sequentially for each branch, allowing a 2–3 minute thermal cooldown between strategies:

```bash
# 1. Hibernate (Managed Entities)
git switch hibernate && ./up-lab.sh && ./run-battery.sh --nominal && ./run-battery.sh --saturation && ./down-lab.sh

# 2. Hibernate DTO (Projections)
git switch hibernate-dto && ./up-lab.sh && ./run-battery.sh --nominal && ./run-battery.sh --saturation && ./down-lab.sh

# 3. Native JDBC
git switch jdbc && ./up-lab.sh && ./run-battery.sh --nominal && ./run-battery.sh --saturation && ./down-lab.sh
```

---

### Stage 2: Complementary White-Box Saturation Diagnostics (30 Interleaved Runs)

Run separately after Stage 1 (allowing 5–15 minutes of idle thermal settling) to isolate internal bottlenecks under 1,200 RPS saturation without introducing observer bias into the primary dataset. `run-diagnostics.sh` executes 10 balanced interleaved rounds across `hibernate`, `hibernate-dto`, and `jdbc`, sampling HikariCP pool usage/acquisition/queue depth at 1 Hz via Spring Actuator, PostgreSQL 17-Alpine `cgroup v2` CPU quota/throttling, shared buffer cache hit ratio, and isolated `/proc` CPU ticks for the JVM and `k6`:

```bash
./tmux-enter.sh
./run-diagnostics.sh
./run-analysis.sh
./tmux-exit.sh
```

---

## Data Analysis & Statistical Validation

Whenever `./run-analysis.sh` is executed from any branch, it rebuilds `processed-data/` and `figures/` across 5 automated stages:

1. **`01_parse_k6.py`:** Parses raw `k6` execution CSVs across primary and diagnostic directories, extracting sustained throughput (RPS), dropped iterations, and latency percentiles ($p50$, $p90$, $p95$, $p99$).
2. **`02_parse_jfr.py`:** Invokes the JDK `jfr` CLI to extract HotSpot telemetry: Stop-the-World GC count and pause times, committed heap peak usage, and average JVM/host CPU load.
3. **`03_consolidate.py`:** Joins `k6`, `JFR`, and white-box telemetry JSONs into tidy datasets:
   * `processed-data/dataset_final.csv` (60 primary runs)
   * `processed-data/diagnostics_dataset.csv` (30 interleaved saturation diagnostic runs)
4. **`04_generate_figures.py`:** Produces 300 DPI publication charts:
   * **Stability Plots (`figures/{nominal,saturation}/{strategy}/`):** Run-by-run stationarity across latency, throughput, GC pauses, and CPU load.
   * **Global Comparative Charts (`figures/comparisons/`):** Grouped bar charts comparing throughput, $p95$ tail latency, accumulated GC pauses, and CPU load across scenarios, plus `diagnostics_mechanisms.png` (HikariCP connection hold time vs. PostgreSQL CPU quota).
5. **`05_statistical_tests.py`:** Conducts formal non-parametric inferential analysis:
   * **Normality Testing:** Evaluates empirical distributions using the **Shapiro-Wilk** test (`processed-data/shapiro_wilk_results.csv`).
   * **Hypothesis Testing & Effect Size:** Performs independent pairwise comparisons via the **Mann-Whitney U** test with **Holm-Bonferroni** family-wise error correction, **Cliff's delta ($\delta$)** effect size, and 95% bootstrap confidence intervals (`processed-data/mann_whitney_comparisons.csv`).
   * **Decoupled Tail Latency Boxplot:** Renders `figures/comparisons/distribution_latency_p95_split.png`, isolating Nominal (2.5–8.5 ms) and Saturation (665–750 ms) scales to expose variance, JIT warmup outliers, and architectural performance tiers without visual compression.

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
