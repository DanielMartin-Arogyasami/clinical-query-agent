"""Supervisor Agent — orchestrator with HITL gates."""
from __future__ import annotations
import structlog
from src.agents.base import BaseAgent
from src.models.schemas import AgentName, ApprovalStatus
from config.settings import settings

logger = structlog.get_logger(__name__)

ROUTING_ORDER = [
    AgentName.CRF_DESIGN, AgentName.EDC_CONFIG,
    AgentName.QUERY_GENERATION, AgentName.DATA_CLEANING, AgentName.PROGRAMMING,
]


class SupervisorAgent(BaseAgent):
    agent_name = AgentName.SUPERVISOR

    def run(self, state: dict) -> dict:
        current_stage = state.get("current_stage_index", 0)
        if current_stage >= len(ROUTING_ORDER):
            state["pipeline_status"] = "completed"
            logger.info("supervisor.pipeline_complete")
            self.log_action(
                action="pipeline_complete",
                inputs={"stages_completed": current_stage}, outputs={"status": "completed"},
            )
            return state
        next_agent = ROUTING_ORDER[current_stage]
        state["next_agent"] = next_agent.value
        state["current_stage_index"] = current_stage
        logger.info("supervisor.routing", next_agent=next_agent.value, stage=current_stage)
        self.log_action(
            action="route_to_agent",
            inputs={"current_stage": current_stage}, outputs={"next_agent": next_agent.value},
        )
        return state

    def check_approval_gate(self, state: dict) -> dict:
        if not settings.human_in_the_loop:
            state["gate_status"] = "skipped"
            return state
        current_stage = state.get("current_stage_index", 0)
        if current_stage == 0:
            state["gate_status"] = "approved"
            return state
        state["gate_status"] = "approved"
        self.log_action(
            action="hitl_gate_check",
            inputs={"stage": current_stage}, outputs={"gate_status": "approved"},
            human_approval=ApprovalStatus.APPROVED, human_approver="demo_auto_approve",
            notes="Auto-approved in demo mode. Production requires human interaction.",
        )
        return state

    def advance_stage(self, state: dict) -> dict:
        state["current_stage_index"] = state.get("current_stage_index", 0) + 1
        return state
