from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import pymupdf
except ImportError:  # pragma: no cover - optional dependency at import time
    pymupdf = None

try:
    import pymupdf4llm
except ImportError:  # pragma: no cover - optional dependency
    pymupdf4llm = None


CAPTION_RE = re.compile(r"^(figure|fig\.?|table)\s+([a-z0-9ivx.-]+)?[:.\s-]+", re.IGNORECASE)
SECTION_HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
STANDALONE_HEADING_RE = re.compile(
    r"(?m)^(abstract|introduction|background|methods?|materials and methods|results|discussion|conclusion|references|appendix)\s*$",
    re.IGNORECASE,
)
FOOTER_PATTERNS = [
    re.compile(r"\bpage\s+\d+\s+of\s+\d+\b", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$", re.IGNORECASE),
]


@dataclass
class Caption:
    id: str
    kind: str
    label: str
    text: str
    page: int
    section: str
    bbox: list[float]


@dataclass
class TableArtifact:
    id: str
    page: int
    section: str
    caption_id: str | None
    caption_text: str | None
    bbox: list[float]
    markdown_path: str
    row_count: int
    column_count: int


@dataclass
class FigureArtifact:
    id: str
    page: int
    section: str
    caption_id: str | None
    caption_text: str | None
    bbox: list[float]
    image_path: str
    source: str


@dataclass
class Chunk:
    id: str
    paper_id: str
    section: str
    chunk_index: int
    total_chunks_in_section: int
    token_estimate: int
    text: str
    markdown: str


def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower()).strip("-")
    return value or "document"


def normalize_space(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_page_text(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if any(pattern.search(line) for pattern in FOOTER_PATTERNS):
            continue
        cleaned_lines.append(line)
    return normalize_space("\n".join(cleaned_lines))


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def split_text_evenly(text: str, target_tokens: int) -> list[str]:
    text = normalize_space(text)
    if not text:
        return []

    words = text.split()
    if not words:
        return []

    total_tokens = estimate_tokens(text)
    if total_tokens <= target_tokens:
        return [text]

    chunk_count = max(1, math.ceil(total_tokens / target_tokens))
    target_words = max(1, math.ceil(len(words) / chunk_count))

    chunks: list[str] = []
    start = 0
    for remaining in range(chunk_count, 0, -1):
        words_left = len(words) - start
        current_size = max(1, math.ceil(words_left / remaining))
        current_size = min(current_size, max(target_words + 15, target_words))
        chunk_words = words[start : start + current_size]
        chunks.append(" ".join(chunk_words))
        start += current_size

    if start < len(words):
        chunks[-1] = f"{chunks[-1]} {' '.join(words[start:])}".strip()

    return [chunk for chunk in chunks if chunk.strip()]


def sections_from_markdown(markdown_text: str) -> list[tuple[str, str]]:
    text = normalize_space(markdown_text)
    if not text:
        return [("document", "")]

    matches = list(SECTION_HEADING_RE.finditer(text))
    if not matches:
        return [("document", text)]

    sections: list[tuple[str, str]] = []
    first_start = matches[0].start()
    if first_start > 0:
        preface = text[:first_start].strip()
        if preface:
            sections.append(("document", preface))

    for idx, match in enumerate(matches):
        title = normalize_space(match.group(2))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((title, body))

    return sections or [("document", text)]


def fallback_markdown_from_doc(doc: pymupdf.Document) -> str:
    parts: list[str] = []
    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        text = clean_page_text(page.get_text("text"))
        if not text:
            continue
        parts.append(f"## Page {page_index + 1}\n\n{text}")
    return "\n\n".join(parts)


def extract_markdown(pdf_path: Path, doc: pymupdf.Document) -> str:
    if pymupdf4llm is not None:
        try:
            return normalize_space(pymupdf4llm.to_markdown(str(pdf_path), write_images=False))
        except Exception:
            pass
    return fallback_markdown_from_doc(doc)


def extract_section_titles(markdown_text: str) -> list[str]:
    titles = [title for title, body in sections_from_markdown(markdown_text) if title != "document" and body]
    seen: set[str] = set()
    unique_titles: list[str] = []
    for title in titles:
        key = slugify(title)
        if key in seen:
            continue
        seen.add(key)
        unique_titles.append(title)
    return unique_titles


def make_section_matchers(titles: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    matchers: list[tuple[str, re.Pattern[str]]] = []
    for title in titles:
        escaped = re.escape(title).replace(r"\ ", r"\s+")
        matchers.append((title, re.compile(rf"(?im)^\s*{escaped}\s*$")))
    return matchers


def detect_page_sections(doc: pymupdf.Document, markdown_text: str) -> dict[int, str]:
    titles = extract_section_titles(markdown_text)
    matchers = make_section_matchers(titles)
    current_section = "document"
    page_sections: dict[int, str] = {}

    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        page_text = page.get_text("text")
        matched = False
        for title, matcher in matchers:
            if matcher.search(page_text):
                current_section = title
                matched = True
                break

        if not matched:
            standalone = STANDALONE_HEADING_RE.search(page_text)
            if standalone:
                current_section = normalize_space(standalone.group(1)).title()

        page_sections[page_index + 1] = current_section

    return page_sections


def line_from_dict(line: dict[str, Any]) -> tuple[str, list[float]] | None:
    spans = line.get("spans", [])
    text = "".join(span.get("text", "") for span in spans).strip()
    if not text:
        return None
    bbox = line.get("bbox")
    if not bbox:
        return None
    return text, [float(value) for value in bbox]


def merge_caption_lines(lines: list[tuple[str, list[float]]]) -> tuple[str, list[float]]:
    text = " ".join(part for part, _bbox in lines)
    left = min(bbox[0] for _text, bbox in lines)
    top = min(bbox[1] for _text, bbox in lines)
    right = max(bbox[2] for _text, bbox in lines)
    bottom = max(bbox[3] for _text, bbox in lines)
    return normalize_space(text), [left, top, right, bottom]


def extract_captions(doc: pymupdf.Document, page_sections: dict[int, str]) -> list[Caption]:
    captions: list[Caption] = []
    counter = 1

    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        blocks = page.get_text("dict").get("blocks", [])
        page_lines: list[tuple[str, list[float]]] = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                item = line_from_dict(line)
                if item:
                    page_lines.append(item)

        idx = 0
        while idx < len(page_lines):
            text, bbox = page_lines[idx]
            if not CAPTION_RE.match(text):
                idx += 1
                continue

            merged = [(text, bbox)]
            next_idx = idx + 1
            while next_idx < len(page_lines):
                next_text, next_bbox = page_lines[next_idx]
                vertical_gap = next_bbox[1] - merged[-1][1][3]
                aligned = abs(next_bbox[0] - merged[0][1][0]) <= 28
                if CAPTION_RE.match(next_text):
                    break
                if vertical_gap > 24 or not aligned:
                    break
                merged.append((next_text, next_bbox))
                next_idx += 1

            caption_text, caption_bbox = merge_caption_lines(merged)
            match = CAPTION_RE.match(caption_text)
            label = match.group(0).strip() if match else caption_text.split(" ", 1)[0]
            kind_token = match.group(1).lower() if match else "caption"
            kind = "figure" if kind_token.startswith("fig") else "table" if kind_token == "table" else "caption"
            captions.append(
                Caption(
                    id=f"cap-{counter:03d}",
                    kind=kind,
                    label=label,
                    text=caption_text,
                    page=page_index + 1,
                    section=page_sections.get(page_index + 1, "document"),
                    bbox=caption_bbox,
                )
            )
            counter += 1
            idx = next_idx

    return captions


def markdown_table(rows: list[list[Any]]) -> str:
    cleaned_rows: list[list[str]] = []
    max_cols = 0
    for row in rows:
        normalized = [normalize_space(str(cell)) for cell in row]
        cleaned_rows.append(normalized)
        max_cols = max(max_cols, len(normalized))

    if max_cols == 0:
        return ""

    padded_rows = [row + [""] * (max_cols - len(row)) for row in cleaned_rows]
    header = padded_rows[0]
    body = padded_rows[1:] or [[""] * max_cols]
    separator = ["---"] * max_cols

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


def bbox_distance(a: list[float], b: list[float]) -> float:
    ax_mid = (a[0] + a[2]) / 2
    ay_mid = (a[1] + a[3]) / 2
    bx_mid = (b[0] + b[2]) / 2
    by_mid = (b[1] + b[3]) / 2
    return math.hypot(ax_mid - bx_mid, ay_mid - by_mid)


def nearest_caption(
    captions: list[Caption],
    page: int,
    kind: str,
    bbox: list[float],
) -> Caption | None:
    candidates = [caption for caption in captions if caption.page == page and caption.kind == kind]
    if not candidates:
        return None
    return min(candidates, key=lambda caption: bbox_distance(caption.bbox, bbox))


def extract_tables(
    doc: pymupdf.Document,
    output_dir: Path,
    captions: list[Caption],
    page_sections: dict[int, str],
) -> list[TableArtifact]:
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    tables: list[TableArtifact] = []
    counter = 1

    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        finder = getattr(page, "find_tables", None)
        if finder is None:
            continue

        try:
            found_tables = page.find_tables()
        except Exception:
            continue

        for table in getattr(found_tables, "tables", []):
            rows = table.extract() or []
            if not rows:
                continue

            table_md = markdown_table(rows)
            if not table_md.strip():
                continue

            table_id = f"table-{counter:03d}"
            markdown_path = tables_dir / f"{table_id}.md"
            caption = nearest_caption(captions, page_index + 1, "table", [float(v) for v in table.bbox])

            content_parts = [f"# {table_id}"]
            if caption:
                content_parts.append(f"\n{caption.text}\n")
            content_parts.append(table_md)
            markdown_path.write_text("\n\n".join(content_parts).strip() + "\n", encoding="utf-8")

            tables.append(
                TableArtifact(
                    id=table_id,
                    page=page_index + 1,
                    section=page_sections.get(page_index + 1, "document"),
                    caption_id=caption.id if caption else None,
                    caption_text=caption.text if caption else None,
                    bbox=[float(v) for v in table.bbox],
                    markdown_path=str(markdown_path),
                    row_count=len(rows),
                    column_count=max(len(row) for row in rows),
                )
            )
            counter += 1

    return tables


def save_pixmap(page: pymupdf.Page, clip: pymupdf.Rect, path: Path, dpi: int = 160) -> None:
    matrix = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=matrix, clip=clip, alpha=False)
    pix.save(path)


def extract_figures(
    doc: pymupdf.Document,
    output_dir: Path,
    captions: list[Caption],
    page_sections: dict[int, str],
) -> list[FigureArtifact]:
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    figures: list[FigureArtifact] = []
    seen_rects: set[tuple[int, tuple[int, int, int, int]]] = set()
    counter = 1

    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        image_items = page.get_images(full=True)

        for image_tuple in image_items:
            xref = image_tuple[0]
            rects = page.get_image_rects(xref)
            if not rects:
                continue

            try:
                image_bytes = doc.extract_image(xref)
            except Exception:
                image_bytes = None

            for rect_index, rect in enumerate(rects, start=1):
                rect_key = (
                    page_index + 1,
                    (
                        int(rect.x0),
                        int(rect.y0),
                        int(rect.x1),
                        int(rect.y1),
                    ),
                )
                if rect_key in seen_rects:
                    continue
                seen_rects.add(rect_key)

                figure_id = f"figure-{counter:03d}"
                caption = nearest_caption(captions, page_index + 1, "figure", [rect.x0, rect.y0, rect.x1, rect.y1])
                extension = image_bytes.get("ext", "png") if image_bytes else "png"
                image_path = figures_dir / f"{figure_id}.{extension}"

                if image_bytes and image_bytes.get("image"):
                    image_path.write_bytes(image_bytes["image"])
                    source = "embedded-image"
                else:
                    save_pixmap(page, rect, image_path.with_suffix(".png"))
                    image_path = image_path.with_suffix(".png")
                    source = "page-crop"

                figures.append(
                    FigureArtifact(
                        id=figure_id,
                        page=page_index + 1,
                        section=page_sections.get(page_index + 1, "document"),
                        caption_id=caption.id if caption else None,
                        caption_text=caption.text if caption else None,
                        bbox=[float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)],
                        image_path=str(image_path),
                        source=source,
                    )
                )
                counter += 1

        # Fallback: crop a region immediately above each figure caption if no image was linked.
        page_captions = [caption for caption in captions if caption.page == page_index + 1 and caption.kind == "figure"]
        for caption in page_captions:
            already_linked = any(figure.caption_id == caption.id for figure in figures)
            if already_linked:
                continue

            page_rect = page.rect
            clip_top = max(page_rect.y0, caption.bbox[1] - 220)
            clip_bottom = max(clip_top + 40, caption.bbox[1] - 12)
            clip = pymupdf.Rect(page_rect.x0 + 24, clip_top, page_rect.x1 - 24, clip_bottom)
            if clip.height < 40 or clip.width < 40:
                continue

            figure_id = f"figure-{counter:03d}"
            image_path = figures_dir / f"{figure_id}.png"
            save_pixmap(page, clip, image_path)

            figures.append(
                FigureArtifact(
                    id=figure_id,
                    page=page_index + 1,
                    section=page_sections.get(page_index + 1, "document"),
                    caption_id=caption.id,
                    caption_text=caption.text,
                    bbox=[float(clip.x0), float(clip.y0), float(clip.x1), float(clip.y1)],
                    image_path=str(image_path),
                    source="caption-heuristic-crop",
                )
            )
            counter += 1

    return figures


def captions_to_markdown(captions: list[Caption]) -> str:
    grouped: dict[str, list[Caption]] = {"figure": [], "table": [], "caption": []}
    for caption in captions:
        grouped.setdefault(caption.kind, []).append(caption)

    parts: list[str] = ["# Captions"]
    for kind in ("figure", "table", "caption"):
        items = grouped.get(kind, [])
        if not items:
            continue
        parts.append(f"\n## {kind.title()} Captions\n")
        for item in items:
            parts.append(f"### {item.id} ({item.section}, page {item.page})\n\n{item.text}")
    return "\n\n".join(parts).strip() + "\n"


def chunk_sections(markdown_text: str, paper_id: str, target_tokens: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    section_items = sections_from_markdown(markdown_text)

    for section_title, body in section_items:
        chunk_texts = split_text_evenly(body, target_tokens)
        total = len(chunk_texts)
        if not total:
            continue

        for index, chunk_text in enumerate(chunk_texts, start=1):
            section_label = section_title if section_title else "document"
            heading = f"## {section_label}" if section_label != "document" else "## Document"
            markdown_chunk = f"{heading}\n\n{chunk_text}".strip()
            chunks.append(
                Chunk(
                    id=f"{slugify(section_label)}-{index:03d}",
                    paper_id=paper_id,
                    section=section_label,
                    chunk_index=index,
                    total_chunks_in_section=total,
                    token_estimate=estimate_tokens(chunk_text),
                    text=chunk_text,
                    markdown=markdown_chunk,
                )
            )

    return chunks


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [json.dumps(row, ensure_ascii=True) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def build_pdf_bundle(pdf_path: str | Path, output_dir: str | Path, target_tokens: int = 400) -> dict[str, Any]:
    if pymupdf is None:
        raise RuntimeError(
            "PyMuPDF is required for PDF extraction. Install dependencies from requirements-pdf-tools.txt."
        )

    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paper_id = slugify(pdf_path.stem)

    doc = pymupdf.open(str(pdf_path))
    try:
        markdown_text = extract_markdown(pdf_path, doc)
        page_sections = detect_page_sections(doc, markdown_text)
        captions = extract_captions(doc, page_sections)
        tables = extract_tables(doc, output_dir, captions, page_sections)
        figures = extract_figures(doc, output_dir, captions, page_sections)
        chunks = chunk_sections(markdown_text, paper_id, target_tokens)
    finally:
        doc.close()

    markdown_dir = output_dir / "markdown"
    chunks_dir = output_dir / "chunks"
    metadata_dir = output_dir / "metadata"
    captions_dir = output_dir / "captions"
    markdown_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    captions_dir.mkdir(parents=True, exist_ok=True)

    paper_markdown_path = markdown_dir / f"{paper_id}.md"
    captions_markdown_path = captions_dir / "captions.md"
    chunk_jsonl_path = chunks_dir / "chunks.jsonl"

    paper_markdown_path.write_text(markdown_text + ("\n" if not markdown_text.endswith("\n") else ""), encoding="utf-8")
    captions_markdown_path.write_text(captions_to_markdown(captions), encoding="utf-8")
    write_json(captions_dir / "captions.json", [asdict(caption) for caption in captions])
    write_json(metadata_dir / "tables.json", [asdict(table) for table in tables])
    write_json(metadata_dir / "figures.json", [asdict(figure) for figure in figures])
    write_jsonl(chunk_jsonl_path, [asdict(chunk) for chunk in chunks])

    manifest = {
        "paper_id": paper_id,
        "source_pdf": str(pdf_path),
        "paper_markdown": str(paper_markdown_path),
        "captions_markdown": str(captions_markdown_path),
        "captions_json": str(captions_dir / "captions.json"),
        "tables_json": str(metadata_dir / "tables.json"),
        "figures_json": str(metadata_dir / "figures.json"),
        "chunks_jsonl": str(chunk_jsonl_path),
        "table_count": len(tables),
        "figure_count": len(figures),
        "caption_count": len(captions),
        "chunk_count": len(chunks),
        "sections": sorted({chunk.section for chunk in chunks}),
    }
    write_json(output_dir / "manifest.json", manifest)
    return manifest


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract structured assets and chunks from a PDF.")
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Directory for generated markdown, figures, tables, captions, and chunks",
        required=True,
    )
    parser.add_argument(
        "--target-tokens",
        type=int,
        default=400,
        help="Approximate token target for equal-sized chunks within each section",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    manifest = build_pdf_bundle(args.pdf, args.output_dir, target_tokens=args.target_tokens)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
