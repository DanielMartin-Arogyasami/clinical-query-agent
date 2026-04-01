"""
Data validation tools — vectorised pandas operations.
[FIX H2] All iterrows() replaced with vectorised operations.
[FIX L1] Missing-required check uses input_required_variables.
"""
from __future__ import annotations
import pandas as pd
from src.models.schemas import DataAnomaly, Severity
from src.models.clinical import VITAL_SIGN_RANGES


def check_vital_sign_ranges(
    df: pd.DataFrame,
    subject_col: str = "USUBJID",
    test_col: str = "VSTESTCD",
    value_col: str = "VSSTRESN",
    visit_col: str = "VISIT",
) -> list[DataAnomaly]:
    """Vectorised vital sign range check. [FIX H2]"""
    anomalies = []
    for test_code, ref in VITAL_SIGN_RANGES.items():
        mask = df[test_col].astype(str).str.upper() == test_code
        subset = df[mask].copy()
        if subset.empty:
            continue
        vals = pd.to_numeric(subset[value_col], errors="coerce")
        critical_mask = (vals < ref.critical_low) | (vals > ref.critical_high)
        abnormal_mask = ((vals < ref.normal_low) | (vals > ref.normal_high)) & ~critical_mask
        nan_mask = vals.isna()

        for idx in subset.index[critical_mask & ~nan_mask]:
            anomalies.append(DataAnomaly(
                subject_id=str(subset.at[idx, subject_col]),
                visit=str(subset.at[idx, visit_col]),
                domain="VS", field_name=test_code,
                observed_value=str(vals.at[idx]),
                expected_value=f"{ref.normal_low}-{ref.normal_high} {ref.unit}",
                anomaly_type="out_of_range", severity=Severity.CRITICAL,
                confidence=0.95,
                rule_reference=f"VS range check: {ref.test_name} [{ref.normal_low}-{ref.normal_high}]",
            ))
        for idx in subset.index[abnormal_mask & ~nan_mask]:
            anomalies.append(DataAnomaly(
                subject_id=str(subset.at[idx, subject_col]),
                visit=str(subset.at[idx, visit_col]),
                domain="VS", field_name=test_code,
                observed_value=str(vals.at[idx]),
                expected_value=f"{ref.normal_low}-{ref.normal_high} {ref.unit}",
                anomaly_type="out_of_range", severity=Severity.HIGH,
                confidence=0.95,
                rule_reference=f"VS range check: {ref.test_name} [{ref.normal_low}-{ref.normal_high}]",
            ))
    return anomalies


def check_temporal_consistency(
    df: pd.DataFrame,
    date_col: str = "VSDTC",
    consent_date_col: str = "RFSTDTC",
    subject_col: str = "USUBJID",
    visit_col: str = "VISIT",
    domain: str = "VS",
) -> list[DataAnomaly]:
    """Vectorised temporal consistency check. [FIX H2]"""
    if date_col not in df.columns or consent_date_col not in df.columns:
        return []
    dates = pd.to_datetime(df[date_col], errors="coerce")
    consents = pd.to_datetime(df[consent_date_col], errors="coerce")
    valid = dates.notna() & consents.notna()
    before_consent = valid & (dates < consents)

    anomalies = []
    for idx in df.index[before_consent]:
        anomalies.append(DataAnomaly(
            subject_id=str(df.at[idx, subject_col]),
            visit=str(df.at[idx, visit_col]),
            domain=domain, field_name=date_col,
            observed_value=str(df.at[idx, date_col]),
            expected_value=f">= {df.at[idx, consent_date_col]}",
            anomaly_type="temporal", severity=Severity.HIGH,
            confidence=0.99,
            rule_reference=f"Temporal check: {date_col} >= {consent_date_col}",
        ))
    return anomalies


def check_cross_field_bp(
    df: pd.DataFrame,
    subject_col: str = "USUBJID",
    visit_col: str = "VISIT",
) -> list[DataAnomaly]:
    """Vectorised cross-field BP check. [FIX H2]"""
    vs_bp = df[df["VSTESTCD"].isin(["SYSBP", "DIABP"])].copy()
    if vs_bp.empty:
        return []
    pivot = vs_bp.pivot_table(
        index=[subject_col, visit_col], columns="VSTESTCD", values="VSSTRESN", aggfunc="first"
    )
    if "SYSBP" not in pivot.columns or "DIABP" not in pivot.columns:
        return []

    valid = pivot["SYSBP"].notna() & pivot["DIABP"].notna()
    bad = valid & (pivot["DIABP"] >= pivot["SYSBP"])

    anomalies = []
    for (subj, visit) in pivot.index[bad]:
        sys_val = pivot.loc[(subj, visit), "SYSBP"]
        dia_val = pivot.loc[(subj, visit), "DIABP"]
        anomalies.append(DataAnomaly(
            subject_id=str(subj), visit=str(visit),
            domain="VS", field_name="DIABP",
            observed_value=f"DIABP={dia_val}, SYSBP={sys_val}",
            expected_value="DIABP < SYSBP",
            anomaly_type="cross_field", severity=Severity.HIGH,
            confidence=0.99,
            rule_reference="Cross-field check: Diastolic BP < Systolic BP",
        ))
    return anomalies


def check_missing_required(
    df: pd.DataFrame,
    required_cols: list[str],
    subject_col: str = "USUBJID",
    visit_col: str = "VISIT",
    domain: str = "VS",
) -> list[DataAnomaly]:
    """Vectorised missing-required check. [FIX H2] [FIX L1]"""
    anomalies = []
    for col in required_cols:
        if col not in df.columns:
            continue
        missing_mask = df[col].isna() | (df[col].astype(str).str.strip() == "")
        for idx in df.index[missing_mask]:
            anomalies.append(DataAnomaly(
                subject_id=str(df.at[idx, subject_col]),
                visit=str(df.at[idx, visit_col]),
                domain=domain, field_name=col,
                observed_value="MISSING",
                expected_value="Non-empty value required",
                anomaly_type="missing", severity=Severity.MEDIUM,
                confidence=1.0,
                rule_reference=f"Presence check: {col} is required",
            ))
    return anomalies
