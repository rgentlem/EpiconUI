from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from nhanes_agent.app.core.config import AgentSettings
from nhanes_agent.app.services.agent.tools import extract_nhanes_entities
from nhanes_agent.app.services.nhanes.nhanes_repository import NhanesRepository
from nhanes_agent.app.services.nhanes.validator import validate_components, validate_cycles, validate_variables
from project_store import ingest_pdf_to_project
from rag_store import index_project_paper


class IngestService:
    """High-level ingestion workflow for PDFs and NHANES extraction."""

    def __init__(self, settings: AgentSettings):
        self.settings = settings
        self.repository = NhanesRepository(str(settings.base_dir) if settings.base_dir is not None else None)

    def ingest_pdf(self, *, project_name: str, filename: str, content: bytes, auto_index: bool = True) -> dict[str, Any]:
        """Run PDF ingestion, optional vector indexing, and NHANES extraction."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_pdf = Path(tmp_dir) / filename
            temp_pdf.write_bytes(content)
            ingest_result = ingest_pdf_to_project(
                project_name,
                temp_pdf,
                base_dir=self.settings.base_dir,
                target_tokens=self.settings.chunk_size,
            )

        paper = ingest_result["paper"]
        if auto_index:
            try:
                index_project_paper(project_name, paper["paper_slug"], base_dir=self.settings.base_dir)
            except Exception:
                pass

        manifest = ingest_result["manifest"]
        chunks_path = Path(str(manifest.get("chunks_jsonl") or ""))
        chunk_lines = chunks_path.read_text(encoding="utf-8").splitlines() if chunks_path.exists() else []
        chunk_text = "\n".join(chunk_lines)
        extracted = extract_nhanes_entities(chunk_text)
        validated_cycles = validate_cycles(extracted["cycles"], self.repository)
        validated_components = validate_components(extracted["components"], self.repository)
        preferred_cycle = next((item["canonical_cycles"][0] for item in validated_cycles if item["canonical_cycles"]), None)
        preferred_component = next((item["canonical_component"] for item in validated_components if item["validation_status"] == "validated"), None)
        validated_variables = validate_variables(
            extracted["variables"],
            preferred_cycle,
            preferred_component,
            self.repository,
            threshold=self.settings.variable_confidence_threshold,
        )

        return {
            "document_id": f"{project_name}:{paper['paper_slug']}",
            "number_of_chunks": len(chunk_lines),
            "number_of_validated_cycles": sum(1 for item in validated_cycles if item["validation_status"] == "validated"),
            "number_of_validated_components": sum(1 for item in validated_components if item["validation_status"] == "validated"),
            "number_of_validated_variables": sum(1 for item in validated_variables if item["validation_status"] == "validated"),
            "paper": paper,
        }
