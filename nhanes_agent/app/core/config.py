from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rag_config import load_database_config, load_embedding_config


@dataclass(frozen=True)
class RetrievalWeights:
    vector: float = 0.45
    lexical: float = 0.35
    entity_overlap: float = 0.15
    metadata_boost: float = 0.05


@dataclass(frozen=True)
class AgentSettings:
    embedding_model_name: str
    chat_model_name: str
    chunk_size: int
    chunk_overlap: int
    top_k_retrieval: int
    weights: RetrievalWeights
    variable_confidence_threshold: float
    fuzzy_match_threshold: float
    llm_extraction_enabled: bool
    base_dir: str | Path | None = None


def load_agent_settings(base_dir: str | Path | None = None) -> AgentSettings:
    embedding = load_embedding_config(base_dir)
    return AgentSettings(
        embedding_model_name=embedding.model,
        chat_model_name="gpt-4o-mini",
        chunk_size=400,
        chunk_overlap=40,
        top_k_retrieval=8,
        weights=RetrievalWeights(),
        variable_confidence_threshold=0.75,
        fuzzy_match_threshold=0.86,
        llm_extraction_enabled=True,
        base_dir=base_dir,
    )


def database_dsn(base_dir: str | Path | None = None) -> str:
    config = load_database_config(base_dir)
    password = config.password.replace("@", "%40")
    return f"postgresql+psycopg://{config.user}:{password}@{config.host}:{config.port}/{config.dbname}"
