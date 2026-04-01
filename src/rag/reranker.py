"""
Cross-encoder reranker.
[FIX H5] Now integrated into BaseAgent.retrieve_context().
"""
from __future__ import annotations
import structlog
from config.settings import settings
from src.rag.retriever import RetrievedChunk

logger = structlog.get_logger(__name__)


class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
            logger.info("reranker.loaded", model=self.model_name)

    def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int | None = None) -> list[RetrievedChunk]:
        if not chunks:
            return []
        top_k = top_k or settings.rerank_top_k
        self._load_model()
        pairs = [(query, chunk.text) for chunk in chunks]
        scores = self._model.predict(pairs)
        for chunk, score in zip(chunks, scores):
            chunk.score = float(score)
            chunk.source = "reranked"
        ranked = sorted(chunks, key=lambda c: c.score, reverse=True)
        return ranked[:top_k]
