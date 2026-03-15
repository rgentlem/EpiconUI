from __future__ import annotations

from pathlib import Path


def load_pdf_bytes(path: str | Path) -> bytes:
    """Read the source PDF bytes from disk."""
    return Path(path).read_bytes()
