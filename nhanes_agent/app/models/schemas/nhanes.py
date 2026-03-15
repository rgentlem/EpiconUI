from __future__ import annotations

from pydantic import BaseModel


class EvidenceReference(BaseModel):
    """Evidence reference for validated output rows."""

    chunk_id: str
    document_id: str
    section: str
    score: float
    short_quote: str


class ValidatedCycle(BaseModel):
    raw_mention: str
    canonical_cycles: list[str]
    validation_status: str
    confidence: float
    evidence_chunk_ids: list[str]


class ValidatedComponent(BaseModel):
    raw_mention: str
    canonical_component: str
    validation_status: str
    confidence: float
    evidence_chunk_ids: list[str]


class ValidatedVariable(BaseModel):
    raw_mention: str
    canonical_variable_name: str
    canonical_label: str
    component: str
    cycle: str
    validation_status: str
    confidence: float
    evidence_chunk_ids: list[str]
