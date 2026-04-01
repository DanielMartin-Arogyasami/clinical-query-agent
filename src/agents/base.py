"""
Base agent class — shared infrastructure for all specialist agents.
[FIX C4] Uses invoke_llm_with_retry for all LLM calls.
[FIX H5] Integrates CrossEncoderReranker into retrieve_context().
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
import structlog
from src.audit.trail import AuditTrail
from src.models.schemas import AgentName, ApprovalStatus
from src.rag.retriever import HybridRetriever, RetrievedChunk
from src.rag.reranker import CrossEncoderReranker
from src.utils.helpers import load_agent_config, get_llm, parse_llm_json, invoke_llm_with_retry
from config.settings import settings

logger = structlog.get_logger(__name__)

# Shared reranker instance (lazy-loaded)
_reranker: CrossEncoderReranker | None = None


def _get_reranker() -> CrossEncoderReranker:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoderReranker()
    return _reranker


class BaseAgent(ABC):
    agent_name: AgentName

    def __init__(self, audit_trail: AuditTrail, retriever: HybridRetriever | None = None):
        self.audit = audit_trail
        self.retriever = retriever
        self.config = load_agent_config(self.agent_name.value)
        self.confidence_threshold = self.config.get("confidence_threshold", settings.confidence_threshold)
        self._llm = None  # lazy: avoid requiring API key until an LLM call
        self._prompt_template = self._build_system_prompt()

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm()
        return self._llm

    def _build_system_prompt(self) -> str:
        return (
            f"You are {self.config['name']}, a {self.config['role']}.\n\n"
            f"GOAL: {self.config['goal']}\n\n"
            f"BACKSTORY: {self.config['backstory']}\n\n"
            "RULES:\n"
            "1. Ground every claim in retrieved evidence. Cite the source.\n"
            "2. If confidence < threshold, ABSTAIN and say so explicitly.\n"
            "3. Output ONLY valid JSON matching the required schema. No markdown, no preamble.\n"
            "4. Never fabricate data points, references, or query text.\n"
            f"5. Your confidence threshold is {self.confidence_threshold}.\n"
        )

    def invoke_llm(self, messages: list[dict]) -> str:
        """Invoke LLM with retry and return raw content string. [FIX C4]"""
        response = invoke_llm_with_retry(self.llm, messages, max_retries=settings.max_retries)
        return response.content

    def invoke_llm_json(self, messages: list[dict]) -> dict:
        """Invoke LLM with retry and parse JSON from output. [FIX C2 + C4]"""
        raw = self.invoke_llm(messages)
        return parse_llm_json(raw)

    def retrieve_context(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Retrieve context via hybrid RAG + optional reranking. [FIX H5]"""
        if self.retriever is None:
            return []
        # Over-fetch for reranking
        fetch_k = top_k * 3 if settings.reranker_enabled else top_k
        chunks = self.retriever.retrieve(query, top_k=fetch_k)
        # Rerank [FIX H5]
        if settings.reranker_enabled and chunks:
            try:
                reranker = _get_reranker()
                chunks = reranker.rerank(query, chunks, top_k=top_k)
            except Exception as e:
                logger.warning("base_agent.reranker_failed", error=str(e))
                chunks = chunks[:top_k]
        else:
            chunks = chunks[:top_k]
        return chunks

    def format_context(self, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return "No relevant context retrieved."
        parts = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.metadata.get("section_heading", chunk.chunk_id)
            parts.append(f"[Source {i}: {source}]\n{chunk.text}")
        return "\n\n---\n\n".join(parts)

    def should_abstain(self, confidence: float) -> bool:
        return confidence < self.confidence_threshold

    def log_action(
        self,
        action: str,
        inputs: Any,
        outputs: Any,
        citations: list[str] | None = None,
        confidence: float | None = None,
        human_approval: ApprovalStatus | None = None,
        human_approver: str | None = None,
        notes: str | None = None,
    ):
        return self.audit.log_action(
            agent=self.agent_name,
            action=action,
            inputs=inputs,
            outputs=outputs,
            model_version=settings.llm_model,
            prompt_template=self._prompt_template,
            retrieval_citations=citations,
            confidence=confidence,
            human_approval=human_approval or (
                ApprovalStatus.PENDING if settings.human_in_the_loop else ApprovalStatus.SKIPPED
            ),
            human_approver=human_approver,
            notes=notes,
        )

    @abstractmethod
    def run(self, state: dict) -> dict:
        ...
