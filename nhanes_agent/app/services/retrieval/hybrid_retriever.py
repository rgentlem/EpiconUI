from __future__ import annotations

from typing import Any

from nhanes_agent.app.core.config import RetrievalWeights
from nhanes_agent.app.services.retrieval.lexical_retriever import retrieve_lexical_chunks
from nhanes_agent.app.services.retrieval.vector_retriever import retrieve_vector_chunks
from nhanes_agent.app.utils.text import tokenize


def _metadata_boost(text: str, filters: dict[str, str | None]) -> float:
    score = 0.0
    for key in ("cycle", "component"):
        value = (filters.get(key) or "").strip().lower()
        if value and value in text.lower():
            score += 1.0
    return score


def _entity_overlap(query: str, chunk_text: str) -> float:
    query_terms = set(tokenize(query))
    chunk_terms = set(tokenize(chunk_text))
    if not query_terms or not chunk_terms:
        return 0.0
    return len(query_terms & chunk_terms) / len(query_terms)


def search_chunks(query: str, filters: dict[str, str | None], *, project_name: str, paper_slug: str, top_k: int, weights: RetrievalWeights, base_dir: str | None = None) -> list[dict[str, Any]]:
    """Run hybrid retrieval by combining dense and lexical candidates."""
    merged: dict[str, dict[str, Any]] = {}
    for row in retrieve_vector_chunks(query, project_name, paper_slug, top_k=top_k):
        merged[row["chunk_id"]] = row
    for row in retrieve_lexical_chunks(query, project_name, paper_slug, top_k=top_k, base_dir=base_dir):
        current = merged.setdefault(row["chunk_id"], row)
        current["lexical_score"] = max(float(current.get("lexical_score", 0.0)), float(row["lexical_score"]))
        current.setdefault("chunk_text", row["chunk_text"])
        current.setdefault("section", row["section"])
        current.setdefault("document_id", row["document_id"])
        current.setdefault("chunk_index", row["chunk_index"])

    rows: list[dict[str, Any]] = []
    for row in merged.values():
        row["entity_overlap_score"] = _entity_overlap(query, row.get("chunk_text", ""))
        row["metadata_boost"] = _metadata_boost(row.get("chunk_text", ""), filters)
        row["hybrid_score"] = (
            weights.vector * float(row.get("vector_score", 0.0))
            + weights.lexical * float(row.get("lexical_score", 0.0))
            + weights.entity_overlap * float(row.get("entity_overlap_score", 0.0))
            + weights.metadata_boost * float(row.get("metadata_boost", 0.0))
        )
        rows.append(row)

    rows.sort(key=lambda item: (-float(item["hybrid_score"]), item["section"], int(item["chunk_index"])))
    return rows[:top_k]
