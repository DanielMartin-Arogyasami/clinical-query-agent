"""
CRF Design Agent — Protocol → CRF extraction.
[FIX C2] Uses invoke_llm_json. [FIX M1] Specific exception handling.
"""
from __future__ import annotations
import json
import structlog
from pydantic import ValidationError
from src.agents.base import BaseAgent
from src.models.schemas import AgentName, CRFSpecification, ProtocolField

logger = structlog.get_logger(__name__)

CRF_EXTRACTION_PROMPT = """Analyse the following protocol text and extract a structured CRF specification.

PROTOCOL TEXT:
{protocol_text}

RELEVANT CONTEXT:
{context}

Output ONLY this JSON (no markdown, no preamble):
{{"study_id": "...", "protocol_version": "...", "fields": [{{"field_name": "...", "crf_page": "...", "visit": "...", "data_type": "numeric|text|date|coded", "required": true, "expected_range": "...", "cdisc_variable": "SDTM variable", "source_section": "protocol section"}}], "visit_schedule": {{"Visit 1": ["Demographics", "Vital Signs"]}}, "extraction_confidence": 0.0, "citations": ["section refs"]}}"""


class CRFDesignAgent(BaseAgent):
    agent_name = AgentName.CRF_DESIGN

    def run(self, state: dict) -> dict:
        protocol_text = state.get("protocol_text", "")
        if not protocol_text:
            logger.warning("crf_design.no_protocol_text")
            return state

        chunks = self.retrieve_context("CDISC CDASH CRF design standards visit schedule")
        context = self.format_context(chunks)
        citations = [c.metadata.get("section_heading", c.chunk_id) for c in chunks]

        prompt = CRF_EXTRACTION_PROMPT.format(
            protocol_text=protocol_text[:8000],
            context=context,
        )

        try:
            result = self.invoke_llm_json([
                {"role": "system", "content": self._prompt_template},
                {"role": "user", "content": prompt},
            ])
            crf_spec = CRFSpecification(
                study_id=result.get("study_id", state.get("study_id", "UNKNOWN")),
                protocol_version=result.get("protocol_version", "1.0"),
                fields=[ProtocolField(**f) for f in result.get("fields", [])],
                visit_schedule=result.get("visit_schedule", {}),
                extraction_confidence=result.get("extraction_confidence", 0.0),
                citations=result.get("citations", []),
            )
        except json.JSONDecodeError as e:
            logger.error("crf_design.json_parse_error", error=str(e))
            crf_spec = CRFSpecification(
                study_id=state.get("study_id", "UNKNOWN"), protocol_version="1.0",
                fields=[], visit_schedule={}, extraction_confidence=0.0, citations=[],
            )
        except ValidationError as e:
            logger.error("crf_design.validation_error", error=str(e))
            crf_spec = CRFSpecification(
                study_id=state.get("study_id", "UNKNOWN"), protocol_version="1.0",
                fields=[], visit_schedule={}, extraction_confidence=0.0, citations=[],
            )

        state["crf_spec_status"] = "abstained" if self.should_abstain(crf_spec.extraction_confidence) else "completed"
        state["crf_spec"] = crf_spec.model_dump()
        self.log_action(
            action="extract_crf_specification",
            inputs={"protocol_text_length": len(protocol_text)},
            outputs={"num_fields": len(crf_spec.fields), "confidence": crf_spec.extraction_confidence},
            citations=citations, confidence=crf_spec.extraction_confidence,
        )
        return state
