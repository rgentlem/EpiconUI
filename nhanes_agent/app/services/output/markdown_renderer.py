from __future__ import annotations

from nhanes_agent.app.services.output.json_renderer import render_json_summary
from nhanes_agent.app.utils.markdown import markdown_table_row


def render_markdown_answer(bundle: dict) -> str:
    """Render the required deterministic Markdown response template."""
    lines = [
        "# Query Result",
        "",
        "## Query",
        bundle["query"],
        "",
        "## Summary",
        bundle["summary"],
        "",
        "## Retrieved Evidence",
        "### Chunk References",
    ]
    for item in bundle["evidence"]:
        lines.extend(
            [
                f"- chunk_id: {item['chunk_id']}",
                f"  - document_id: {item['document_id']}",
                f"  - section: {item['section']}",
                f"  - score: {item['score']:.4f}",
                f"  - short_quote: \"{item['short_quote']}\"",
            ]
        )
    if not bundle["evidence"]:
        lines.append("- None found")

    lines.extend(
        [
            "",
            "## NHANES Cycles",
            markdown_table_row(["Raw Mention", "Canonical Cycle(s)", "Validation Status", "Confidence", "Evidence Chunk IDs"]),
            markdown_table_row(["---", "---", "---", "---", "---"]),
        ]
    )
    for row in bundle["cycles"]:
        lines.append(
            markdown_table_row(
                [
                    row["raw_mention"],
                    ", ".join(row["canonical_cycles"]) or "None found",
                    row["validation_status"],
                    f"{row['confidence']:.2f}",
                    ", ".join(row["evidence_chunk_ids"]) or "None found",
                ]
            )
        )
    if not bundle["cycles"]:
        lines.append(markdown_table_row(["None found", "None found", "unvalidated", "0.00", "None found"]))

    lines.extend(
        [
            "",
            "## NHANES Components",
            markdown_table_row(["Raw Mention", "Canonical Component", "Validation Status", "Confidence", "Evidence Chunk IDs"]),
            markdown_table_row(["---", "---", "---", "---", "---"]),
        ]
    )
    for row in bundle["components"]:
        lines.append(
            markdown_table_row(
                [
                    row["raw_mention"],
                    row["canonical_component"],
                    row["validation_status"],
                    f"{row['confidence']:.2f}",
                    ", ".join(row["evidence_chunk_ids"]) or "None found",
                ]
            )
        )
    if not bundle["components"]:
        lines.append(markdown_table_row(["None found", "None found", "unvalidated", "0.00", "None found"]))

    lines.extend(
        [
            "",
            "## NHANES Variables",
            markdown_table_row(["Raw Mention", "Canonical Variable Name", "Canonical Label", "Component", "Cycle", "Validation Status", "Confidence", "Evidence Chunk IDs"]),
            markdown_table_row(["---", "---", "---", "---", "---", "---", "---", "---"]),
        ]
    )
    for row in bundle["variables"]:
        lines.append(
            markdown_table_row(
                [
                    row["raw_mention"],
                    row["canonical_variable_name"] or "None found",
                    row["canonical_label"] or "None found",
                    row["component"] or "None found",
                    row["cycle"] or "None found",
                    row["validation_status"],
                    f"{row['confidence']:.2f}",
                    ", ".join(row["evidence_chunk_ids"]) or "None found",
                ]
            )
        )
    if not bundle["variables"]:
        lines.append(markdown_table_row(["None found", "None found", "None found", "None found", "None found", "unvalidated", "0.00", "None found"]))

    lines.extend(["", "## Notes"])
    for note in bundle["notes"]:
        lines.append(f"- {note}")
    if not bundle["notes"]:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Machine-Readable Summary",
            "```json",
            render_json_summary(bundle["machine_summary"]),
            "```",
        ]
    )
    return "\n".join(lines)
