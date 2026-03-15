from __future__ import annotations

import re

from nhanes_agent.app.services.nhanes.normalizer import normalize_component_name

TABLE_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,11}_[A-M]\b")


def extract_component_mentions(text: str) -> list[dict]:
    """Extract potential components or table references from text."""
    mentions: list[dict] = []
    lowered = (text or "").lower()
    for alias in ("demographics", "blood pressure", "body measures", "laboratory", "diabetes questionnaire"):
        if alias in lowered:
            mentions.append(
                {
                    "raw_mention": alias,
                    "canonical_component": normalize_component_name(alias),
                    "confidence": 0.8,
                    "match_source": "alias",
                }
            )
    for match in TABLE_RE.finditer(text or ""):
        mentions.append(
            {
                "raw_mention": match.group(0),
                "canonical_component": match.group(0),
                "confidence": 0.92,
                "match_source": "table_code",
            }
        )
    return mentions
