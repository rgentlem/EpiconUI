from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from nhanes_agent.app.models.sql.base import Base


class NhanesComponent(Base):
    """Canonical NHANES component reference."""

    __tablename__ = "nhanes_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_name: Mapped[str] = mapped_column(String(128), index=True)
    alias: Mapped[str] = mapped_column(String(128), index=True)
