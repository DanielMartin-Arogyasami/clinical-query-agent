"""
Query Generation Agent — anomaly detection and query creation.
[FIX C2] Uses invoke_llm_json. [FIX H1] Batched query text generation.
[FIX M1] Specific exceptions. [FIX L1] Uses input_required_variables.
"""
from __future__ import annotations
import json
import structlog
from pydantic import ValidationError
from src.agents.base import BaseAgent
from src.models.schemas import AgentName, DataAnomaly, DataQuery, Severity
from src.tools.validation_tools import (
    check_vital_sign_ranges,
    check_temporal_consistency,
    check_cross_field_bp,
    check_missing_required,
)

logger = structlog.get_logger(__name__)

CONTEXTUAL_QUERY_PROMPT = """You are analysing clinical trial data for anomalies that rule-based checks may miss.

RULE-BASED ANOMALIES ALREADY DETECTED:
{rule_anomalies_json}

DATA SUMMARY:
{data_summary}

PROTOCOL CONTEXT:
{context}

Identify ADDITIONAL anomalies (patterns, clinically suspicious values, site-level issues).
Output ONLY this JSON (no markdown):
{{"additional_anomalies": [{{"subject_id": "...", "visit": "...", "domain": "...", "field_name": "...", "observed_value": "...", "expected_value": "...", "anomaly_type": "pattern", "severity": "medium", "confidence": 0.0, "reasoning": "..."}}]}}
If none found, return {{"additional_anomalies": []}}."""

BATCH_QUERY_PROMPT = """Generate clear, professional data queries for these anomalies.

ANOMALIES:
{anomalies_json}

PROTOCOL CONTEXT:
{context}

Output ONLY this JSON (no markdown):
{{"queries": [{{"anomaly_id": "...", "query_text": "Clear actionable query for site", "suggested_resolution": "or null", "severity": "medium"}}]}}"""


class QueryGenerationAgent(BaseAgent):
    agent_name = AgentName.QUERY_GENERATION

    def run(self, state: dict) -> dict:
        data_path = state.get("data_path")
        df = state.get("dataframe")
        if df is None and data_path:
            from src.tools.data_tools import load_sdtm_dataset
            df = load_sdtm_dataset(data_path)
        if df is None or df.empty:
            logger.warning("query_gen.no_data")
            return state

        domain = state.get("domain", "VS")
        all_anomalies: list[DataAnomaly] = []

        # Phase 1: Deterministic rule-based checks
        if domain == "VS":
            all_anomalies.extend(check_vital_sign_ranges(df))
            all_anomalies.extend(check_cross_field_bp(df))
            if "RFSTDTC" in df.columns:
                all_anomalies.extend(check_temporal_consistency(df))
            from src.models.clinical import SDTM_DOMAINS
            # [FIX L1] Use input_required_variables instead of all required
            required = SDTM_DOMAINS.get("VS", {}).get(
                "input_required_variables",
                SDTM_DOMAINS.get("VS", {}).get("required_variables", []),
            )
            present_required = [c for c in required if c in df.columns]
            all_anomalies.extend(check_missing_required(df, present_required, domain="VS"))

        logger.info("query_gen.rule_based", num_anomalies=len(all_anomalies))

        # Phase 2: LLM contextual analysis
        chunks = self.retrieve_context(f"protocol visit schedule {domain} data quality criteria")
        context = self.format_context(chunks)
        from src.tools.data_tools import compute_dataset_summary
        data_summary = json.dumps(compute_dataset_summary(df), indent=2, default=str)

        try:
            result = self.invoke_llm_json([
                {"role": "system", "content": self._prompt_template},
                {"role": "user", "content": CONTEXTUAL_QUERY_PROMPT.format(
                    rule_anomalies_json=json.dumps([a.model_dump() for a in all_anomalies[:20]], default=str),
                    data_summary=data_summary, context=context,
                )},
            ])
            for extra in result.get("additional_anomalies", []):
                if extra.get("confidence", 0) >= self.confidence_threshold:
                    all_anomalies.append(DataAnomaly(
                        subject_id=extra["subject_id"], visit=extra["visit"],
                        domain=extra.get("domain", domain), field_name=extra["field_name"],
                        observed_value=str(extra["observed_value"]),
                        expected_value=str(extra.get("expected_value", "")),
                        anomaly_type=extra.get("anomaly_type", "pattern"),
                        severity=Severity(extra.get("severity", "medium")),
                        confidence=extra["confidence"],
                        evidence_citations=[extra.get("reasoning", "")],
                    ))
        except (json.JSONDecodeError, KeyError, ValidationError) as e:
            logger.warning("query_gen.llm_contextual_error", error=str(e))

        # Phase 3: Batched query text generation [FIX H1]
        queries = self._generate_queries_batched(all_anomalies, context)

        state["anomalies"] = [a.model_dump() for a in all_anomalies]
        state["queries"] = [q.model_dump() for q in queries]
        state["query_generation_status"] = "completed"
        self.log_action(
            action="generate_queries",
            inputs={"data_rows": len(df), "domain": domain},
            outputs={"num_anomalies": len(all_anomalies), "num_queries": len(queries)},
            citations=[c.metadata.get("section_heading", c.chunk_id) for c in chunks],
            confidence=sum(a.confidence for a in all_anomalies) / max(len(all_anomalies), 1),
        )
        return state

    def _generate_queries_batched(self, anomalies: list[DataAnomaly], context: str) -> list[DataQuery]:
        """Generate query texts in batches of 15 to reduce API calls. [FIX H1]"""
        BATCH_SIZE = 15
        all_queries: list[DataQuery] = []

        for i in range(0, len(anomalies), BATCH_SIZE):
            batch = anomalies[i : i + BATCH_SIZE]
            batch_dicts = [
                {
                    "anomaly_id": a.anomaly_id, "subject_id": a.subject_id,
                    "visit": a.visit, "field_name": a.field_name,
                    "observed_value": a.observed_value, "expected_value": a.expected_value,
                    "anomaly_type": a.anomaly_type, "severity": a.severity.value,
                }
                for a in batch
            ]
            try:
                result = self.invoke_llm_json([
                    {"role": "system", "content": self._prompt_template},
                    {"role": "user", "content": BATCH_QUERY_PROMPT.format(
                        anomalies_json=json.dumps(batch_dicts, default=str),
                        context=context[:3000],
                    )},
                ])
                query_map = {q["anomaly_id"]: q for q in result.get("queries", [])}
                for a in batch:
                    q_data = query_map.get(a.anomaly_id, {})
                    all_queries.append(DataQuery(
                        anomaly_id=a.anomaly_id, subject_id=a.subject_id,
                        visit=a.visit, domain=a.domain, field_name=a.field_name,
                        query_text=q_data.get("query_text", self._fallback_query_text(a)),
                        severity=a.severity, confidence=a.confidence,
                        suggested_resolution=q_data.get("suggested_resolution"),
                        evidence_citations=a.evidence_citations,
                    ))
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("query_gen.batch_error", error=str(e), batch_start=i)
                for a in batch:
                    all_queries.append(DataQuery(
                        anomaly_id=a.anomaly_id, subject_id=a.subject_id,
                        visit=a.visit, domain=a.domain, field_name=a.field_name,
                        query_text=self._fallback_query_text(a),
                        severity=a.severity, confidence=a.confidence,
                        evidence_citations=a.evidence_citations,
                    ))
        return all_queries

    @staticmethod
    def _fallback_query_text(anomaly: DataAnomaly) -> str:
        return (
            f"The value of {anomaly.field_name} ({anomaly.observed_value}) "
            f"for Subject {anomaly.subject_id} at {anomaly.visit} is flagged as "
            f"{anomaly.anomaly_type}. Expected: {anomaly.expected_value}. Please verify."
        )
