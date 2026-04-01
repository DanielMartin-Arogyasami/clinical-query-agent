"""Shared test fixtures. [NEW — from review recommendation]"""
from __future__ import annotations
import pytest
import pandas as pd
from src.audit.trail import AuditTrail


@pytest.fixture
def audit_trail(tmp_path):
    return AuditTrail(run_id="test-fixture", log_dir=str(tmp_path))


@pytest.fixture
def sample_vs_df():
    return pd.DataFrame([
        {"USUBJID": "S001", "VSTESTCD": "SYSBP", "VSSTRESN": 120, "VISIT": "V1", "VSDTC": "2024-02-01", "RFSTDTC": "2024-01-15"},
        {"USUBJID": "S001", "VSTESTCD": "DIABP", "VSSTRESN": 75, "VISIT": "V1", "VSDTC": "2024-02-01", "RFSTDTC": "2024-01-15"},
        {"USUBJID": "S002", "VSTESTCD": "SYSBP", "VSSTRESN": 250, "VISIT": "V1", "VSDTC": "2024-02-01", "RFSTDTC": "2024-01-15"},
        {"USUBJID": "S002", "VSTESTCD": "DIABP", "VSSTRESN": 130, "VISIT": "V1", "VSDTC": "2024-02-01", "RFSTDTC": "2024-01-15"},
    ])
