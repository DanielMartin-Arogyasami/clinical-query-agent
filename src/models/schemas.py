"""
Pydantic models defining inter-agent data contracts.
[FIX M2] datetime.now(timezone.utc) replaces deprecated datetime.utcnow()
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class QueryStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"


class AgentName(str, Enum):
    SUPERVISOR = "supervisor"
    CRF_DESIGN = "crf_design"
    EDC_CONFIG = "edc_config"
    QUERY_GENERATION = "query_generation"
    DATA_CLEANING = "data_cleaning"
    PROGRAMMING = "programming"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"


# ── Protocol & CRF ──────────────────────────────────────────────


class ProtocolField(BaseModel):
    field_name: str
    crf_page: str
    visit: str | None = None
    data_type: str
    required: bool = True
    expected_range: str | None = None
    cdisc_variable: str | None = None
    source_section: str | None = None


class CRFSpecification(BaseModel):
    study_id: str
    protocol_version: str
    fields: list[ProtocolField]
    visit_schedule: dict[str, list[str]]
    extraction_confidence: float
    citations: list[str]


# ── EDC Configuration ───────────────────────────────────────────


class EditCheck(BaseModel):
    check_id: str = Field(default_factory=lambda: f"EC-{uuid.uuid4().hex[:8].upper()}")
    check_type: str
    target_field: str
    condition: str
    query_text: str
    severity: Severity = Severity.MEDIUM
    active: bool = True


class EDCConfiguration(BaseModel):
    study_id: str
    edit_checks: list[EditCheck]
    field_constraints: dict[str, dict[str, Any]]
    cross_form_rules: list[dict[str, Any]]
    generation_confidence: float


# ── Anomalies & Queries ─────────────────────────────────────────


class DataAnomaly(BaseModel):
    anomaly_id: str = Field(default_factory=lambda: f"AN-{uuid.uuid4().hex[:8].upper()}")
    subject_id: str
    visit: str
    domain: str
    field_name: str
    observed_value: str
    expected_value: str | None = None
    anomaly_type: str
    severity: Severity = Severity.MEDIUM
    confidence: float
    rule_reference: str | None = None
    evidence_citations: list[str] = Field(default_factory=list)


class DataQuery(BaseModel):
    query_id: str = Field(default_factory=lambda: f"QR-{uuid.uuid4().hex[:8].upper()}")
    anomaly_id: str
    subject_id: str
    visit: str
    domain: str
    field_name: str
    query_text: str
    severity: Severity = Severity.MEDIUM
    status: QueryStatus = QueryStatus.OPEN
    suggested_resolution: str | None = None
    evidence_citations: list[str] = Field(default_factory=list)
    confidence: float = 0.0


# ── Data Cleaning ───────────────────────────────────────────────


class CleaningAction(BaseModel):
    action_id: str = Field(default_factory=lambda: f"CA-{uuid.uuid4().hex[:8].upper()}")
    query_id: str
    action_type: str
    original_value: str
    new_value: str | None = None
    justification: str
    resolution_pattern: str | None = None
    confidence: float
    requires_human_approval: bool = True


# ── SDTM/ADaM ──────────────────────────────────────────────────


class SDTMMapping(BaseModel):
    source_field: str
    sdtm_domain: str
    sdtm_variable: str
    transformation: str
    controlled_terminology: str | None = None
    derivation_rule: str | None = None


class SDTMDataset(BaseModel):
    domain: str
    dataset_name: str
    label: str
    variables: list[SDTMMapping]
    record_count: int
    validation_status: str
    validation_messages: list[str] = Field(default_factory=list)


# ── Audit & Pipeline ───────────────────────────────────────────


class AuditEntry(BaseModel):
    entry_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent: AgentName
    action: str
    inputs_hash: str
    outputs_hash: str
    model_version: str
    prompt_template_hash: str
    retrieval_citations: list[str] = Field(default_factory=list)
    confidence: float | None = None
    human_approval: ApprovalStatus = ApprovalStatus.PENDING
    human_approver: str | None = None
    notes: str | None = None
