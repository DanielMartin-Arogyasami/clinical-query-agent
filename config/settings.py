"""
Central configuration — loads from .env, provides typed settings.
[FIX H6] ensure_dirs() removed from module scope — called explicitly by entry points.
"""
from __future__ import annotations
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_model: str = "gpt-4o"

    # Embedding / RAG
    embedding_model: str = "text-embedding-3-small"
    chroma_persist_dir: str = str(PROJECT_ROOT / "data" / "chromadb")
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_top_k: int = 10
    rerank_top_k: int = 5
    reranker_enabled: bool = True

    # Pipeline
    confidence_threshold: float = 0.75
    max_retries: int = 3
    human_in_the_loop: bool = True

    # Audit
    audit_log_dir: str = str(PROJECT_ROOT / "logs" / "audit")
    audit_log_format: Literal["jsonl", "json"] = "jsonl"

    # Data paths
    protocol_dir: str = str(PROJECT_ROOT / "data" / "protocols")
    cdisc_dir: str = str(PROJECT_ROOT / "data" / "cdisc")
    synthetic_data_dir: str = str(PROJECT_ROOT / "data" / "synthetic")

    # External APIs
    ctgov_base_url: str = "https://clinicaltrials.gov/api/v2"

    def ensure_dirs(self) -> None:
        """Create required directories. Call from entry points, NOT at import time."""
        for d in [
            self.chroma_persist_dir,
            self.audit_log_dir,
            self.protocol_dir,
            self.cdisc_dir,
            self.synthetic_data_dir,
        ]:
            Path(d).mkdir(parents=True, exist_ok=True)

    @property
    def llm_provider(self) -> Literal["openai", "anthropic"]:
        return "anthropic" if self.llm_model.startswith("claude") else "openai"


# Singleton — dirs are NOT created here (FIX H6)
settings = Settings()
