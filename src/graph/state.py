"""
Pipeline state schema. [FIX H4] TypedDict replaces dead ClinicalPipelineState.
[FIX M7] Removed unused MessagesState import.
"""
from __future__ import annotations
from typing import Any, TypedDict


class ClinicalPipelineState(TypedDict, total=False):
    """Typed shared state for the LangGraph pipeline. [FIX H4]"""
    study_id: str
    protocol_text: str
    data_path: str
    domain: str
    dataframe: Any  # pd.DataFrame — not JSON-serialisable, so Any
    crf_spec: dict | None
    edc_config: dict | None
    anomalies: list[dict]
    queries: list[dict]
    cleaning_actions: list[dict]
    sdtm_datasets: list[dict]
    current_stage_index: int
    next_agent: str
    gate_status: str
    pipeline_status: str
    crf_spec_status: str
    edc_config_status: str
    query_generation_status: str
    cleaning_status: str
    programming_status: str
