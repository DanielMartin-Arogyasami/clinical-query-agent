"""
EDC Configuration Agent. [FIX C2] [FIX M1]
"""
from __future__ import annotations
import json
import structlog
from pydantic import ValidationError
from src.agents.base import BaseAgent
from src.models.schemas import AgentName, EditCheck, EDCConfiguration

logger = structlog.get_logger(__name__)

EDC_CONFIG_PROMPT = """Given the CRF specification, generate edit checks and validation rules.

CRF SPECIFICATION:
{crf_spec_json}

RELEVANT CONTEXT:
{context}

Output ONLY this JSON (no markdown):
{{"edit_checks": [{{"check_type": "range|presence|temporal|cross_form|consistency", "target_field": "VAR", "condition": "...", "query_text": "...", "severity": "low|medium|high|critical"}}], "field_constraints": {{"VAR": {{"type": "numeric", "min": 0, "max": 300}}}}, "cross_form_rules": [], "generation_confidence": 0.0}}"""


class EDCConfigAgent(BaseAgent):
    agent_name = AgentName.EDC_CONFIG

    def run(self, state: dict) -> dict:
        crf_spec = state.get("crf_spec")
        if not crf_spec:
            logger.warning("edc_config.no_crf_spec")
            return state

        chunks = self.retrieve_context("edit checks validation rules CDISC CDASH range temporal")
        context = self.format_context(chunks)
        citations = [c.metadata.get("section_heading", c.chunk_id) for c in chunks]

        prompt = EDC_CONFIG_PROMPT.format(
            crf_spec_json=json.dumps(crf_spec, indent=2, default=str)[:6000],
            context=context,
        )

        try:
            result = self.invoke_llm_json([
                {"role": "system", "content": self._prompt_template},
                {"role": "user", "content": prompt},
            ])
            study_id = crf_spec.get("study_id", "UNKNOWN") if isinstance(crf_spec, dict) else "UNKNOWN"
            edc = EDCConfiguration(
                study_id=study_id,
                edit_checks=[EditCheck(**ec) for ec in result.get("edit_checks", [])],
                field_constraints=result.get("field_constraints", {}),
                cross_form_rules=result.get("cross_form_rules", []),
                generation_confidence=result.get("generation_confidence", 0.0),
            )
        except json.JSONDecodeError as e:
            logger.error("edc_config.json_parse_error", error=str(e))
            edc = EDCConfiguration(
                study_id="UNKNOWN", edit_checks=[], field_constraints={},
                cross_form_rules=[], generation_confidence=0.0,
            )
        except ValidationError as e:
            logger.error("edc_config.validation_error", error=str(e))
            edc = EDCConfiguration(
                study_id="UNKNOWN", edit_checks=[], field_constraints={},
                cross_form_rules=[], generation_confidence=0.0,
            )

        state["edc_config"] = edc.model_dump()
        state["edc_config_status"] = "abstained" if self.should_abstain(edc.generation_confidence) else "completed"
        self.log_action(
            action="generate_edc_configuration",
            inputs={"num_crf_fields": len(crf_spec.get("fields", [])) if isinstance(crf_spec, dict) else 0},
            outputs={"num_edit_checks": len(edc.edit_checks), "confidence": edc.generation_confidence},
            citations=citations, confidence=edc.generation_confidence,
        )
        return state
