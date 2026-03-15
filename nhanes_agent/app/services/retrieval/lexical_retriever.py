from __future__ import annotations

from typing import Any

from local_retrieval import retrieve_top_chunks
from project_store import ensure_project, read_json


def retrieve_lexical_chunks(query: str, project_name: str, paper_slug: str, top_k: int, *, base_dir: str | None = None) -> list[dict[str, Any]]:
    """Retrieve top-k chunk candidates using local lexical overlap scoring."""
    project = ensure_project(project_name, base_dir=base_dir)
    project_metadata = read_json(project.metadata_path, {})
    paper = next((item for item in project_metadata.get("papers", []) if item.get("paper_slug") == paper_slug), None)
    if not paper:
        return []
    chunks_path = str((paper.get("manifest") or {}).get("chunks_jsonl") or "")
    if not chunks_path:
        return []
    rows = retrieve_top_chunks(query, chunks_path, top_k=top_k)
    output: list[dict[str, Any]] = []
    for row in rows:
        output.append(
            {
                "chunk_id": f"{paper_slug}:{row.get('section', 'document')}:{row.get('chunk_index', 1)}",
                "document_id": f"{project_name}:{paper_slug}",
                "section": row.get("section", "document"),
                "chunk_index": int(row.get("chunk_index", 1)),
                "chunk_text": str(row.get("text", "")),
                "vector_score": 0.0,
                "lexical_score": float(row.get("score", 0.0)),
                "entity_overlap_score": 0.0,
                "metadata_boost": 0.0,
            }
        )
    return output
