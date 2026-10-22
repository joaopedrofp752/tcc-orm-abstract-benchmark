#!/usr/bin/env python3
"""
02_parse_jfr.py - Parse binary Java Flight Recorder (.jfr) files via JDK CLI.
"""

import json
import re
import subprocess
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "raw-data"
PROCESSED_DIR = BASE_DIR / "processed-data"

STRATEGIES = ["hibernate", "hibernate-dto", "jdbc"]


def parse_iso_duration_to_ms(duration_val) -> float:
    """
    Converts ISO-8601 duration format (e.g. 'PT0.0123S', 'PT15.4MS') or numbers to ms.
    """
    if isinstance(duration_val, (int, float)):
        return float(duration_val)

    if not isinstance(duration_val, str):
        return 0.0

    # Match seconds with decimals
    match = re.search(r"PT(?:(\d+)M)?(?:([\d.]+)S)?", duration_val)
    if match:
        minutes = float(match.group(1) or 0)
        seconds = float(match.group(2) or 0)
        return (minutes * 60 + seconds) * 1000.0

    return 0.0


def extract_jfr_metrics(jfr_file: Path) -> dict:
    """
    Invokes JDK 'jfr print --json' and aggregates GC, CPU, and Memory telemetry.
    """
    events_to_query = "jdk.GarbageCollection,jdk.CPULoad,jdk.GCHeapSummary"
    cmd = [
        "jfr", "print",
        "--json",
        "--events", events_to_query,
        str(jfr_file)
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        raw_json = json.loads(proc.stdout)
    except subprocess.CalledProcessError as e:
        print(f"  ! jfr command failed for {jfr_file.name}: {e.stderr[:200]}")
        return {}
    except json.JSONDecodeError as e:
        print(f"  ! Failed to decode JFR JSON for {jfr_file.name}: {e}")
        return {}

    events = raw_json.get("recording", {}).get("events", [])

    gc_durations = []
    cpu_jvm_samples = []
    cpu_machine_samples = []
    heap_used_samples = []

    for event in events:
        event_type = event.get("type")
        values = event.get("values", {})

        # 1. Garbage Collection Pauses
        if event_type == "jdk.GarbageCollection":
            duration = values.get("sumOfPauses", values.get("duration", 0))
            pause_ms = parse_iso_duration_to_ms(duration)
            gc_durations.append(pause_ms)

        # 2. CPU Telemetry
        elif event_type == "jdk.CPULoad":
            # JVM usage is user + system load
            jvm_user = values.get("jvmUser", 0.0)
            jvm_system = values.get("jvmSystem", 0.0)
            machine_total = values.get("machineTotal", 0.0)

            cpu_jvm_samples.append((jvm_user + jvm_system) * 100.0)
            cpu_machine_samples.append(machine_total * 100.0)

        # 3. Heap Memory Usage
        elif event_type == "jdk.GCHeapSummary":
            heap_used_bytes = values.get("heapUsed", 0)
            if heap_used_bytes > 0:
                heap_used_samples.append(heap_used_bytes / (1024 * 1024))  # Convert to MB

    gc_count = len(gc_durations)
    total_gc_pause_ms = sum(gc_durations)
    avg_gc_pause_ms = (total_gc_pause_ms / gc_count) if gc_count > 0 else 0.0

    avg_cpu_jvm = (sum(cpu_jvm_samples) / len(cpu_jvm_samples)) if cpu_jvm_samples else 0.0
    avg_cpu_machine = (sum(cpu_machine_samples) / len(cpu_machine_samples)) if cpu_machine_samples else 0.0
    peak_heap_mb = max(heap_used_samples) if heap_used_samples else 0.0

    return {
        "run": jfr_file.stem,
        "gc_count": int(gc_count),
        "gc_total_pause_ms": round(total_gc_pause_ms, 2),
        "gc_avg_pause_ms": round(avg_gc_pause_ms, 2),
        "cpu_jvm_avg_pct": round(avg_cpu_jvm, 2),
        "cpu_machine_avg_pct": round(avg_cpu_machine, 2),
        "heap_used_peak_mb": round(peak_heap_mb, 2),
    }


def process_strategy_jfr(strategy: str) -> None:
    jfr_dir = RAW_DIR / strategy / "jfr"
    if not jfr_dir.exists():
        print(f"[-] Directory not found: {jfr_dir} (skipping)")
        return

    jfr_files = sorted(jfr_dir.glob("run_*.jfr"))
    if not jfr_files:
        print(f"[-] No JFR files found for strategy: {strategy} (skipping)")
        return

    print(f"[+] Processing {len(jfr_files)} JFR recordings for '{strategy}'...")
    records = []

    for file_path in jfr_files:
        metrics = extract_jfr_metrics(file_path)
        if metrics:
            records.append(metrics)

    if records:
        out_dir = PROCESSED_DIR / strategy
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "jfr_metrics.csv"

        result_df = pd.DataFrame(records)
        result_df.to_csv(out_file, index=False)
        print(f"  -> Saved JFR metrics to: {out_file.relative_to(BASE_DIR)}")


def main():
    for strategy in STRATEGIES:
        process_strategy_jfr(strategy)


if __name__ == "__main__":
    main()
