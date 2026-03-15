from __future__ import annotations

import re


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    """Tokenize text into simple alphanumeric terms."""
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


def short_quote(text: str, limit: int = 120) -> str:
    """Create a compact deterministic quote for output tables."""
    cleaned = " ".join((text or "").split())
    return cleaned[:limit] + ("..." if len(cleaned) > limit else "")
