from __future__ import annotations

from typing import Any

from rag_store import search_chunks


def retrieve_vector_chunks(query: str, project_name: str, paper_slug: str, top_k: int) -> list[dict[str, Any]]:
    """Retrieve top-k chunk candidates via pgvector similarity."""
    rows = search_chunks(query, project_name_or_slug=project_name, paper_name_or_slug=paper_slug, top_k=top_k)
    output: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        output.append(
            {
                "chunk_id": f"{paper_slug}:{row['section']}:{row['chunk_index']}",
                "document_id": f"{project_name}:{paper_slug}",
                "section": row["section"],
                "chunk_index": row["chunk_index"],
                "chunk_text": row["text"],
                "vector_score": max(0.0, 1.0 - float(row["distance"])),
                "lexical_score": 0.0,
                "entity_overlap_score": 0.0,
                "metadata_boost": 0.0,
                "rank": index,
            }
        )
    return output
