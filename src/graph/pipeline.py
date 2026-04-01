"""
LangGraph pipeline.
[FIX C1] Correct return type annotation.
[FIX L4] Single run_id source in run_pipeline.
"""
from __future__ import annotations
from typing import Any
import uuid
import structlog
from langgraph.graph import StateGraph, START, END

from config.settings import settings
from src.audit.trail import AuditTrail
from src.rag.retriever import HybridRetriever
from src.agents.supervisor import SupervisorAgent
from src.agents.crf_design import CRFDesignAgent
from src.agents.edc_config import EDCConfigAgent
from src.agents.query_generation import QueryGenerationAgent
from src.agents.data_cleaning import DataCleaningAgent
from src.agents.programming import ProgrammingAgent

logger = structlog.get_logger(__name__)


def build_pipeline(
    run_id: str,
    retriever: HybridRetriever | None = None,
) -> tuple[Any, AuditTrail]:  # FIX C1: correct return type
    """Construct the clinical data management LangGraph pipeline."""
    audit = AuditTrail(run_id=run_id)
    supervisor = SupervisorAgent(audit_trail=audit, retriever=retriever)
    agents = {
        "crf_design": CRFDesignAgent(audit_trail=audit, retriever=retriever),
        "edc_config": EDCConfigAgent(audit_trail=audit, retriever=retriever),
        "query_generation": QueryGenerationAgent(audit_trail=audit, retriever=retriever),
        "data_cleaning": DataCleaningAgent(audit_trail=audit, retriever=retriever),
        "programming": ProgrammingAgent(audit_trail=audit, retriever=retriever),
    }

    def supervisor_node(state: dict) -> dict:
        return supervisor.run(state)

    def gate_node(state: dict) -> dict:
        return supervisor.check_approval_gate(state)

    def agent_dispatch(state: dict) -> dict:
        agent_name = state.get("next_agent")
        if agent_name and agent_name in agents:
            return agents[agent_name].run(state)
        logger.error("pipeline.unknown_agent", agent=agent_name)
        return state

    def advance_node(state: dict) -> dict:
        return supervisor.advance_stage(state)

    def should_continue(state: dict) -> str:
        return "end" if state.get("pipeline_status") == "completed" else "gate"

    def gate_decision(state: dict) -> str:
        return "dispatch" if state.get("gate_status") in ("approved", "skipped") else "end"

    graph = StateGraph(dict)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("gate", gate_node)
    graph.add_node("dispatch", agent_dispatch)
    graph.add_node("advance", advance_node)
    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges("supervisor", should_continue, {"gate": "gate", "end": END})
    graph.add_conditional_edges("gate", gate_decision, {"dispatch": "dispatch", "end": END})
    graph.add_edge("dispatch", "advance")
    graph.add_edge("advance", "supervisor")

    logger.info("pipeline.built", run_id=run_id)
    return graph.compile(), audit


def run_pipeline(
    study_id: str,
    protocol_text: str = "",
    data_path: str = "",
    domain: str = "VS",
    retriever: HybridRetriever | None = None,
) -> tuple[dict, AuditTrail]:
    """Execute the full pipeline end-to-end."""
    run_id = uuid.uuid4().hex  # FIX L4: single source of run_id
    settings.ensure_dirs()  # FIX H6: called here, not at import
    compiled_graph, audit = build_pipeline(run_id=run_id, retriever=retriever)

    initial_state = {
        "study_id": study_id, "protocol_text": protocol_text,
        "data_path": data_path, "domain": domain,
        "dataframe": None, "crf_spec": None, "edc_config": None,
        "anomalies": [], "queries": [], "cleaning_actions": [], "sdtm_datasets": [],
        "current_stage_index": 0, "next_agent": "", "gate_status": "",
        "pipeline_status": "in_progress",
    }
    logger.info("pipeline.starting", study_id=study_id, run_id=run_id)
    final_state = compiled_graph.invoke(initial_state)
    logger.info("pipeline.finished", status=final_state.get("pipeline_status"))
    return final_state, audit
