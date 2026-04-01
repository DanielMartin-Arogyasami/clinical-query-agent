"""Benchmark suite (Section 8.3)."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass
import pandas as pd
from evaluation.metrics import evaluate_anomaly_detection, AnomalyDetectionMetrics
from src.tools.validation_tools import (
    check_vital_sign_ranges,
    check_temporal_consistency,
    check_cross_field_bp,
    check_missing_required,
)


@dataclass
class BenchmarkResult:
    benchmark_name: str
    method: str
    metrics: AnomalyDetectionMetrics
    latency_seconds: float
    details: dict

    def to_dict(self) -> dict:
        return {
            "benchmark": self.benchmark_name,
            "method": self.method,
            "metrics": self.metrics.to_dict(),
            "latency_seconds": round(self.latency_seconds, 3),
            "details": self.details,
        }


def run_anomaly_detection_benchmark(
    data_path: str = "data/synthetic/vs_anomalous.csv",
    ground_truth_path: str = "data/synthetic/ground_truth_anomalies.json",
) -> BenchmarkResult:
    df = pd.read_csv(data_path)
    with open(ground_truth_path, encoding="utf-8") as f:
        ground_truth = json.load(f)
    start = time.perf_counter()
    anomalies = []
    anomalies.extend(check_vital_sign_ranges(df))
    anomalies.extend(check_temporal_consistency(df))
    anomalies.extend(check_cross_field_bp(df))
    from src.models.clinical import SDTM_DOMAINS
    required = SDTM_DOMAINS["VS"].get("input_required_variables", [])
    present = [c for c in required if c in df.columns]
    anomalies.extend(check_missing_required(df, present, domain="VS"))
    elapsed = time.perf_counter() - start
    detected = [{"subject_id": a.subject_id, "type": a.anomaly_type} for a in anomalies]
    metrics = evaluate_anomaly_detection(
        detected=detected, ground_truth=ground_truth, match_fields=("subject", "type"),
    )
    type_breakdown = {}
    for atype in ["out_of_range", "temporal", "missing", "cross_field"]:
        type_breakdown[atype] = {
            "ground_truth": sum(1 for a in ground_truth if a["type"] == atype),
            "detected": sum(1 for a in anomalies if a.anomaly_type == atype),
        }
    return BenchmarkResult(
        benchmark_name="anomaly_detection_vs",
        method="rule_based",
        metrics=metrics,
        latency_seconds=elapsed,
        details={
            "data_rows": len(df),
            "ground_truth_count": len(ground_truth),
            "detected_count": len(anomalies),
            "type_breakdown": type_breakdown,
        },
    )
