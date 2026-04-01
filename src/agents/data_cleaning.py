"""Data Cleaning Agent. [FIX C2] [FIX M1]"""
from __future__ import annotations
import json
import structlog
from pydantic import ValidationError
from src.agents.base import BaseAgent
from src.models.schemas import AgentName, CleaningAction

logger = structlog.get_logger(__name__)

CLEANING_PROMPT = """You are resolving data queries for a clinical trial.

QUERIES TO RESOLVE:
{queries_json}

PROTOCOL CONTEXT:
{context}

Auto-resolvable: unit conversions, obvious data entry errors, derivable values.
MUST escalate: clinically ambiguous, safety-relevant, requiring SDV.

Output ONLY this JSON (no markdown):
{{"actions": [{{"query_id": "...", "action_type": "auto_resolve|escalate|flag_for_review", "original_value": "...", "new_value": "null if escalating", "justification": "...", "resolution_pattern": "null", "confidence": 0.0, "requires_human_approval": true}}]}}"""


class DataCleaningAgent(BaseAgent):
    agent_name = AgentName.DATA_CLEANING

    def run(self, state: dict) -> dict:
        queries = state.get("queries", [])
        if not queries:
            state["cleaning_status"] = "no_queries"
            return state

        chunks = self.retrieve_context("data cleaning query resolution patterns clinical trial")
        context = self.format_context(chunks)
        citations = [c.metadata.get("section_heading", c.chunk_id) for c in chunks]

        try:
            result = self.invoke_llm_json([
                {"role": "system", "content": self._prompt_template},
                {"role": "user", "content": CLEANING_PROMPT.format(
                    queries_json=json.dumps(queries[:30], indent=2, default=str),
                    context=context,
                )},
            ])
            actions = [CleaningAction(**a) for a in result.get("actions", [])]
        except json.JSONDecodeError as e:
            logger.error("data_cleaning.json_parse_error", error=str(e))
            actions = self._escalate_all(queries)
        except (ValidationError, KeyError) as e:
            logger.error("data_cleaning.validation_error", error=str(e))
            actions = self._escalate_all(queries)

        state["cleaning_actions"] = [a.model_dump() for a in actions]
        state["cleaning_status"] = "completed"
        auto_resolved = sum(1 for a in actions if a.action_type == "auto_resolve")
        escalated = sum(1 for a in actions if a.action_type == "escalate")
        self.log_action(
            action="clean_data",
            inputs={"num_queries": len(queries)},
            outputs={"auto_resolved": auto_resolved, "escalated": escalated},
            citations=citations,
            confidence=sum(a.confidence for a in actions) / max(len(actions), 1),
        )
        return state

    @staticmethod
    def _escalate_all(queries: list[dict]) -> list[CleaningAction]:
        return [
            CleaningAction(
                query_id=q.get("query_id", "unknown") if isinstance(q, dict) else "unknown",
                action_type="escalate", original_value="",
                justification="Auto-resolution failed; escalating to human review.",
                confidence=0.0, requires_human_approval=True,
            )
            for q in queries
        ]
