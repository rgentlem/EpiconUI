from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from project_store import ensure_project, read_json
from rag_store import index_project_paper

router = APIRouter(tags=["admin"])


class ReindexRequest(BaseModel):
    """Request for full-paper vector reindexing."""

    project_name: str = Field(..., min_length=1)


@router.post("/admin/reindex")
def reindex_documents(request: ReindexRequest) -> dict:
    """Rebuild embeddings for all papers in a project."""
    project = ensure_project(request.project_name)
    metadata = read_json(project.metadata_path, {})
    reindexed: list[str] = []
    for paper in metadata.get("papers", []):
        index_project_paper(request.project_name, paper["paper_slug"])
        reindexed.append(paper["paper_slug"])
    return {
        "project_name": request.project_name,
        "reindexed_papers": reindexed,
        "count": len(reindexed),
    }
