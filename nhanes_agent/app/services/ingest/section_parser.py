from __future__ import annotations

from pdf_tools import sections_from_markdown


def parse_sections(markdown: str) -> list[dict[str, str]]:
    """Split Markdown into named sections."""
    return [{"heading": title, "text": body} for title, body in sections_from_markdown(markdown)]
