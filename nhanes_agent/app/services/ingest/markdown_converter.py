from __future__ import annotations

from pathlib import Path

import pymupdf

from pdf_tools import extract_markdown


def convert_pdf_to_markdown(pdf_path: str | Path) -> str:
    """Convert a PDF into Markdown using the existing EpiconUI parser."""
    pdf_path = Path(pdf_path)
    with pymupdf.open(pdf_path) as doc:
        return extract_markdown(pdf_path, doc)
