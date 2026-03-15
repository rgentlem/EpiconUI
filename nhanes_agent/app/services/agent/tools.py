from __future__ import annotations

from nhanes_agent.app.core.config import AgentSettings
from nhanes_agent.app.services.nhanes.component_extractor import extract_component_mentions
from nhanes_agent.app.services.nhanes.cycle_extractor import extract_cycle_mentions
from nhanes_agent.app.services.nhanes.variable_extractor import extract_variable_mentions
from nhanes_agent.app.services.retrieval.hybrid_retriever import search_chunks as hybrid_search_chunks


def search_chunks(query: str, filters: dict[str, str | None], *, project_name: str, paper_slug: str, settings: AgentSettings) -> list[dict]:
    """Internal tool: hybrid retrieval over chunk candidates."""
    return hybrid_search_chunks(
        query,
        filters,
        project_name=project_name,
        paper_slug=paper_slug,
        top_k=settings.top_k_retrieval,
        weights=settings.weights,
        base_dir=str(settings.base_dir) if settings.base_dir is not None else None,
    )


def extract_nhanes_entities(text: str) -> dict:
    """Internal tool: entity extraction over free text."""
    return {
        "cycles": extract_cycle_mentions(text),
        "variables": extract_variable_mentions(text),
        "components": extract_component_mentions(text),
        "raw_mentions": text,
        "confidence": 0.8,
    }
