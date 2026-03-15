from __future__ import annotations

from pdf_tools import slugify


def make_document_id(project_name: str, paper_slug: str) -> str:
    """Build a stable document identifier."""
    return f"{slugify(project_name)}:{slugify(paper_slug)}"
