"""Ingest protocols into RAG index. [FIX H6]"""
from __future__ import annotations
import json
from pathlib import Path
import structlog
from config.settings import settings
from src.rag.indexer import chunk_protocol, index_documents

logger = structlog.get_logger(__name__)


def ingest_ctgov_protocols():
    protocol_dir = Path(settings.protocol_dir)
    all_chunks = []
    for json_file in protocol_dir.glob("*.json"):
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)
        proto = data.get("protocolSection", data)
        ident = proto.get("identificationModule", {})
        desc = proto.get("descriptionModule", {})
        elig = proto.get("eligibilityModule", {})
        outcomes = proto.get("outcomesModule", {})
        nct_id = ident.get("nctId", json_file.stem)
        text_parts = [
            f"# {ident.get('briefTitle', 'Untitled Study')}",
            f"NCT ID: {nct_id}",
            f"\n## Description\n{desc.get('detailedDescription', desc.get('briefSummary', ''))}",
            f"\n## Eligibility\n{elig.get('eligibilityCriteria', '')}",
        ]
        for po in outcomes.get("primaryOutcomes", []):
            text_parts.append(f"\n## Primary Outcome\n- {po.get('measure', '')}: {po.get('description', '')}")
        for so in outcomes.get("secondaryOutcomes", []):
            text_parts.append(f"\n## Secondary Outcome\n- {so.get('measure', '')}: {so.get('description', '')}")
        chunks = chunk_protocol("\n".join(text_parts), metadata={
            "source": nct_id, "doc_type": "protocol", "format": "clinicaltrials_gov",
        })
        all_chunks.extend(chunks)
        print(f"Chunked {nct_id}: {len(chunks)} chunks")
    if all_chunks:
        index_documents(all_chunks, collection_name="protocols")
        print(f"\nIndexed {len(all_chunks)} total chunks into ChromaDB")
    else:
        print("No protocol files found. Run download_public_data.py first.")


def main():
    settings.ensure_dirs()
    print("Ingesting protocols into RAG index...")
    ingest_ctgov_protocols()
    print("\nOK: Ingestion complete.")


if __name__ == "__main__":
    main()
