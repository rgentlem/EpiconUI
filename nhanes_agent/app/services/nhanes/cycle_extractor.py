from __future__ import annotations

import re

from nhanes_agent.app.services.nhanes.normalizer import expand_cycle_range

RANGE_RE = re.compile(r"\b(19\d{2}|20\d{2})\s*[-\u2013]\s*(19\d{2}|20\d{2})\b")
THROUGH_RE = re.compile(r"\b(19\d{2}|20\d{2})\s+(?:through|to)\s+(19\d{2}|20\d{2})\b", re.IGNORECASE)


def extract_cycle_mentions(text: str) -> list[dict]:
    """Extract raw cycle mentions and normalize them to canonical cycle lists."""
    results: list[dict] = []
    for regex, base_confidence in ((RANGE_RE, 0.96), (THROUGH_RE, 0.88)):
        for match in regex.finditer(text or ""):
            start_year = int(match.group(1))
            end_year = int(match.group(2))
            if end_year == start_year + 1:
                cycles = [f"{start_year}-{end_year}"]
            else:
                cycles = expand_cycle_range(start_year, end_year)
            results.append(
                {
                    "raw_mention": match.group(0),
                    "canonical_cycles": cycles,
                    "confidence": base_confidence if cycles else 0.2,
                }
            )
    return results
