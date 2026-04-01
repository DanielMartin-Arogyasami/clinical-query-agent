"""
Evaluation metrics. [FIX M6] Explicit field mapping instead of string replacement.
"""
from __future__ import annotations
from dataclasses import dataclass


# [FIX M6] Explicit field name mapping between ground truth and detection
GT_TO_DETECTED_FIELD_MAP = {"subject": "subject_id"}


@dataclass
class AnomalyDetectionMetrics:
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0

    @property
    def precision(self) -> float:
        d = self.true_positives + self.false_positives
        return self.true_positives / d if d > 0 else 0.0

    @property
    def recall(self) -> float:
        d = self.true_positives + self.false_negatives
        return self.true_positives / d if d > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    @property
    def specificity(self) -> float:
        d = self.true_negatives + self.false_positives
        return self.true_negatives / d if d > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "specificity": round(self.specificity, 4),
        }


@dataclass
class RetrievalMetrics:
    relevant_retrieved: int = 0
    total_retrieved: int = 0
    total_relevant: int = 0

    @property
    def recall_at_k(self) -> float:
        return self.relevant_retrieved / self.total_relevant if self.total_relevant > 0 else 0.0

    @property
    def precision_at_k(self) -> float:
        return self.relevant_retrieved / self.total_retrieved if self.total_retrieved > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "recall_at_k": round(self.recall_at_k, 4),
            "precision_at_k": round(self.precision_at_k, 4),
        }


def evaluate_anomaly_detection(
    detected: list[dict],
    ground_truth: list[dict],
    match_fields: tuple[str, ...] = ("subject", "type"),
) -> AnomalyDetectionMetrics:
    """[FIX M6] Uses explicit field map instead of string replacement hack."""
    def make_key(item: dict, is_detected: bool) -> tuple:
        keys = []
        for f in match_fields:
            if is_detected:
                mapped = GT_TO_DETECTED_FIELD_MAP.get(f, f)
                keys.append(item.get(mapped, ""))
            else:
                keys.append(item.get(f, ""))
        return tuple(keys)

    gt_keys = {make_key(a, False) for a in ground_truth}
    det_keys = {make_key(a, True) for a in detected}
    tp = len(gt_keys & det_keys)
    fp = len(det_keys - gt_keys)
    fn = len(gt_keys - det_keys)
    return AnomalyDetectionMetrics(true_positives=tp, false_positives=fp, false_negatives=fn)
