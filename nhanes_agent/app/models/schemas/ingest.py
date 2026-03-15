from __future__ import annotations

from pydantic import BaseModel, Field


class IngestPdfMetadata(BaseModel):
    """Optional metadata provided at ingestion time."""

    project_name: str = Field(..., min_length=1)
    auto_index: bool = True


class IngestPdfResponse(BaseModel):
    """Ingestion response payload."""

    document_id: str
    number_of_chunks: int
    number_of_validated_cycles: int
    number_of_validated_components: int
    number_of_validated_variables: int
