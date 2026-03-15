from __future__ import annotations

from pydantic import BaseModel


class QueryResponse(BaseModel):
    """Primary response for agent queries."""

    markdown: str
    payload: dict


class DocumentResponse(BaseModel):
    """Document-level ingestion metadata response."""

    document_id: str
    metadata: dict


class ChunkResponse(BaseModel):
    """Chunk-level retrieval and extraction metadata response."""

    chunk_id: str
    payload: dict
