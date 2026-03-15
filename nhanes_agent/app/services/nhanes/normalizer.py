from __future__ import annotations

from legacy_nhanes_agent import YEAR_TO_CYCLE, SUFFIX_TO_CYCLE

COMPONENT_ALIASES = {
    "demographics": "Demographics",
    "demographic": "Demographics",
    "blood pressure": "Blood Pressure",
    "body measures": "Body Measures",
    "laboratory": "Laboratory",
    "lab": "Laboratory",
    "diabetes questionnaire": "Diabetes Questionnaire",
}


def expand_cycle_range(start_year: int, end_year: int) -> list[str]:
    """Expand pooled year ranges into canonical two-year NHANES cycles."""
    cycles: list[str] = []
    for year in range(start_year, end_year + 1, 2):
        cycle = YEAR_TO_CYCLE.get(year)
        if cycle and cycle not in cycles:
            cycles.append(cycle)
    return cycles


def normalize_component_name(raw: str) -> str:
    """Map aliases to canonical component names."""
    lowered = raw.strip().lower()
    return COMPONENT_ALIASES.get(lowered, raw.strip().title())


def cycle_from_suffix(table_name: str) -> str:
    """Infer the cycle from a table suffix when available."""
    suffix = table_name.rsplit("_", 1)[-1].upper()
    return SUFFIX_TO_CYCLE.get(suffix, "")
