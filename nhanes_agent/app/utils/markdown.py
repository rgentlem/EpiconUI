from __future__ import annotations


def markdown_table_row(values: list[str]) -> str:
    """Render a deterministic Markdown table row."""
    escaped = [str(value).replace("\n", " ").replace("|", "\\|") for value in values]
    return "| " + " | ".join(escaped) + " |"
