"""
Document chunker and indexer.
[FIX H3] SHA-256 with 16 chars for chunk IDs (was MD5 with 12).
[FIX L2] Regex-based tokenisation for BM25 corpus preparation.
"""
from __future__ import annotations
import hashlib
import re
from typing import Any
import structlog
from config.settings import settings

logger = structlog.get_logger(__name__)


def chunk_protocol(text: str, metadata: dict[str, Any] | None = None) -> list[dict]:
    """
    Chunk a protocol document at section boundaries.
    Returns list of dicts with keys: text, metadata, chunk_id.
    """
    metadata = metadata or {}
    sections = re.split(r"\n(?=#{1,4}\s|\d+\.\s|\d+\.\d+\s)", text)
    chunks = []

    current_parent = "root"
    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue

        heading_match = re.match(r"^(#{1,4})\s+(.+?)$|^(\d+(?:\.\d+)*)\s+(.+?)$", section, re.M)
        heading = ""
        if heading_match:
            heading = heading_match.group(2) or heading_match.group(4) or ""
            if heading_match.group(1) and len(heading_match.group(1)) <= 2:
                current_parent = heading

        if len(section) > settings.chunk_size * 2:
            sub_chunks = _split_large_section(section, settings.chunk_size, settings.chunk_overlap)
            for j, sub in enumerate(sub_chunks):
                chunk_id = hashlib.sha256(sub.encode()).hexdigest()[:16]  # FIX H3
                chunks.append({
                    "text": sub,
                    "chunk_id": chunk_id,
                    "metadata": {
                        **metadata,
                        "section_heading": heading,
                        "parent_section": current_parent,
                        "chunk_index": f"{i}.{j}",
                    },
                })
        else:
            chunk_id = hashlib.sha256(section.encode()).hexdigest()[:16]  # FIX H3
            chunks.append({
                "text": section,
                "chunk_id": chunk_id,
                "metadata": {
                    **metadata,
                    "section_heading": heading,
                    "parent_section": current_parent,
                    "chunk_index": str(i),
                },
            })

    logger.info("indexer.chunked", num_chunks=len(chunks), source=metadata.get("source", "?"))
    return chunks


def _split_large_section(text: str, size: int, overlap: int) -> list[str]:
    """Split oversized section into overlapping chunks at sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current: list[str] = []
    current_len = 0

    for sent in sentences:
        if current_len + len(sent) > size and current:
            chunks.append(" ".join(current))
            overlap_sents = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) > overlap:
                    break
                overlap_sents.insert(0, s)
                overlap_len += len(s)
            current = overlap_sents
            current_len = overlap_len
        current.append(sent)
        current_len += len(sent)

    if current:
        chunks.append(" ".join(current))
    return chunks


def tokenize_clinical(text: str) -> list[str]:
    """[FIX L2] Clinical-aware tokeniser — preserves hyphenated terms and CDISC codes.
    [BUG1 FIX] Patterns now match lowercase (text is lowercased before matching).
    """
    lowered = text.lower()
    # Match: CDISC-style codes (letters+digits like lbcat2), hyphenated terms, then plain words
    return re.findall(r"[a-z]{2,}\d+|[\w]+-[\w]+|[\w]+", lowered)


def index_documents(
    documents: list[dict],
    collection_name: str = "protocols",
) -> Any:
    """
    Index chunked documents into ChromaDB.
    [FIX L3] Note: ChromaDB uses its own default embedding model (all-MiniLM-L6-v2).
    The settings.embedding_model is for external embedding workflows.
    """
    import chromadb

    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    ids = [d["chunk_id"] for d in documents]
    texts = [d["text"] for d in documents]
    metadatas = [d["metadata"] for d in documents]

    batch_size = 100
    for i in range(0, len(ids), batch_size):
        collection.add(
            ids=ids[i : i + batch_size],
            documents=texts[i : i + batch_size],
            metadatas=metadatas[i : i + batch_size],
        )

    logger.info("indexer.indexed", collection=collection_name, num_docs=len(ids))
    return collection
