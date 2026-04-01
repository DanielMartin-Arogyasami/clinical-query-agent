"""Tests for RAG subsystem."""
from __future__ import annotations
from src.rag.indexer import chunk_protocol, _split_large_section, tokenize_clinical
from src.rag.retriever import HybridRetriever, RetrievedChunk


class TestChunking:
    def test_basic(self):
        chunks = chunk_protocol("# Section 1\nContent.\n\n# Section 2\nMore.", metadata={"source": "test"})
        assert len(chunks) >= 1
        assert all("chunk_id" in c for c in chunks)
        # [FIX H3] SHA-256 chunk IDs are 16 hex chars
        assert all(len(c["chunk_id"]) == 16 for c in chunks)

    def test_preserves_metadata(self):
        chunks = chunk_protocol("# Study\nPhase III.", metadata={"source": "NCT001"})
        assert chunks[0]["metadata"]["source"] == "NCT001"

    def test_split_large(self):
        text = ". ".join([f"Sentence {i}" for i in range(100)])
        assert len(_split_large_section(text, size=200, overlap=50)) > 1


class TestTokenizer:
    def test_clinical_terms(self):
        tokens = tokenize_clinical("Systolic blood-pressure SYSBP VSSTRESN")
        assert "blood-pressure" in tokens
        assert "sysbp" in tokens
        assert "vsstresn" in tokens

    def test_cdisc_codes_with_digits(self):
        """[BUG1 FIX] Verify codes like LBCAT2 are captured as single tokens."""
        tokens = tokenize_clinical("LBCAT2 AETERM1 simple")
        assert "lbcat2" in tokens
        assert "aeterm1" in tokens


class TestHybridRetriever:
    def test_bm25_search(self):
        r = HybridRetriever()
        r.load_corpus([
            {"text": "systolic blood pressure", "chunk_id": "1"},
            {"text": "patient demographics", "chunk_id": "2"},
        ])
        results = r._bm25_search("blood pressure", top_k=2)
        assert len(results) >= 1
        assert all(isinstance(x, RetrievedChunk) for x in results)

    def test_rrf(self):
        a = [RetrievedChunk(text="A", chunk_id="1", score=1.0)]
        b = [RetrievedChunk(text="B", chunk_id="2", score=0.9)]
        fused = HybridRetriever._reciprocal_rank_fusion(a, b, 0.5, 0.5)
        assert len(fused) == 2
