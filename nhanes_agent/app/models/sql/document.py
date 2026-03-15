from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from nhanes_agent.app.models.sql.base import Base


class Document(Base):
    """Logical document metadata for ingested PDFs."""

    __tablename__ = "documents"

    document_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_name: Mapped[str] = mapped_column(String(255), index=True)
    paper_slug: Mapped[str] = mapped_column(String(255), index=True)
    paper_name: Mapped[str] = mapped_column(String(255))
    source_pdf: Mapped[str] = mapped_column(Text)
    manifest_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
