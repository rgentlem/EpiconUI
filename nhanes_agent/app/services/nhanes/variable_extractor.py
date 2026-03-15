from __future__ import annotations

import re

VARIABLE_RE = re.compile(r"\b[A-Z][A-Z0-9]{3,15}\b")
ALIASES = {
    "bmi": "BMXBMI",
    "glycohemoglobin": "LBXGH",
    "systolic blood pressure": "BPXSY1",
    "age in years at screening": "RIDAGEYR",
}


def extract_variable_mentions(text: str) -> list[dict]:
    """Extract variable mentions from exact codes and common aliases."""
    results: list[dict] = []
    for match in VARIABLE_RE.finditer(text or ""):
        token = match.group(0)
        if "_" in token:
            continue
        results.append(
            {
                "raw_mention": token,
                "candidate": token,
                "confidence": 0.95,
                "match_source": "exact_code",
            }
        )

    lowered = (text or "").lower()
    for alias, candidate in ALIASES.items():
        if alias in lowered:
            results.append(
                {
                    "raw_mention": alias,
                    "candidate": candidate,
                    "confidence": 0.78,
                    "match_source": "alias",
                }
            )
    return results
