from __future__ import annotations

import re


def clean_markdown(markdown: str) -> str:
    """Normalize Markdown whitespace deterministically."""
    text = markdown.replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
