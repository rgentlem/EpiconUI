from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from nhanes_agent.app.models.sql.base import Base


class Embedding(Base):
    """Embedding row metadata. Vector storage remains in pgvector-backed tables."""

    __tablename__ = "embeddings"

    chunk_id: Mapped[int] = mapped_column(ForeignKey("chunks.chunk_id"), primary_key=True)
    embedding_model: Mapped[str] = mapped_column(String(255))
    embedding_dimensions: Mapped[int] = mapped_column(Integer)
