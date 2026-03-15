from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Structured request for hybrid NHANES query processing."""

    query: str = Field(..., min_length=1)
    project_name: str = Field(..., min_length=1)
    paper_slug: str = Field(..., min_length=1)


class HybridRetrievalFilters(BaseModel):
    """Optional metadata filters applied during retrieval."""

    cycle: str | None = None
    component: str | None = None
