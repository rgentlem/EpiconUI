from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from config_store import DEFAULT_OPENAI_BASE_URL, load_llm_config
from project_store import epimind_home


@dataclass
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    dbname: str
    schema: str


@dataclass
class EmbeddingConfig:
    base_url: str
    api_key: str
    model: str
    dimensions: int
    batch_size: int
    timeout: int


def rag_config_path(base_dir: str | Path | None = None) -> Path:
    root = epimind_home(base_dir) / "config"
    root.mkdir(parents=True, exist_ok=True)
    return root / "rag.json"


def _stored_rag_config(base_dir: str | Path | None = None) -> dict[str, Any]:
    path = rag_config_path(base_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_database_config(base_dir: str | Path | None = None) -> DatabaseConfig:
    stored = _stored_rag_config(base_dir)
    return DatabaseConfig(
        host=os.environ.get("EPIMIND_PGHOST", os.environ.get("PGHOST", stored.get("host", "127.0.0.1"))).strip(),
        port=int(os.environ.get("EPIMIND_PGPORT", os.environ.get("PGPORT", stored.get("port", 5432)))),
        user=os.environ.get("EPIMIND_PGUSER", os.environ.get("PGUSER", stored.get("user", "postgres"))).strip(),
        password=os.environ.get("EPIMIND_PGPASSWORD", os.environ.get("PGPASSWORD", "")),
        dbname=os.environ.get(
            "EPIMIND_PGDATABASE",
            os.environ.get("PGDATABASE", stored.get("dbname", "epimind")),
        ).strip(),
        schema=os.environ.get("EPIMIND_PGSCHEMA", stored.get("schema", "epimind")).strip() or "epimind",
    )


def load_embedding_config(base_dir: str | Path | None = None) -> EmbeddingConfig:
    stored = _stored_rag_config(base_dir)
    llm = load_llm_config(base_dir)
    return EmbeddingConfig(
        base_url=(
            os.environ.get("OPENAI_EMBEDDING_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or os.environ.get("OPENAI_API_BASE")
            or stored.get("embedding_base_url")
            or llm.get("base_url")
            or DEFAULT_OPENAI_BASE_URL
        ).strip(),
        api_key=(
            os.environ.get("OPENAI_EMBEDDING_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or stored.get("embedding_api_key")
            or llm.get("api_key", "")
        ).strip(),
        model=(
            os.environ.get("OPENAI_EMBEDDING_MODEL")
            or stored.get("embedding_model")
            or "text-embedding-3-small"
        ).strip(),
        dimensions=int(os.environ.get("OPENAI_EMBEDDING_DIMENSIONS", stored.get("embedding_dimensions", 1536))),
        batch_size=int(os.environ.get("OPENAI_EMBEDDING_BATCH_SIZE", stored.get("embedding_batch_size", 32))),
        timeout=int(os.environ.get("OPENAI_EMBEDDING_TIMEOUT", stored.get("embedding_timeout", 180))),
    )


def rag_runtime_summary(base_dir: str | Path | None = None) -> dict[str, Any]:
    db = load_database_config(base_dir)
    embedding = load_embedding_config(base_dir)
    return {
        "database": {
            "host": db.host,
            "port": db.port,
            "user": db.user,
            "dbname": db.dbname,
            "schema": db.schema,
            "has_password": bool(db.password),
        },
        "embedding": {
            "base_url": embedding.base_url,
            "model": embedding.model,
            "dimensions": embedding.dimensions,
            "batch_size": embedding.batch_size,
            "timeout": embedding.timeout,
            "has_api_key": bool(embedding.api_key),
        },
    }


def save_rag_runtime_config(
    *,
    base_dir: str | Path | None = None,
    database: DatabaseConfig | None = None,
    embedding: EmbeddingConfig | None = None,
    tables: dict[str, str] | None = None,
) -> dict[str, Any]:
    database = database or load_database_config(base_dir)
    embedding = embedding or load_embedding_config(base_dir)
    payload = {
        "host": database.host,
        "port": database.port,
        "user": database.user,
        "dbname": database.dbname,
        "schema": database.schema,
        "embedding_base_url": embedding.base_url,
        "embedding_model": embedding.model,
        "embedding_dimensions": embedding.dimensions,
        "embedding_batch_size": embedding.batch_size,
        "embedding_timeout": embedding.timeout,
        "tables": tables or {},
    }
    path = rag_config_path(base_dir)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def config_asdict(database: DatabaseConfig, embedding: EmbeddingConfig) -> dict[str, Any]:
    return {
        "database": asdict(database),
        "embedding": asdict(embedding),
    }
