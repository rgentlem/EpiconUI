from __future__ import annotations

import logging

from nhanes_agent.app.services.nhanes.nhanes_repository import NhanesRepository

logger = logging.getLogger(__name__)


def validate_cycles(cycle_mentions: list[dict], repository: NhanesRepository) -> list[dict]:
    """Validate extracted cycle mentions against the canonical cycle set."""
    results: list[dict] = []
    for mention in cycle_mentions:
        cycles = [cycle for cycle in mention["canonical_cycles"] if repository.validate_cycle(cycle)]
        status = "validated" if cycles else "unvalidated"
        if not cycles:
            logger.warning("Cycle validation failed for mention=%s", mention["raw_mention"])
        results.append(
            {
                **mention,
                "canonical_cycles": cycles,
                "validation_status": status,
            }
        )
    return results


def validate_components(component_mentions: list[dict], repository: NhanesRepository) -> list[dict]:
    """Validate extracted component mentions."""
    results: list[dict] = []
    for mention in component_mentions:
        valid = repository.validate_component(mention["canonical_component"])
        if not valid:
            logger.warning("Component validation failed for mention=%s", mention["raw_mention"])
        results.append(
            {
                **mention,
                "validation_status": "validated" if valid else "unvalidated",
            }
        )
    return results


def validate_variables(variable_mentions: list[dict], optional_cycle: str | None, optional_component: str | None, repository: NhanesRepository, threshold: float) -> list[dict]:
    """Validate variable mentions against NHANES metadata."""
    results: list[dict] = []
    for mention in variable_mentions:
        matches = repository.validate_variable(mention["candidate"], cycle=optional_cycle, component=optional_component)
        if not matches:
            logger.warning("Variable validation failed for mention=%s", mention["raw_mention"])
            results.append(
                {
                    "raw_mention": mention["raw_mention"],
                    "canonical_variable_name": "",
                    "canonical_label": "",
                    "component": optional_component or "",
                    "cycle": optional_cycle or "",
                    "validation_status": "unvalidated",
                    "confidence": min(float(mention["confidence"]), threshold - 0.01),
                    "match_source": mention["match_source"],
                    "validation_tier": "none",
                }
            )
            continue

        top_match = matches[0]
        results.append(
            {
                "raw_mention": mention["raw_mention"],
                "canonical_variable_name": top_match.variable_name,
                "canonical_label": top_match.canonical_label,
                "component": top_match.component,
                "cycle": top_match.cycle,
                "validation_status": "validated" if float(mention["confidence"]) >= threshold else "ambiguous",
                "confidence": float(mention["confidence"]),
                "match_source": mention["match_source"],
                "validation_tier": mention["match_source"],
            }
        )
    return results
