from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from nhanes_agent.app.models.sql.base import Base


class NhanesCycle(Base):
    """Canonical NHANES cycle reference."""

    __tablename__ = "nhanes_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_name: Mapped[str] = mapped_column(String(32), index=True)
