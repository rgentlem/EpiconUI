from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from nhanes_agent.app.models.sql.base import Base


class Extraction(Base):
    """Recorded extraction and validation result for a chunk-level mention."""

    __tablename__ = "extractions"

    extraction_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("chunks.chunk_id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    raw_mention: Mapped[str] = mapped_column(Text)
    canonical_value: Mapped[str] = mapped_column(Text)
    validation_status: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
