"""
End-to-end demo — rule-based anomaly detection on synthetic data.
[FIX M2] Uses datetime.now(timezone.utc). [FIX H6] Calls ensure_dirs().
[FIX L1] Uses input_required_variables.
"""
from __future__ import annotations
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from rich.console import Console
from rich.table import Table

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from src.audit.trail import AuditTrail
from src.models.schemas import AgentName
from src.tools.validation_tools import (
    check_vital_sign_ranges,
    check_temporal_consistency,
    check_cross_field_bp,
    check_missing_required,
)

console = Console()


def run_rule_based_demo():
    settings.ensure_dirs()
    console.rule("[bold blue]Multi-Agent Clinical Trial DM — Rule-Based Demo")

    data_dir = Path(settings.synthetic_data_dir)
    vs_path = data_dir / "vs_anomalous.csv"
    gt_path = data_dir / "ground_truth_anomalies.json"
    if not vs_path.exists():
        console.print("[red]Synthetic data not found. Run: python data/synthetic/generate_synthetic.py")
        return

    df = pd.read_csv(vs_path)
    with open(gt_path, encoding="utf-8") as f:
        ground_truth = json.load(f)
    console.print(f"\nLoaded {len(df)} VS records with {len(ground_truth)} injected anomalies\n")

    audit = AuditTrail(run_id=f"demo-rule-based-{uuid.uuid4().hex[:12]}")
    anomalies = []
    anomalies.extend(check_vital_sign_ranges(df))
    anomalies.extend(check_temporal_consistency(df))
    anomalies.extend(check_cross_field_bp(df))
    # [FIX L1] Only check true input-required fields
    from src.models.clinical import SDTM_DOMAINS
    required = SDTM_DOMAINS["VS"].get("input_required_variables", [])
    present_cols = [c for c in required if c in df.columns]
    anomalies.extend(check_missing_required(df, present_cols, domain="VS"))

    gt_types = {(a["subject"], a["visit"], a["type"]) for a in ground_truth}
    detected_types = {(a.subject_id, a.visit, a.anomaly_type) for a in anomalies}
    true_positives = gt_types & detected_types
    false_negatives = gt_types - detected_types
    false_positives = detected_types - gt_types
    precision = len(true_positives) / max(len(true_positives) + len(false_positives), 1)
    recall = len(true_positives) / max(len(gt_types), 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)

    table = Table(title="Anomaly Detection Results (Rule-Based)")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    for label, val in [
        ("Total detected", len(anomalies)),
        ("Ground truth", len(ground_truth)),
        ("True positives", len(true_positives)),
        ("False negatives", len(false_negatives)),
        ("False positives", len(false_positives)),
        ("Precision", f"{precision:.3f}"),
        ("Recall", f"{recall:.3f}"),
        ("F1", f"{f1:.3f}"),
    ]:
        table.add_row(str(label), str(val))
    console.print(table)

    type_table = Table(title="Detection by Anomaly Type")
    type_table.add_column("Type", style="cyan")
    type_table.add_column("Injected", style="yellow")
    type_table.add_column("Detected", style="green")
    for atype in ["out_of_range", "temporal", "missing", "cross_field"]:
        type_table.add_row(
            atype,
            str(sum(1 for a in ground_truth if a["type"] == atype)),
            str(sum(1 for a in anomalies if a.anomaly_type == atype)),
        )
    console.print(type_table)

    console.rule("[bold blue]Sample Queries")
    for a in anomalies[:5]:
        console.print(
            f"\n[yellow]Subject:[/] {a.subject_id}  [yellow]Visit:[/] {a.visit}  "
            f"[yellow]Type:[/] {a.anomaly_type}  [yellow]Severity:[/] {a.severity.value}"
        )
        console.print(f"  {a.field_name} = {a.observed_value} (expected: {a.expected_value})")

    audit.log_action(
        agent=AgentName.QUERY_GENERATION, action="rule_based_anomaly_detection",
        inputs={"data_rows": len(df), "domain": "VS"},
        outputs={"num_anomalies": len(anomalies), "precision": precision, "recall": recall, "f1": f1},
        model_version="rule-based-v1.0", prompt_template="N/A", confidence=1.0,
    )
    console.print(f"\nAudit log: {audit.export_summary()['log_file']}")

    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    with open(results_dir / "demo_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": "rule_based",
            "metrics": {
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "tp": len(true_positives),
                "fn": len(false_negatives),
                "fp": len(false_positives),
            },
        }, f, indent=2)
    console.print("[green]OK: Results saved to results/demo_results.json[/]")


if __name__ == "__main__":
    run_rule_based_demo()
