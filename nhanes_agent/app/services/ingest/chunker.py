from __future__ import annotations

from pdf_tools import split_text_evenly


def chunk_sections(sections: list[dict[str, str]], target_tokens: int, overlap_tokens: int = 0) -> list[dict]:
    """Chunk parsed sections deterministically while preserving section grouping."""
    chunks: list[dict] = []
    for section in sections:
        heading = section.get("heading") or "document"
        texts = split_text_evenly(section.get("text", ""), target_tokens)
        total = len(texts)
        for index, chunk_text in enumerate(texts, start=1):
            chunks.append(
                {
                    "section": heading,
                    "chunk_index": index,
                    "total_chunks_in_section": total,
                    "text": chunk_text,
                }
            )
    if overlap_tokens <= 0:
        return chunks
    for index in range(1, len(chunks)):
        prev_words = str(chunks[index - 1].get("text", "")).split()
        if not prev_words:
            continue
        overlap = " ".join(prev_words[-overlap_tokens:])
        chunks[index]["text"] = f"{overlap} {chunks[index]['text']}".strip()
    return chunks
