from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from nhanes_agent.app.core.config import load_agent_settings
from nhanes_agent.app.models.schemas.query import QueryRequest
from nhanes_agent.app.models.schemas.response import ChunkResponse, DocumentResponse, QueryResponse
from nhanes_agent.app.services.agent.executor import QueryExecutor
from project_store import ensure_project, read_json

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query_documents(request: QueryRequest) -> QueryResponse:
    """Execute the hybrid NHANES query pipeline."""
    executor = QueryExecutor(load_agent_settings())
    result = executor.run(query=request.query, project_name=request.project_name, paper_slug=request.paper_slug)
    return QueryResponse(markdown=result["markdown"], payload=result["payload"])


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str) -> DocumentResponse:
    """Return paper metadata and ingestion stats for a document identifier."""
    try:
        project_slug, paper_slug = document_id.split(":", 1)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="document_id must be <project_slug>:<paper_slug>.") from exc

    project = ensure_project(project_slug)
    metadata = read_json(project.metadata_path, {})
    paper = next((item for item in metadata.get("papers", []) if item.get("paper_slug") == paper_slug), None)
    if not paper:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentResponse(document_id=document_id, metadata=paper)


@router.get("/chunks/{chunk_id}", response_model=ChunkResponse)
def get_chunk(chunk_id: str) -> ChunkResponse:
    """Return chunk text and any saved extraction metadata."""
    try:
        project_slug, paper_slug, section, chunk_index = chunk_id.split(":", 3)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="chunk_id must be <project_slug>:<paper_slug>:<section>:<chunk_index>.") from exc

    project = ensure_project(project_slug)
    metadata = read_json(project.metadata_path, {})
    paper = next((item for item in metadata.get("papers", []) if item.get("paper_slug") == paper_slug), None)
    if not paper:
        raise HTTPException(status_code=404, detail="Chunk document not found.")

    chunks_path = Path(str((paper.get("manifest") or {}).get("chunks_jsonl") or ""))
    if not chunks_path.exists():
        raise HTTPException(status_code=404, detail="Chunk storage not found.")

    for line in chunks_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if str(row.get("section", "document")) == section and str(row.get("chunk_index", 1)) == chunk_index:
            return ChunkResponse(chunk_id=chunk_id, payload=row)
    raise HTTPException(status_code=404, detail="Chunk not found.")
