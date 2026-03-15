from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "what",
    "which",
    "with",
}


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "") if token and token.lower() not in STOPWORDS]


def load_chunks(chunks_jsonl_path: str | Path) -> list[dict[str, Any]]:
    path = Path(chunks_jsonl_path)
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        rows.append(json.loads(stripped))
    return rows


def score_chunk(query_tokens: list[str], chunk_text: str) -> float:
    if not query_tokens:
        return 0.0

    chunk_tokens = tokenize(chunk_text)
    if not chunk_tokens:
        return 0.0

    chunk_counts = Counter(chunk_tokens)
    unique_matches = {token for token in query_tokens if token in chunk_counts}
    overlap_score = float(sum(chunk_counts[token] for token in unique_matches))
    coverage_score = len(unique_matches) / max(1, len(set(query_tokens)))
    density_penalty = math.log(len(chunk_tokens) + 8, 2)
    return (overlap_score + (coverage_score * 4.0)) / density_penalty


def retrieve_top_chunks(query: str, chunks_jsonl_path: str | Path, top_k: int = 8) -> list[dict[str, Any]]:
    query_tokens = tokenize(query)
    scored: list[dict[str, Any]] = []
    for row in load_chunks(chunks_jsonl_path):
        text = str(row.get("text") or row.get("markdown") or "")
        score = score_chunk(query_tokens, text)
        if score <= 0:
            continue
        scored.append(
            {
                **row,
                "score": round(score, 4),
            }
        )

    scored.sort(key=lambda item: (-float(item.get("score", 0.0)), str(item.get("section") or ""), int(item.get("chunk_index", 0))))
    if scored:
        return scored[:top_k]

    fallback = load_chunks(chunks_jsonl_path)[:top_k]
    for item in fallback:
        item["score"] = 0.0
    return fallback
