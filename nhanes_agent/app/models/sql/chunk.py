from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from nhanes_agent.app.models.sql.base import Base


class Chunk(Base):
    """Chunk-level text metadata for retrieval and provenance."""

    __tablename__ = "chunks"

    chunk_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.document_id"), index=True)
    section_name: Mapped[str] = mapped_column(String(255), default="document")
    chunk_index: Mapped[int] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(Text)
    markdown: Mapped[str] = mapped_column(Text)
