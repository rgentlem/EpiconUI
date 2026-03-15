from __future__ import annotations

from nhanes_agent.app.core.config import AgentSettings
from nhanes_agent.app.services.agent.answer_builder import build_answer
from nhanes_agent.app.services.agent.planner import build_retrieval_filters
from nhanes_agent.app.services.agent.tools import extract_nhanes_entities, search_chunks
from nhanes_agent.app.services.nhanes.nhanes_repository import NhanesRepository
from nhanes_agent.app.services.nhanes.validator import validate_components, validate_cycles, validate_variables


class QueryExecutor:
    """Deterministic orchestrator for NHANES-aware document queries."""

    def __init__(self, settings: AgentSettings):
        self.settings = settings
        self.repository = NhanesRepository(str(settings.base_dir) if settings.base_dir is not None else None)

    def run(self, *, query: str, project_name: str, paper_slug: str) -> dict:
        """Execute the full query workflow and build the final response."""
        filters = build_retrieval_filters(query)
        chunks = search_chunks(query, filters, project_name=project_name, paper_slug=paper_slug, settings=self.settings)
        combined_text = "\n\n".join([query] + [chunk.get("chunk_text", "") for chunk in chunks])
        extracted = extract_nhanes_entities(combined_text)

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

        chunk_ids = [chunk["chunk_id"] for chunk in chunks]
        for row in validated_cycles:
            row["evidence_chunk_ids"] = chunk_ids
        for row in validated_components:
            row["evidence_chunk_ids"] = chunk_ids
        for row in validated_variables:
            row["evidence_chunk_ids"] = chunk_ids

        notes: list[str] = []
        if not [row for row in validated_variables if row["validation_status"] == "validated"]:
            notes.append("No validated NHANES variables were found.")
        ambiguous = [row["raw_mention"] for row in validated_variables if row["validation_status"] != "validated"]
        if ambiguous:
            notes.append(f"Unresolved variable mentions: {', '.join(sorted(set(ambiguous)))}")
        pooled = [row["raw_mention"] for row in validated_cycles if len(row["canonical_cycles"]) > 1]
        if pooled:
            notes.append(f"Cycle pooling assumptions applied to: {', '.join(sorted(set(pooled)))}")

        summary = (
            f"Retrieved {len(chunks)} candidate chunks and validated "
            f"{sum(1 for item in validated_cycles if item['validation_status'] == 'validated')} cycle mentions, "
            f"{sum(1 for item in validated_components if item['validation_status'] == 'validated')} component mentions, and "
            f"{sum(1 for item in validated_variables if item['validation_status'] == 'validated')} variable mentions."
        )
        return build_answer(
            {
                "query": query,
                "chunks": chunks,
                "cycles": validated_cycles,
                "components": validated_components,
                "variables": validated_variables,
                "notes": notes,
                "summary": summary,
            }
        )
