from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pdf_tools import build_pdf_bundle, slugify


@dataclass
class ProjectPaths:
    project_name: str
    project_slug: str
    root_dir: Path
    papers_dir: Path
    metadata_path: Path


@dataclass
class PaperPaths:
    paper_name: str
    paper_slug: str
    root_dir: Path
    paper_dir: Path
    source_pdf_path: Path
    chunks_dir: Path
    markdown_dir: Path
    captions_dir: Path
    figures_dir: Path
    tables_dir: Path
    metadata_dir: Path
    metadata_path: Path


def epimind_home(base_dir: str | Path | None = None) -> Path:
    if base_dir is not None:
        return Path(base_dir).expanduser().resolve()
    return (Path.home() / ".EpiMind").resolve()


def projects_root(base_dir: str | Path | None = None) -> Path:
    root = epimind_home(base_dir) / "Projects"
    root.mkdir(parents=True, exist_ok=True)
    return root


def list_projects(base_dir: str | Path | None = None) -> list[dict[str, str]]:
    root = projects_root(base_dir)
    projects: list[dict[str, str]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        metadata = read_json(child / "project.json", {})
        projects.append(
            {
                "project_name": str(metadata.get("project_name") or child.name),
                "project_slug": str(metadata.get("project_slug") or child.name),
                "root_dir": str(child),
            }
        )
    return projects


def now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def ensure_project(project_name: str, base_dir: str | Path | None = None) -> ProjectPaths:
    name = project_name.strip()
    if not name:
        raise ValueError("Project name cannot be empty.")

    slug = slugify(name)
    root_dir = projects_root(base_dir) / slug
    papers_dir = root_dir / "papers"
    metadata_path = root_dir / "project.json"

    papers_dir.mkdir(parents=True, exist_ok=True)

    metadata = read_json(
        metadata_path,
        {
            "project_name": name,
            "project_slug": slug,
            "created_at": now_iso(),
            "papers": [],
        },
    )
    metadata["project_name"] = name
    metadata["project_slug"] = slug
    metadata.setdefault("created_at", now_iso())
    metadata.setdefault("papers", [])
    metadata["updated_at"] = now_iso()
    write_json(metadata_path, metadata)

    return ProjectPaths(
        project_name=name,
        project_slug=slug,
        root_dir=root_dir,
        papers_dir=papers_dir,
        metadata_path=metadata_path,
    )


def ensure_paper_paths(project: ProjectPaths, pdf_path: str | Path) -> PaperPaths:
    pdf_source = Path(pdf_path).expanduser().resolve()
    if not pdf_source.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_source}")

    paper_name = pdf_source.stem
    paper_slug = slugify(paper_name)
    root_dir = project.papers_dir / paper_slug

    paper_dir = root_dir / "paper"
    chunks_dir = root_dir / "chunks"
    markdown_dir = root_dir / "markdown"
    captions_dir = root_dir / "captions"
    figures_dir = root_dir / "figures"
    tables_dir = root_dir / "tables"
    metadata_dir = root_dir / "metadata"
    metadata_path = root_dir / "paper.json"
    source_pdf_path = paper_dir / pdf_source.name

    for directory in (
        paper_dir,
        chunks_dir,
        markdown_dir,
        captions_dir,
        figures_dir,
        tables_dir,
        metadata_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    return PaperPaths(
        paper_name=paper_name,
        paper_slug=paper_slug,
        root_dir=root_dir,
        paper_dir=paper_dir,
        source_pdf_path=source_pdf_path,
        chunks_dir=chunks_dir,
        markdown_dir=markdown_dir,
        captions_dir=captions_dir,
        figures_dir=figures_dir,
        tables_dir=tables_dir,
        metadata_dir=metadata_dir,
        metadata_path=metadata_path,
    )


def sync_project_index(project: ProjectPaths, paper_record: dict[str, Any]) -> None:
    metadata = read_json(project.metadata_path, {})
    papers = metadata.setdefault("papers", [])
    existing = next((item for item in papers if item.get("paper_slug") == paper_record["paper_slug"]), None)
    if existing:
        existing.update(paper_record)
    else:
        papers.append(paper_record)
    metadata["updated_at"] = now_iso()
    write_json(project.metadata_path, metadata)


def ingest_pdf_to_project(
    project_name: str,
    pdf_path: str | Path,
    *,
    base_dir: str | Path | None = None,
    target_tokens: int = 400,
) -> dict[str, Any]:
    project = ensure_project(project_name, base_dir=base_dir)
    paper_paths = ensure_paper_paths(project, pdf_path)

    pdf_source = Path(pdf_path).expanduser().resolve()
    shutil.copy2(pdf_source, paper_paths.source_pdf_path)

    extraction_manifest = build_pdf_bundle(
        paper_paths.source_pdf_path,
        paper_paths.root_dir,
        target_tokens=target_tokens,
    )

    paper_record = {
        "paper_name": paper_paths.paper_name,
        "paper_slug": paper_paths.paper_slug,
        "paper_dir": str(paper_paths.root_dir),
        "source_pdf": str(paper_paths.source_pdf_path),
        "chunks_dir": str(paper_paths.chunks_dir),
        "markdown_dir": str(paper_paths.markdown_dir),
        "captions_dir": str(paper_paths.captions_dir),
        "figures_dir": str(paper_paths.figures_dir),
        "tables_dir": str(paper_paths.tables_dir),
        "metadata_dir": str(paper_paths.metadata_dir),
        "ingested_at": now_iso(),
        "manifest": extraction_manifest,
    }
    write_json(paper_paths.metadata_path, paper_record)
    sync_project_index(project, paper_record)

    project_payload = {
        "project_name": project.project_name,
        "project_slug": project.project_slug,
        "root_dir": str(project.root_dir),
        "papers_dir": str(project.papers_dir),
        "metadata_path": str(project.metadata_path),
    }

    return {
        "project": project_payload,
        "paper": {
            "paper_name": paper_paths.paper_name,
            "paper_slug": paper_paths.paper_slug,
            "root_dir": str(paper_paths.root_dir),
            "paper_dir": str(paper_paths.paper_dir),
            "source_pdf_path": str(paper_paths.source_pdf_path),
            "chunks_dir": str(paper_paths.chunks_dir),
            "markdown_dir": str(paper_paths.markdown_dir),
            "captions_dir": str(paper_paths.captions_dir),
            "figures_dir": str(paper_paths.figures_dir),
            "tables_dir": str(paper_paths.tables_dir),
            "metadata_dir": str(paper_paths.metadata_dir),
            "metadata_path": str(paper_paths.metadata_path),
        },
        "manifest": extraction_manifest,
    }


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest a PDF into a project under ~/.EpiMind/Projects.")
    parser.add_argument("project_name", help="Project name")
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument(
        "--base-dir",
        help="Override the ~/.EpiMind root for testing or custom deployments",
    )
    parser.add_argument(
        "--target-tokens",
        type=int,
        default=400,
        help="Approximate token target for equal-sized section chunks",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    result = ingest_pdf_to_project(
        args.project_name,
        args.pdf,
        base_dir=args.base_dir,
        target_tokens=args.target_tokens,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
