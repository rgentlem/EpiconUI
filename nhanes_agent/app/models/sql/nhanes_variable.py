from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from nhanes_agent.app.models.sql.base import Base


class NhanesVariable(Base):
    """Canonical NHANES variable metadata mirror."""

    __tablename__ = "nhanes_variables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    variable_name: Mapped[str] = mapped_column(String(64), index=True)
    canonical_label: Mapped[str] = mapped_column(Text)
    component: Mapped[str] = mapped_column(String(128))
    cycle: Mapped[str] = mapped_column(String(32))
