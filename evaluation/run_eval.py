"""Evaluation runner. [FIX M2] [FIX H6]"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings
from rich.console import Console
from rich.table import Table
from evaluation.benchmarks import run_anomaly_detection_benchmark

console = Console()


def main():
    settings.ensure_dirs()
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", default="all")
    parser.add_argument("--output", default="results/eval_results.json")
    args = parser.parse_args()
    results = []
    if args.benchmark in ("all", "anomaly_detection"):
        console.rule("[bold blue]Anomaly Detection Benchmark")
        if not Path("data/synthetic/vs_anomalous.csv").exists():
            console.print("[red]Run: python data/synthetic/generate_synthetic.py")
            return
        result = run_anomaly_detection_benchmark()
        results.append(result.to_dict())
        table = Table(title="Anomaly Detection — Rule-Based")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        for k, v in result.metrics.to_dict().items():
            table.add_row(k, str(v))
        table.add_row("latency_seconds", str(round(result.latency_seconds, 3)))
        console.print(table)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"timestamp": datetime.now(timezone.utc).isoformat(), "benchmarks": results}, f, indent=2)
    console.print(f"\n[green]OK: Results saved to {output_path}[/]")


if __name__ == "__main__":
    main()
