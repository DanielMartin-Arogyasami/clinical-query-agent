"""Integration tests."""
from __future__ import annotations
import json
import pytest
from src.utils.helpers import parse_llm_json


class TestParseLLMJson:
    """[FIX C2] Test the JSON parser that handles LLM output quirks."""

    def test_clean_json(self):
        assert parse_llm_json('{"key": "value"}') == {"key": "value"}

    def test_markdown_fences(self):
        raw = '```json\n{"key": "value"}\n```'
        assert parse_llm_json(raw) == {"key": "value"}

    def test_preamble_text(self):
        raw = 'Here is the JSON output:\n\n{"key": "value"}\n\nLet me know if you need changes.'
        assert parse_llm_json(raw) == {"key": "value"}

    def test_no_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_llm_json("No JSON here at all")


class TestSyntheticDataGeneration:
    def test_generate(self):
        import numpy as np
        from data.synthetic.generate_synthetic import generate_clean_vs_data, _generate_consent_dates
        rng = np.random.default_rng(42)
        consent_dates = _generate_consent_dates(rng)
        df = generate_clean_vs_data(rng, consent_dates)
        assert len(df) > 0
        assert "VSTESTCD" in df.columns

    def test_inject_anomalies(self):
        import numpy as np
        from data.synthetic.generate_synthetic import generate_clean_vs_data, inject_anomalies, _generate_consent_dates
        rng = np.random.default_rng(42)
        consent_dates = _generate_consent_dates(rng)
        df = generate_clean_vs_data(rng, consent_dates)
        _, gt = inject_anomalies(df, rng)
        assert len(gt) >= 15
        assert {"out_of_range", "temporal", "missing"} <= {a["type"] for a in gt}


class TestValidationTools:
    def test_range_check(self, sample_vs_df):
        from src.tools.validation_tools import check_vital_sign_ranges
        anomalies = check_vital_sign_ranges(sample_vs_df)
        subjects = {a.subject_id for a in anomalies}
        assert "S002" in subjects  # 250 SYSBP is out of range

    def test_cross_field_bp(self):
        import pandas as pd
        from src.tools.validation_tools import check_cross_field_bp
        df = pd.DataFrame([
            {"USUBJID": "S001", "VSTESTCD": "SYSBP", "VSSTRESN": 120, "VISIT": "V1"},
            {"USUBJID": "S001", "VSTESTCD": "DIABP", "VSSTRESN": 130, "VISIT": "V1"},
        ])
        assert len(check_cross_field_bp(df)) == 1
