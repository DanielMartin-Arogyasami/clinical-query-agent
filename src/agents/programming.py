"""Programming Agent — SDTM/ADaM. [FIX C2] [FIX M1]"""
from __future__ import annotations
import json
import structlog
from pydantic import ValidationError
from src.agents.base import BaseAgent
from src.models.schemas import AgentName, SDTMMapping, SDTMDataset

logger = structlog.get_logger(__name__)

SDTM_MAPPING_PROMPT = """Generate SDTM mapping specifications for this clinical data.

DATA COLUMNS: {columns}
DOMAIN: {domain}
SAMPLE DATA (first 5 rows): {sample_data}

CDISC CONTEXT:
{context}

Output ONLY this JSON (no markdown):
{{"domain": "{domain}", "dataset_name": "{domain_lower}", "label": "...", "variables": [{{"source_field": "...", "sdtm_domain": "{domain}", "sdtm_variable": "...", "transformation": "...", "controlled_terminology": "null", "derivation_rule": "null"}}], "validation_messages": []}}"""


class ProgrammingAgent(BaseAgent):
    agent_name = AgentName.PROGRAMMING

    def run(self, state: dict) -> dict:
        df = state.get("dataframe")
        data_path = state.get("data_path")
        domain = state.get("domain", "VS")
        if df is None and data_path:
            from src.tools.data_tools import load_sdtm_dataset
            df = load_sdtm_dataset(data_path)
        if df is None or df.empty:
            logger.warning("programming.no_data")
            return state

        chunks = self.retrieve_context(f"SDTM {domain} domain mapping implementation guide variables")
        context = self.format_context(chunks)
        citations = [c.metadata.get("section_heading", c.chunk_id) for c in chunks]

        try:
            result = self.invoke_llm_json([
                {"role": "system", "content": self._prompt_template},
                {"role": "user", "content": SDTM_MAPPING_PROMPT.format(
                    columns=list(df.columns), domain=domain, domain_lower=domain.lower(),
                    sample_data=df.head(5).to_string(), context=context,
                )},
            ])
            dataset = SDTMDataset(
                domain=result.get("domain", domain),
                dataset_name=result.get("dataset_name", domain.lower()),
                label=result.get("label", f"{domain} Dataset"),
                variables=[SDTMMapping(**v) for v in result.get("variables", [])],
                record_count=len(df), validation_status="pending",
                validation_messages=result.get("validation_messages", []),
            )
        except json.JSONDecodeError as e:
            logger.error("programming.json_parse_error", error=str(e))
            dataset = SDTMDataset(
                domain=domain, dataset_name=domain.lower(), label=f"{domain} Dataset",
                variables=[], record_count=len(df), validation_status="error",
                validation_messages=[f"JSON parse error: {e}"],
            )
        except ValidationError as e:
            logger.error("programming.validation_error", error=str(e))
            dataset = SDTMDataset(
                domain=domain, dataset_name=domain.lower(), label=f"{domain} Dataset",
                variables=[], record_count=len(df), validation_status="error",
                validation_messages=[f"Validation error: {e}"],
            )

        state["sdtm_datasets"] = state.get("sdtm_datasets", []) + [dataset.model_dump()]
        state["programming_status"] = "completed"
        self.log_action(
            action="generate_sdtm_mapping",
            inputs={"domain": domain, "num_rows": len(df), "columns": list(df.columns)},
            outputs={"num_variables_mapped": len(dataset.variables), "status": dataset.validation_status},
            citations=citations,
        )
        return state
