from __future__ import annotations

from nhanes_agent.app.services.output.markdown_renderer import render_markdown_answer
from nhanes_agent.app.utils.text import short_quote


def build_answer(context_bundle: dict) -> dict:
    """Build the final deterministic Markdown and machine-readable payload."""
    evidence = [
        {
            "chunk_id": item["chunk_id"],
            "document_id": item["document_id"],
            "section": item["section"],
            "score": float(item["hybrid_score"]),
            "short_quote": short_quote(item.get("chunk_text", "")),
        }
        for item in context_bundle["chunks"]
    ]
    machine_summary = {
        "query": context_bundle["query"],
        "cycles": context_bundle["cycles"],
        "components": context_bundle["components"],
        "variables": context_bundle["variables"],
        "evidence_chunk_ids": [item["chunk_id"] for item in evidence],
    }
    summary = context_bundle["summary"]
    bundle = {
        "query": context_bundle["query"],
        "summary": summary,
        "evidence": evidence,
        "cycles": context_bundle["cycles"],
        "components": context_bundle["components"],
        "variables": context_bundle["variables"],
        "notes": context_bundle["notes"],
        "machine_summary": machine_summary,
    }
    return {
        "markdown": render_markdown_answer(bundle),
        "payload": bundle,
    }
