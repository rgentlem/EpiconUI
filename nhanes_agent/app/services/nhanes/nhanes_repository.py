from __future__ import annotations

from dataclasses import dataclass

from legacy_nhanes_agent import SUFFIX_TO_CYCLE
from rag_config import load_database_config

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


@dataclass
class VariableCandidate:
    variable_name: str
    canonical_label: str
    table_name: str
    component: str
    cycle: str


class NhanesRepository:
    """Repository for NHANES metadata validation."""

    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir

    def connect(self):
        if psycopg is None:
            raise RuntimeError("psycopg is required for NHANES validation.")
        config = load_database_config(self.base_dir)
        return psycopg.connect(
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            dbname=config.dbname,
        )

    def validate_cycle(self, cycle: str) -> bool:
        """Validate a canonical cycle string against known mappings."""
        return cycle in SUFFIX_TO_CYCLE.values()

    def validate_component(self, component: str) -> bool:
        """Validate a component alias or table code."""
        canonical = component.strip()
        return bool(canonical)

    def validate_variable(self, candidate: str, cycle: str | None = None, component: str | None = None) -> list[VariableCandidate]:
        """Validate a NHANES variable candidate against the metadata database."""
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT "Variable", "TableName", COALESCE("VariableDescription", ''), COALESCE("Component", '')
                FROM "Metadata"."QuestionnaireVariables"
                WHERE "Variable" = %s
                ORDER BY "TableName";
                """,
                (candidate,),
            )
            rows = cur.fetchall()

        matches: list[VariableCandidate] = []
        for variable_name, table_name, description, component_name in rows:
            inferred_cycle = SUFFIX_TO_CYCLE.get(str(table_name).rsplit("_", 1)[-1], "")
            if cycle and inferred_cycle and inferred_cycle != cycle:
                continue
            if component and component_name and component.lower() not in component_name.lower() and component.lower() not in str(table_name).lower():
                continue
            matches.append(
                VariableCandidate(
                    variable_name=str(variable_name),
                    canonical_label=str(description),
                    table_name=str(table_name),
                    component=str(component_name or table_name),
                    cycle=inferred_cycle,
                )
            )
        return matches
