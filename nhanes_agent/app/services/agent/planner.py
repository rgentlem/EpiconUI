from __future__ import annotations

from nhanes_agent.app.services.nhanes.component_extractor import extract_component_mentions
from nhanes_agent.app.services.nhanes.cycle_extractor import extract_cycle_mentions


def build_retrieval_filters(query: str) -> dict[str, str | None]:
    """Infer metadata filters from the query before retrieval."""
    cycles = extract_cycle_mentions(query)
    components = extract_component_mentions(query)
    return {
        "cycle": cycles[0]["canonical_cycles"][0] if cycles and cycles[0]["canonical_cycles"] else None,
        "component": components[0]["canonical_component"] if components else None,
    }
