"""
Hybrid retriever — BM25 sparse + ChromaDB dense + reciprocal rank fusion.
[FIX L2] Uses clinical tokeniser for BM25.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import structlog
from rank_bm25 import BM25Okapi
from config.settings import settings

logger = structlog.get_logger(__name__)


@dataclass
class RetrievedChunk:
    text: str
    chunk_id: str
    score: float
    metadata: dict = field(default_factory=dict)
    source: str = ""


class HybridRetriever:
    def __init__(self, collection_name: str = "protocols"):
        self.collection_name = collection_name
        self._bm25: BM25Okapi | None = None
        self._corpus: list[dict] = []
        self._collection = None

    def load_corpus(self, documents: list[dict]) -> None:
        from src.rag.indexer import tokenize_clinical  # FIX L2
        self._corpus = documents
        tokenised = [tokenize_clinical(doc["text"]) for doc in documents]
        self._bm25 = BM25Okapi(tokenised)
        logger.info("retriever.bm25_loaded", corpus_size=len(documents))

    def load_chroma(self) -> None:
        import chromadb
        client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self._collection = client.get_or_create_collection(name=self.collection_name)
        logger.info("retriever.chroma_loaded", collection=self.collection_name)

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        bm25_weight: float = 0.4,
        dense_weight: float = 0.6,
    ) -> list[RetrievedChunk]:
        top_k = top_k or settings.retrieval_top_k
        bm25_results = self._bm25_search(query, top_k * 2)
        dense_results = self._dense_search(query, top_k * 2)
        fused = self._reciprocal_rank_fusion(bm25_results, dense_results, bm25_weight, dense_weight)
        return fused[:top_k]

    def _bm25_search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        if not self._bm25 or not self._corpus:
            return []
        from src.rag.indexer import tokenize_clinical  # FIX L2
        tokens = tokenize_clinical(query)
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for idx, score in ranked:
            doc = self._corpus[idx]
            results.append(RetrievedChunk(
                text=doc["text"],
                chunk_id=doc.get("chunk_id", str(idx)),
                score=float(score),
                metadata=doc.get("metadata", {}),
                source="bm25",
            ))
        return results

    def _dense_search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        if not self._collection:
            return []
        results = self._collection.query(query_texts=[query], n_results=top_k)
        chunks = []
        if results and results["documents"]:
            for doc, meta, dist, cid in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
                results["ids"][0],
            ):
                chunks.append(RetrievedChunk(
                    text=doc, chunk_id=cid,
                    score=1.0 - dist, metadata=meta, source="dense",
                ))
        return chunks

    @staticmethod
    def _reciprocal_rank_fusion(
        list_a: list[RetrievedChunk],
        list_b: list[RetrievedChunk],
        weight_a: float, weight_b: float, k: int = 60,
    ) -> list[RetrievedChunk]:
        scores: dict[str, float] = {}
        chunk_map: dict[str, RetrievedChunk] = {}
        for rank, chunk in enumerate(list_a):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + weight_a / (k + rank + 1)
            chunk_map[chunk.chunk_id] = chunk
        for rank, chunk in enumerate(list_b):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + weight_b / (k + rank + 1)
            if chunk.chunk_id not in chunk_map:
                chunk_map[chunk.chunk_id] = chunk
        ranked_ids = sorted(scores, key=scores.__getitem__, reverse=True)
        return [
            RetrievedChunk(
                text=chunk_map[cid].text, chunk_id=cid,
                score=scores[cid], metadata=chunk_map[cid].metadata, source="fused",
            )
            for cid in ranked_ids
        ]
