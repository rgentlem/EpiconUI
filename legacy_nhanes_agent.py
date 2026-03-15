from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config_store import load_llm_config
from llm_client import create_chat_completion
from local_retrieval import retrieve_top_chunks
from nhanes_metadata_index import MetadataCandidate, search_metadata_candidates
from pdf_tools import slugify
from project_store import ensure_project, read_json, write_json
from rag_config import load_database_config

try:
    import psycopg
except ImportError:  # pragma: no cover - optional dependency
    psycopg = None


YEAR_TO_CYCLE = {
    1999: "1999-2000",
    2000: "1999-2000",
    2001: "2001-2002",
    2002: "2001-2002",
    2003: "2003-2004",
    2004: "2003-2004",
    2005: "2005-2006",
    2006: "2005-2006",
    2007: "2007-2008",
    2008: "2007-2008",
    2009: "2009-2010",
    2010: "2009-2010",
    2011: "2011-2012",
    2012: "2011-2012",
    2013: "2013-2014",
    2014: "2013-2014",
    2015: "2015-2016",
    2016: "2015-2016",
    2017: "2017-2018",
    2018: "2017-2018",
    2019: "2019-2020",
    2020: "2019-2020",
    2021: "2021-2022",
    2022: "2021-2022",
    2023: "2023-2024",
    2024: "2023-2024",
}

SUFFIX_TO_CYCLE = {
    "A": "1999-2000",
    "B": "2001-2002",
    "C": "2003-2004",
    "D": "2005-2006",
    "E": "2007-2008",
    "F": "2009-2010",
    "G": "2011-2012",
    "H": "2013-2014",
    "I": "2015-2016",
    "J": "2017-2018",
    "K": "2019-2020",
    "L": "2021-2022",
    "M": "2023-2024",
}

ABSTRACT_SECTION_HINTS = ("abstract", "summary")
METHODS_SECTION_HINTS = (
    "method",
    "methods",
    "materials and methods",
    "patients and methods",
    "subjects and methods",
    "research design and methods",
    "study population",
    "participants",
    "sample",
    "dataset",
    "data",
    "analytic sample",
)
RESULTS_SECTION_HINTS = ("result", "results", "findings", "discussion")

RANGE_RE = re.compile(r"\b(19\d{2}|20\d{2})\s*[-\u2013]\s*(19\d{2}|20\d{2})\b")
THROUGH_RE = re.compile(r"\b(19\d{2}|20\d{2})\s+(?:through|to)\s+(19\d{2}|20\d{2})\b", re.IGNORECASE)
TABLE_SUFFIX_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,11}_([A-M])\b")

INTENT_SCHEMA = {
    "intent": "cycle_identification",
    "reason": "brief explanation",
}

EVIDENCE_SCHEMA = {
    "summary": "short evidence-grounded interpretation",
    "cycles": [
        {
            "raw_mention": "2015-2018",
            "evidence_chunk_id": "Abstract:1",
            "evidence_quote": "used NHANES data from 2015-2018",
            "confidence": 0.97,
        }
    ],
    "components": [
        {
            "raw_mention": "demographics",
            "evidence_chunk_id": "Methods:1",
            "evidence_quote": "demographic variables were included",
            "confidence": 0.82,
        }
    ],
    "tables": [
        {
            "raw_mention": "DEMO_I",
            "evidence_chunk_id": "Methods:1",
            "evidence_quote": "demographics data were taken from DEMO_I",
            "confidence": 0.93,
        }
    ],
    "variables": [
        {
            "raw_mention": "RIDAGEYR",
            "evidence_chunk_id": "Methods:1",
            "evidence_quote": "age in years at screening (RIDAGEYR)",
            "confidence": 0.94,
        }
    ],
    "notes": [],
}

NHANES_RULES = """
NHANES is organized in 2-year cycles.
Map years to cycles as follows:
1999/2000->1999-2000, 2001/2002->2001-2002, 2003/2004->2003-2004, 2005/2006->2005-2006,
2007/2008->2007-2008, 2009/2010->2009-2010, 2011/2012->2011-2012, 2013/2014->2013-2014,
2015/2016->2015-2016, 2017/2018->2017-2018, 2019/2020->2019-2020, 2021/2022->2021-2022,
2023/2024->2023-2024.

NHANES table suffixes map to cycles:
A->1999-2000, B->2001-2002, C->2003-2004, D->2005-2006, E->2007-2008, F->2009-2010,
G->2011-2012, H->2013-2014, I->2015-2016, J->2017-2018, K->2019-2020, L->2021-2022, M->2023-2024.

Do not invent NHANES variables, tables, or cycles. Only extract what the evidence supports.
"""


@dataclass
class OutputPaths:
    output_dir: Path
    markdown_path: Path
    json_path: Path


def now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain a JSON object.")
    return json.loads(text[start : end + 1])


def require_psycopg() -> None:
    if psycopg is None:
        raise RuntimeError("psycopg is required for NHANES validation. Install requirements-rag.txt first.")


def connect_database(base_dir: str | Path | None = None):
    require_psycopg()
    config = load_database_config(base_dir)
    assert psycopg is not None
    return psycopg.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        dbname=config.dbname,
    )


def load_paper_record(
    project_name: str,
    paper_slug: str,
    base_dir: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    project = ensure_project(project_name, base_dir=base_dir)
    project_payload = read_json(project.metadata_path, {})
    for item in project_payload.get("papers", []):
        if item.get("paper_slug") != paper_slug:
            continue
        paper_path = Path(str(item.get("metadata_path") or Path(item.get("paper_dir", "")) / "paper.json"))
        paper_payload = read_json(paper_path, {})
        if not paper_payload:
            raise FileNotFoundError(f"Paper metadata not found for {paper_slug}.")
        return project_payload, paper_payload, project.metadata_path, paper_path
    raise FileNotFoundError(f"Paper not found in project {project_name}: {paper_slug}")


def load_agent_llm_config(base_dir: str | Path | None = None) -> dict[str, str]:
    config = load_llm_config(base_dir)
    if not config.get("configured"):
        raise ValueError("LLM connection is not configured yet. Save the API URL, model, and API key first.")
    return {
        "base_url": str(config["base_url"]),
        "api_key": str(config["api_key"]),
        "model": str(config["model"]),
        "system_prompt": str(config.get("system_prompt") or ""),
    }


def call_llm_json(
    messages: list[dict[str, str]],
    *,
    base_dir: str | Path | None = None,
    temperature: float = 0.1,
    max_tokens: int = 1200,
) -> dict[str, Any]:
    config = load_agent_llm_config(base_dir)
    result = create_chat_completion(
        base_url=config["base_url"],
        api_key=config["api_key"],
        model=config["model"],
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    payload = extract_json_object(result["content"])
    if not isinstance(payload, dict):
        raise RuntimeError("LLM response was not a JSON object.")
    return payload


def build_intent_messages(query: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "\n".join(
                [
                    "You route NHANES paper questions.",
                    "Return JSON only.",
                    "Allowed intents: cycle_identification, variable_identification, general_extraction.",
                    "Choose cycle_identification for questions about years, survey cycles, pooled years, or which NHANES cycle(s) were used.",
                    "Choose variable_identification for questions about NHANES variables, table names, components, covariates, exposures, or outcomes used in the paper.",
                    "Choose general_extraction only if the question is not primarily about cycles or variables.",
                ]
            ),
        },
        {
            "role": "user",
            "content": f"Query:\n{query}\n\nReturn JSON with this shape:\n{json.dumps(INTENT_SCHEMA, indent=2)}",
        },
    ]


def classify_query_intent(query: str, *, base_dir: str | Path | None = None) -> str:
    payload = call_llm_json(build_intent_messages(query), base_dir=base_dir, temperature=0.0, max_tokens=200)
    intent = str(payload.get("intent", "")).strip()
    if intent not in {"cycle_identification", "variable_identification", "general_extraction"}:
        raise RuntimeError(f"Unsupported intent returned by LLM: {intent or '<empty>'}")
    return intent


def section_bucket(section_name: str) -> str:
    lowered = section_name.strip().lower()
    if any(hint in lowered for hint in ABSTRACT_SECTION_HINTS):
        return "abstract"
    if any(hint in lowered for hint in METHODS_SECTION_HINTS):
        return "methods"
    if any(hint in lowered for hint in RESULTS_SECTION_HINTS):
        return "results"
    return "other"


def retrieval_query_for_intent(query: str, intent: str) -> str:
    if intent == "cycle_identification":
        return f"{query.strip()} abstract methods data years cycle survey participants sample"
    if intent == "variable_identification":
        return f"{query.strip()} methods variables covariates exposure outcome questionnaire laboratory examination tables"
    return query.strip()


def rerank_chunks(chunks: list[dict[str, Any]], intent: str) -> list[dict[str, Any]]:
    reranked: list[dict[str, Any]] = []
    for chunk in chunks:
        score = float(chunk.get("score", 0.0))
        bucket = section_bucket(str(chunk.get("section", "")))
        if intent == "cycle_identification":
            if bucket == "abstract":
                score += 4.0
            elif bucket == "methods":
                score += 3.0
            elif bucket == "results":
                score += 0.5
        elif intent == "variable_identification":
            if bucket == "methods":
                score += 4.0
            elif bucket == "abstract":
                score += 2.5
            elif bucket == "results":
                score += 1.5
        reranked.append({**chunk, "score": round(score, 4)})
    reranked.sort(
        key=lambda item: (
            -float(item.get("score", 0.0)),
            str(item.get("section", "")),
            int(item.get("chunk_index", 0)),
        )
    )
    return reranked


def select_evidence_chunks(chunks: list[dict[str, Any]], intent: str) -> tuple[list[dict[str, Any]], str]:
    priorities = {
        "cycle_identification": ("abstract", "methods", "results", "other"),
        "variable_identification": ("methods", "abstract", "results", "other"),
        "general_extraction": ("abstract", "methods", "results", "other"),
    }[intent]
    bucketed = {name: [] for name in priorities}
    for chunk in chunks:
        bucketed.setdefault(section_bucket(str(chunk.get("section", ""))), []).append(chunk)

    selected: list[dict[str, Any]] = []
    for bucket in priorities:
        selected.extend(bucketed.get(bucket, []))
        if len(selected) >= 4:
            break
    selected = selected[:4] if selected else chunks[:4]
    source = section_bucket(str(selected[0].get("section", ""))) if selected else "other"
    return selected, source


def build_evidence_prompt(query: str, chunks: list[dict[str, Any]], intent: str) -> list[dict[str, str]]:
    evidence_lines: list[str] = []
    for chunk in chunks:
        evidence_lines.append(
            "\n".join(
                [
                    f"Chunk ID: {chunk.get('section', 'document')}:{chunk.get('chunk_index', 1)}",
                    f"Section: {chunk.get('section', 'document')}",
                    f"Text: {chunk.get('text', '')}",
                ]
            )
        )

    task_lines = [
        "You are interpreting retrieved evidence from a scientific paper that uses NHANES.",
        NHANES_RULES.strip(),
        "Use only the supplied evidence.",
        "Return JSON only.",
        "Every extracted item must be supported by a specific evidence chunk.",
        "Leave arrays empty when the evidence does not justify an extraction.",
    ]
    if intent == "cycle_identification":
        task_lines.extend(
            [
                "The user is asking which NHANES cycles or years were used in the paper.",
                "Prefer abstract evidence first, then methods-oriented evidence.",
                "Extract raw year spans exactly as written, such as 2015-2018.",
            ]
        )
    elif intent == "variable_identification":
        task_lines.extend(
            [
                "The user is asking which NHANES variables, tables, or components were used in the paper.",
                "Prefer methods-oriented evidence first, then abstract, then results.",
                "Return actual variable codes only when the paper shows them. If the paper only names a construct like BMI, return that exact construct text in variables.",
            ]
        )
    else:
        task_lines.append("Summarize the NHANES-relevant evidence conservatively.")

    evidence_text = "\n\n".join(evidence_lines)

    return [
        {"role": "system", "content": "\n".join(task_lines)},
        {
            "role": "user",
            "content": (
                f"Query:\n{query}\n\n"
                f"Evidence:\n\n{evidence_text}\n\n"
                f"Return JSON with this shape:\n{json.dumps(EVIDENCE_SCHEMA, indent=2)}"
            ),
        },
    ]


def normalize_llm_cycle_mentions(llm_payload: dict[str, Any], chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    known_chunk_ids = {
        f"{chunk.get('section', 'document')}:{chunk.get('chunk_index', 1)}" for chunk in chunks
    }
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in llm_payload.get("cycles", []):
        if not isinstance(item, dict):
            continue
        raw = str(item.get("raw_mention", "")).strip()
        evidence_chunk_id = str(item.get("evidence_chunk_id", "")).strip()
        if not raw or raw in seen:
            continue
        if evidence_chunk_id and evidence_chunk_id not in known_chunk_ids:
            continue
        seen.add(raw)
        rows.append(
            {
                "raw": raw,
                "source": "llm_evidence_interpretation",
                "confidence": min(0.99, max(0.0, float(item.get("confidence", 0.0) or 0.0))),
                "evidence_chunk_id": evidence_chunk_id,
                "evidence_quote": str(item.get("evidence_quote", "")).strip(),
            }
        )
    return rows


def normalize_llm_entity_mentions(
    llm_payload: dict[str, Any],
    chunks: list[dict[str, Any]],
    key: str,
    field_name: str,
) -> list[dict[str, Any]]:
    known_chunk_ids = {
        f"{chunk.get('section', 'document')}:{chunk.get('chunk_index', 1)}" for chunk in chunks
    }
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in llm_payload.get(key, []):
        if not isinstance(item, dict):
            continue
        raw = str(item.get("raw_mention", "")).strip()
        evidence_chunk_id = str(item.get("evidence_chunk_id", "")).strip()
        if not raw or raw in seen:
            continue
        if evidence_chunk_id and evidence_chunk_id not in known_chunk_ids:
            continue
        seen.add(raw)
        rows.append(
            {
                field_name: raw,
                "raw": raw,
                "source": "llm_evidence_interpretation",
                "confidence": min(0.99, max(0.0, float(item.get("confidence", 0.0) or 0.0))),
                "evidence_chunk_id": evidence_chunk_id,
                "evidence_quote": str(item.get("evidence_quote", "")).strip(),
            }
        )
    return rows


def build_variable_candidate_messages(
    query: str,
    evidence_chunks: list[dict[str, Any]],
    raw_mentions: list[str],
    cycles: list[str],
    candidates: list[MetadataCandidate],
) -> list[dict[str, str]]:
    evidence_lines = []
    for chunk in evidence_chunks:
        evidence_lines.append(
            "\n".join(
                [
                    f"Chunk ID: {chunk.get('section', 'document')}:{chunk.get('chunk_index', 1)}",
                    f"Section: {chunk.get('section', 'document')}",
                    f"Text: {chunk.get('text', '')}",
                ]
            )
        )
    candidate_rows = [
        {
            "variable_name": row.variable_name,
            "table_name": row.table_name,
            "canonical_label": row.canonical_label,
            "component": row.component,
            "cycle": row.cycle,
            "score": round(row.total_score, 4),
        }
        for row in candidates
    ]
    evidence_text = "\n\n".join(evidence_lines)
    schema = {
        "variables": [
            {
                "variable_name": "RIDAGEYR",
                "table_name": "DEMO_I",
                "canonical_label": "Age in years at screening",
                "component": "Demographics",
                "cycle": "2015-2016",
                "evidence_chunk_id": "Methods:1",
                "confidence": 0.95,
            }
        ],
        "tables": [],
        "notes": [],
    }
    return [
        {
            "role": "system",
            "content": "\n".join(
                [
                    "You are selecting validated NHANES metadata candidates for a scientific paper.",
                    "Use only the supplied evidence and candidate metadata rows.",
                    "Do not invent variables or tables.",
                    "Return only candidates that are clearly supported by the evidence.",
                    "If no candidate is adequately supported, return an empty variables array.",
                    "Return JSON only.",
                ]
            ),
        },
        {
            "role": "user",
            "content": (
                f"Query:\n{query}\n\n"
                f"Raw evidence mentions:\n{json.dumps(raw_mentions, indent=2)}\n\n"
                f"Inferred cycles:\n{json.dumps(cycles, indent=2)}\n\n"
                f"Evidence:\n\n{evidence_text}\n\n"
                f"Candidate metadata rows:\n{json.dumps(candidate_rows, indent=2)}\n\n"
                f"Return JSON with this shape:\n{json.dumps(schema, indent=2)}"
            ),
        },
    ]


def normalize_candidate_selection(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in payload.get("variables", []):
        if not isinstance(item, dict):
            continue
        variable_name = str(item.get("variable_name", "")).strip()
        table_name = str(item.get("table_name", "")).strip()
        if not variable_name or not table_name:
            continue
        key = (variable_name, table_name)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "variable_name": variable_name,
                "table_name": table_name,
                "canonical_label": str(item.get("canonical_label", "")).strip(),
                "component": str(item.get("component", "")).strip(),
                "cycle": str(item.get("cycle", "")).strip(),
                "evidence_chunk_id": str(item.get("evidence_chunk_id", "")).strip(),
                "confidence": min(0.99, max(0.0, float(item.get("confidence", 0.0) or 0.0))),
            }
        )
    return rows


def normalize_cycle_range(start_year: int, end_year: int) -> str | None:
    if end_year == start_year + 1:
        return f"{start_year}-{end_year}"
    return None


def expand_cycle_range(start_year: int, end_year: int) -> list[str]:
    cycles: list[str] = []
    for year in sorted(YEAR_TO_CYCLE):
        cycle = YEAR_TO_CYCLE[year]
        cycle_start = int(cycle.split("-", 1)[0])
        cycle_end = int(cycle.split("-", 1)[1])
        if cycle_start >= start_year and cycle_end <= end_year and cycle not in cycles:
            cycles.append(cycle)
    return cycles


def canonicalize_cycle_mention(raw_mention: str) -> list[str]:
    raw = raw_mention.strip()
    range_match = RANGE_RE.search(raw) or THROUGH_RE.search(raw)
    if range_match:
        start_year = int(range_match.group(1))
        end_year = int(range_match.group(2))
        cycle = normalize_cycle_range(start_year, end_year)
        if cycle:
            return [cycle]
        return expand_cycle_range(start_year, end_year)

    suffix_match = TABLE_SUFFIX_RE.search(raw)
    if suffix_match:
        cycle = SUFFIX_TO_CYCLE.get(suffix_match.group(1))
        return [cycle] if cycle else []

    if raw.isdigit():
        cycle = YEAR_TO_CYCLE.get(int(raw))
        return [cycle] if cycle else []
    return []


def validate_cycle_mentions(cycles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for row in cycles:
        canonical_cycles = canonicalize_cycle_mention(str(row.get("raw", "")))
        validated.append(
            {
                **row,
                "canonical_cycles": canonical_cycles,
                "status": "validated" if canonical_cycles else "unvalidated",
            }
        )
    return validated


def describe_columns(cur, schema_name: str, table_name: str) -> set[str]:
    cur.execute(f'SELECT * FROM "{schema_name}"."{table_name}" LIMIT 0;')
    return {desc.name for desc in cur.description or []}


def validate_tables(cur, tables: list[str]) -> list[dict[str, Any]]:
    if not tables:
        return []
    cur.execute(
        """
        SELECT DISTINCT "TableName"
        FROM "Metadata"."QuestionnaireVariables"
        WHERE "TableName" = ANY(%s)
        ORDER BY "TableName";
        """,
        (tables,),
    )
    found = {row[0] for row in cur.fetchall()}
    results: list[dict[str, Any]] = []
    for table in tables:
        suffix = table.rsplit("_", 1)[-1] if "_" in table else ""
        results.append(
            {
                "table_name": table,
                "exists": table in found,
                "cycle": SUFFIX_TO_CYCLE.get(suffix, ""),
                "confidence": 0.98 if table in found else 0.3,
            }
        )
    return results


def validate_variables(cur, variables: list[str]) -> list[dict[str, Any]]:
    if not variables:
        return []

    available_columns = describe_columns(cur, "Metadata", "QuestionnaireVariables")
    select_parts = ['"Variable"', '"TableName"']
    if "VariableDescription" in available_columns:
        select_parts.append('"VariableDescription"')
    elif "Variable Label" in available_columns:
        select_parts.append('"Variable Label"')
    else:
        select_parts.append("NULL::text AS variable_description")

    if "Component" in available_columns:
        select_parts.append('"Component"')
    elif "DataGroup" in available_columns:
        select_parts.append('"DataGroup" AS "Component"')
    else:
        select_parts.append("NULL::text AS \"Component\"")

    sql = f"""
        SELECT {", ".join(select_parts)}
        FROM "Metadata"."QuestionnaireVariables"
        WHERE "Variable" = ANY(%s)
        ORDER BY "Variable", "TableName";
    """
    cur.execute(sql, (variables,))
    rows = cur.fetchall()

    grouped: dict[str, list[tuple[Any, ...]]] = {}
    for row in rows:
        grouped.setdefault(str(row[0]), []).append(row)

    results: list[dict[str, Any]] = []
    for variable in variables:
        matches = grouped.get(variable, [])
        if not matches:
            results.append(
                {
                    "variable": variable,
                    "status": "not_found",
                    "matches": [],
                    "confidence": 0.2,
                }
            )
            continue

        normalized_matches = []
        for row in matches:
            table_name = str(row[1])
            suffix = table_name.rsplit("_", 1)[-1] if "_" in table_name else ""
            normalized_matches.append(
                {
                    "table_name": table_name,
                    "cycle": SUFFIX_TO_CYCLE.get(suffix, ""),
                    "description": str(row[2] or ""),
                    "component": str(row[3] or ""),
                }
            )
        results.append(
            {
                "variable": variable,
                "status": "validated",
                "matches": normalized_matches,
                "confidence": 0.99,
            }
        )
    return results


def build_canonical_matches(
    cycles: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    variables: list[dict[str, Any]],
    components: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cycle in cycles:
        for canonical_cycle in cycle.get("canonical_cycles", []):
            rows.append(
                {
                    "entity_type": "cycle",
                    "entity": canonical_cycle,
                    "status": cycle.get("status", "unvalidated"),
                    "confidence": cycle.get("confidence", 0.0),
                    "details": cycle.get("raw", ""),
                }
            )
    for table in tables:
        rows.append(
            {
                "entity_type": "table",
                "entity": table["table_name"],
                "status": "validated" if table["exists"] else "not_found",
                "confidence": table["confidence"],
                "details": table.get("cycle", ""),
            }
        )
    for variable in variables:
        rows.append(
            {
                "entity_type": "variable",
                "entity": variable["variable"],
                "status": variable["status"],
                "confidence": variable["confidence"],
                "details": ", ".join(match["table_name"] for match in variable.get("matches", [])[:4]),
            }
        )
    for component in components:
        rows.append(
            {
                "entity_type": "component",
                "entity": component["component"],
                "status": "inferred",
                "confidence": component.get("confidence", 0.0),
                "details": component.get("raw", ""),
            }
        )
    rows.sort(key=lambda item: (-float(item["confidence"]), item["entity_type"], item["entity"]))
    return rows


def build_summary(analysis: dict[str, Any]) -> str:
    intent = analysis["intent"]
    llm_summary = str(analysis.get("llm_summary", "")).strip()
    if intent == "cycle_identification":
        cycles = []
        raws = []
        for row in analysis["validated"]["cycles"]:
            for cycle in row.get("canonical_cycles", []):
                if cycle not in cycles:
                    cycles.append(cycle)
            raw = str(row.get("raw", "")).strip()
            if raw and raw not in raws:
                raws.append(raw)
        if cycles:
            lead = raws[0] if raws else ", ".join(cycles)
            source = analysis.get("evidence_source", "")
            location = {
                "abstract": " This was found in the abstract.",
                "methods": " This was found in the materials and methods section.",
                "results": " This was found in results-related text.",
            }.get(source, "")
            return f"The paper uses NHANES data from {lead}, corresponding to cycles {', '.join(cycles)}.{location}"
        return llm_summary or "I could not determine the NHANES cycles used in the paper from the retrieved evidence."

    if intent == "variable_identification":
        validated = [row["variable"] for row in analysis["validated"]["variables"] if row.get("status") == "validated"]
        if validated:
            source = analysis.get("evidence_source", "")
            location = {
                "methods": " This was found in the materials and methods section.",
                "abstract": " This was found in the abstract.",
                "results": " This was found in results-related text.",
            }.get(source, "")
            return f"The paper uses the NHANES variables {', '.join(validated[:10])}.{location}"
        return llm_summary or "I could not determine validated NHANES variable names from the retrieved evidence."

    return llm_summary or "I could not produce a validated NHANES-specific answer from the retrieved evidence."


def build_markdown_report(analysis: dict[str, Any]) -> str:
    lines = [
        "# NHANES Query Report",
        "",
        "## Query",
        analysis["query"],
        "",
        "## Summary",
        analysis["summary"],
        "",
        "## Evidence",
    ]
    for chunk in analysis["retrieval"]["chunks"]:
        text = str(chunk.get("text", "")).strip().replace("\n", " ")
        quote = text[:240] + ("..." if len(text) > 240 else "")
        lines.extend(
            [
                f"- {chunk.get('section', 'document')}:{chunk.get('chunk_index', 1)} (score {chunk.get('score', 0.0)})",
                f"  - {quote}",
            ]
        )
    if not analysis["retrieval"]["chunks"]:
        lines.append("- No evidence chunks were retrieved.")

    lines.extend(["", "## Validated Cycles"])
    if analysis["validated"]["cycles"]:
        for row in analysis["validated"]["cycles"]:
            cycles = ", ".join(row.get("canonical_cycles", [])) or "unvalidated"
            lines.append(f"- {row.get('raw', '')}: {cycles}")
    else:
        lines.append("- None found")

    lines.extend(["", "## Validated Tables"])
    if analysis["validated"]["tables"]:
        for row in analysis["validated"]["tables"]:
            status = "validated" if row.get("exists") else "not_found"
            cycle = row.get("cycle", "")
            suffix = f" ({cycle})" if cycle else ""
            lines.append(f"- {row['table_name']}: {status}{suffix}")
    else:
        lines.append("- None found")

    lines.extend(["", "## Validated Variables"])
    if analysis["validated"]["variables"]:
        for row in analysis["validated"]["variables"]:
            details = ", ".join(match["table_name"] for match in row.get("matches", [])[:4])
            details_text = f" [{details}]" if details else ""
            lines.append(f"- {row['variable']}: {row['status']}{details_text}")
    else:
        lines.append("- None found")

    lines.extend(["", "## Notes"])
    notes = list(analysis.get("interpretation_notes", []))
    if analysis.get("llm_summary"):
        notes.insert(0, f"LLM interpretation: {analysis['llm_summary']}")
    if notes:
        lines.extend(f"- {note}" for note in notes)
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Machine Parseable JSON",
            "```json",
            json.dumps(analysis, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def output_paths(paper_metadata: dict[str, Any], query: str) -> OutputPaths:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    query_slug = slugify(query)[:48] or "query"
    output_dir = Path(str(paper_metadata.get("outputs_dir") or Path(paper_metadata["paper_dir"]) / "outputs"))
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{timestamp}-nhanes-query-{query_slug}"
    return OutputPaths(
        output_dir=output_dir,
        markdown_path=output_dir / f"{stem}.md",
        json_path=output_dir / f"{stem}.json",
    )


def update_output_metadata(
    project_metadata: dict[str, Any],
    paper_metadata: dict[str, Any],
    project_metadata_path: Path,
    paper_metadata_path: Path,
    output_record: dict[str, Any],
) -> None:
    paper_outputs = list(paper_metadata.get("outputs", []))
    paper_outputs.insert(0, output_record)
    paper_metadata["outputs"] = paper_outputs[:25]
    write_json(paper_metadata_path, paper_metadata)

    for item in project_metadata.get("papers", []):
        if item.get("paper_slug") != paper_metadata.get("paper_slug"):
            continue
        outputs = list(item.get("outputs", []))
        outputs.insert(0, output_record)
        item["outputs"] = outputs[:25]
    project_metadata["updated_at"] = now_iso()
    write_json(project_metadata_path, project_metadata)


def run_nhanes_extraction_query(
    project_name: str,
    paper_slug: str,
    query: str,
    *,
    base_dir: str | Path | None = None,
    top_k: int = 8,
    save_output: bool = True,
) -> dict[str, Any]:
    if not query.strip():
        raise ValueError("Query is required.")

    project_metadata, paper_metadata, project_metadata_path, paper_metadata_path = load_paper_record(
        project_name,
        paper_slug,
        base_dir=base_dir,
    )
    manifest = paper_metadata.get("manifest", {})
    chunks_jsonl = manifest.get("chunks_jsonl")
    if not chunks_jsonl:
        raise RuntimeError("Paper manifest is missing chunks_jsonl.")

    intent = classify_query_intent(query, base_dir=base_dir)
    retrieval_query = retrieval_query_for_intent(query, intent)
    candidate_count = max(top_k, 12)
    retrieval = retrieve_top_chunks(retrieval_query, chunks_jsonl, top_k=candidate_count)
    retrieval = rerank_chunks(retrieval, intent)
    evidence_chunks, evidence_source = select_evidence_chunks(retrieval, intent)
    llm_payload = call_llm_json(
        build_evidence_prompt(query, evidence_chunks, intent),
        base_dir=base_dir,
        temperature=0.1,
        max_tokens=1200,
    )

    cycles = validate_cycle_mentions(normalize_llm_cycle_mentions(llm_payload, evidence_chunks))
    table_mentions = normalize_llm_entity_mentions(llm_payload, evidence_chunks, "tables", "table_name")
    variable_mentions = normalize_llm_entity_mentions(llm_payload, evidence_chunks, "variables", "variable")
    component_mentions = normalize_llm_entity_mentions(llm_payload, evidence_chunks, "components", "component")

    metadata_candidates: list[MetadataCandidate] = []
    selected_metadata_variables: list[dict[str, Any]] = []
    if intent == "variable_identification":
        cycle_filters = sorted(
            {
                cycle
                for row in cycles
                if row.get("status") == "validated"
                for cycle in row.get("canonical_cycles", [])
            }
        )
        component_filters = sorted({str(item.get("component", "")).strip() for item in component_mentions if str(item.get("component", "")).strip()})
        raw_variable_mentions = [str(item.get("variable", "")).strip() for item in variable_mentions if str(item.get("variable", "")).strip()]
        metadata_query_parts = [query.strip(), *raw_variable_mentions]
        metadata_query = " | ".join(part for part in metadata_query_parts if part)
        metadata_candidates = search_metadata_candidates(
            query=metadata_query or query.strip(),
            cycles=cycle_filters,
            components=component_filters,
            top_k=12,
            base_dir=base_dir,
        )
        selection_payload = call_llm_json(
            build_variable_candidate_messages(
                query,
                evidence_chunks,
                raw_variable_mentions,
                cycle_filters,
                metadata_candidates,
            ),
            base_dir=base_dir,
            temperature=0.1,
            max_tokens=900,
        )
        selected_metadata_variables = normalize_candidate_selection(selection_payload)

    with connect_database(base_dir=base_dir) as conn, conn.cursor() as cur:
        validated_tables = validate_tables(
            cur,
            sorted(
                {
                    item["table_name"]
                    for item in table_mentions
                }
                | {
                    item["table_name"]
                    for item in selected_metadata_variables
                    if item.get("table_name")
                }
            ),
        )
        validated_variables = validate_variables(
            cur,
            sorted(
                {
                    item["variable"]
                    for item in variable_mentions
                }
                | {
                    item["variable_name"]
                    for item in selected_metadata_variables
                    if item.get("variable_name")
                }
            ),
        )

    interpretation_notes = [str(item).strip() for item in llm_payload.get("notes", []) if str(item).strip()]
    for row in cycles:
        if row["status"] != "validated":
            interpretation_notes.append(f"Unvalidated cycle mention: {row.get('raw', '')}")
    for row in validated_variables:
        if row["status"] != "validated":
            interpretation_notes.append(f"Unvalidated variable mention: {row.get('variable', '')}")
    for row in validated_tables:
        if not row["exists"]:
            interpretation_notes.append(f"Unvalidated table mention: {row.get('table_name', '')}")

    analysis = {
        "agent": "llm_validated_nhanes_query",
        "intent": intent,
        "query": query.strip(),
        "project_name": project_metadata["project_name"],
        "project_slug": project_metadata["project_slug"],
        "paper_name": paper_metadata["paper_name"],
        "paper_slug": paper_metadata["paper_slug"],
        "generated_at": now_iso(),
        "retrieval": {
            "mode": "llm_interpreted_ranked_chunks",
            "chunk_count": len(evidence_chunks),
            "candidate_chunk_count": len(retrieval),
            "retrieval_query": retrieval_query,
            "chunks": evidence_chunks,
        },
        "extracted": {
            "cycles": cycles,
            "tables": table_mentions,
            "variables": variable_mentions,
            "components": component_mentions,
        },
        "validated": {
            "cycles": cycles,
            "tables": validated_tables,
            "variables": validated_variables,
            "components": component_mentions,
        },
        "llm_used": True,
        "llm_summary": str(llm_payload.get("summary", "")).strip(),
        "evidence_source": evidence_source,
        "interpretation_notes": interpretation_notes,
    }
    if metadata_candidates:
        analysis["metadata_candidates"] = [
            {
                "variable_name": row.variable_name,
                "table_name": row.table_name,
                "canonical_label": row.canonical_label,
                "component": row.component,
                "cycle": row.cycle,
                "total_score": row.total_score,
            }
            for row in metadata_candidates
        ]
    if selected_metadata_variables:
        analysis["selected_metadata_variables"] = selected_metadata_variables
    analysis["canonical_matches"] = build_canonical_matches(
        cycles,
        validated_tables,
        validated_variables,
        component_mentions,
    )
    analysis["summary"] = build_summary(analysis)
    analysis["quick_answer"] = analysis["summary"]

    markdown = build_markdown_report(analysis)
    output_record = None
    if save_output:
        paths = output_paths(paper_metadata, query)
        paths.markdown_path.write_text(markdown, encoding="utf-8")
        paths.json_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
        output_record = {
            "output_id": paths.markdown_path.stem,
            "title": f"NHANES query: {query.strip()[:72]}",
            "kind": "nhanes_extraction",
            "created_at": analysis["generated_at"],
            "query": query.strip(),
            "summary": analysis["summary"],
            "markdown_path": str(paths.markdown_path),
            "json_path": str(paths.json_path),
        }
        update_output_metadata(project_metadata, paper_metadata, project_metadata_path, paper_metadata_path, output_record)

    return {
        "ok": True,
        "answer": markdown.split("## Machine Parseable JSON", 1)[0].strip(),
        "quick_answer": analysis["quick_answer"],
        "output": output_record,
        "analysis": analysis,
        "saved_output": save_output,
    }
