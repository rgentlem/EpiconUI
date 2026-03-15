from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from embedding_client import create_embeddings
from rag_config import DatabaseConfig, EmbeddingConfig, load_database_config, load_embedding_config

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


TABLE_NAME = "nhanes_variable_metadata"


@dataclass
class MetadataCandidate:
    variable_name: str
    table_name: str
    canonical_label: str
    component: str
    cycle: str
    searchable_text: str
    vector_score: float = 0.0
    lexical_score: float = 0.0
    total_score: float = 0.0


def require_psycopg() -> None:
    if psycopg is None:
        raise RuntimeError("psycopg is required for NHANES metadata indexing. Install requirements-rag.txt first.")


def connect(database: DatabaseConfig):
    require_psycopg()
    assert psycopg is not None
    return psycopg.connect(
        host=database.host,
        port=database.port,
        user=database.user,
        password=database.password,
        dbname=database.dbname,
    )


def infer_cycle(table_name: str) -> str:
    suffix = str(table_name).rsplit("_", 1)[-1] if "_" in str(table_name) else ""
    mapping = {
        "A": "1999-2000",
        "B": "2001-2002",
        "C": "2003-2004",
        "D": "2005-2006",
        "E": "2007-2008",
        "F": "2009-2010",
        "G": "2011-2012",
        "H": "2013-2014",
        "I": "2015-2016",
        "J": "2017-2018",
        "K": "2019-2020",
        "L": "2021-2022",
        "M": "2023-2024",
    }
    return mapping.get(suffix, "")


def build_searchable_text(row: dict[str, Any]) -> str:
    return " | ".join(
        [
            f"Variable={row['variable_name']}",
            f"Table={row['table_name']}",
            f"Label={row['canonical_label']}",
            f"Component={row['component']}",
            f"Cycle={row['cycle']}",
        ]
    )


def ensure_metadata_index(
    database: DatabaseConfig | None = None,
    embedding: EmbeddingConfig | None = None,
    *,
    base_dir: str | None = None,
) -> None:
    database = database or load_database_config(base_dir)
    embedding = embedding or load_embedding_config(base_dir)
    table = f"{database.schema}.{TABLE_NAME}"
    with connect(database) as conn, conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {database.schema};")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
                metadata_id bigserial PRIMARY KEY,
                variable_name text NOT NULL,
                table_name text NOT NULL,
                canonical_label text NOT NULL,
                component text NOT NULL,
                cycle text NOT NULL,
                searchable_text text NOT NULL,
                embedding_model text NOT NULL,
                embedding_dimensions integer NOT NULL,
                embedding vector({embedding.dimensions}) NOT NULL,
                updated_at timestamptz NOT NULL DEFAULT now(),
                UNIQUE (variable_name, table_name)
            );
            """
        )
        cur.execute(f"CREATE INDEX IF NOT EXISTS {TABLE_NAME}_cycle_idx ON {table} (cycle);")
        cur.execute(f"CREATE INDEX IF NOT EXISTS {TABLE_NAME}_component_idx ON {table} (component);")
        try:
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS {TABLE_NAME}_embedding_idx ON {table} USING hnsw (embedding vector_cosine_ops);"
            )
        except Exception:
            conn.rollback()
            with conn.cursor() as retry_cur:
                retry_cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                retry_cur.execute(
                    f"CREATE INDEX IF NOT EXISTS {TABLE_NAME}_embedding_ivfflat_idx ON {table} USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
                )
        conn.commit()


def fetch_questionnaire_variable_rows(cur) -> list[dict[str, str]]:
    cur.execute('SELECT * FROM "Metadata"."QuestionnaireVariables" LIMIT 0;')
    columns = {desc.name for desc in cur.description or []}
    description_expr = '"VariableDescription"' if "VariableDescription" in columns else '"Variable Label"' if "Variable Label" in columns else "''"
    component_expr = '"Component"' if "Component" in columns else '"DataGroup"' if "DataGroup" in columns else "''"
    cur.execute(
        f"""
        SELECT DISTINCT
            "Variable" AS variable_name,
            "TableName" AS table_name,
            COALESCE({description_expr}, '') AS canonical_label,
            COALESCE({component_expr}, '') AS component
        FROM "Metadata"."QuestionnaireVariables"
        WHERE COALESCE("Variable", '') <> ''
          AND COALESCE("TableName", '') <> ''
        ORDER BY "Variable", "TableName";
        """
    )
    rows = []
    for variable_name, table_name, canonical_label, component in cur.fetchall():
        row = {
            "variable_name": str(variable_name),
            "table_name": str(table_name),
            "canonical_label": str(canonical_label or ""),
            "component": str(component or ""),
            "cycle": infer_cycle(str(table_name)),
        }
        row["searchable_text"] = build_searchable_text(row)
        rows.append(row)
    return rows


def fetch_existing_metadata_rows(cur, table: str) -> dict[tuple[str, str], dict[str, str]]:
    cur.execute(
        f"""
        SELECT variable_name, table_name, canonical_label, component, cycle, searchable_text
        FROM {table};
        """
    )
    rows: dict[tuple[str, str], dict[str, str]] = {}
    for variable_name, table_name, canonical_label, component, cycle, searchable_text in cur.fetchall():
        rows[(str(variable_name), str(table_name))] = {
            "variable_name": str(variable_name),
            "table_name": str(table_name),
            "canonical_label": str(canonical_label or ""),
            "component": str(component or ""),
            "cycle": str(cycle or ""),
            "searchable_text": str(searchable_text or ""),
        }
    return rows


def plan_metadata_sync(
    source_rows: list[dict[str, str]],
    existing_rows: dict[tuple[str, str], dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[tuple[str, str]]]:
    unchanged: list[dict[str, str]] = []
    to_embed: list[dict[str, str]] = []
    source_keys = {(row["variable_name"], row["table_name"]) for row in source_rows}

    for row in source_rows:
        key = (row["variable_name"], row["table_name"])
        existing = existing_rows.get(key)
        if existing and existing.get("searchable_text") == row.get("searchable_text"):
            unchanged.append(row)
        else:
            to_embed.append(row)

    stale_keys = sorted(set(existing_rows) - source_keys)
    return unchanged, to_embed, stale_keys


def rebuild_metadata_index(*, base_dir: str | None = None) -> dict[str, Any]:
    database = load_database_config(base_dir)
    embedding = load_embedding_config(base_dir)
    ensure_metadata_index(database, embedding, base_dir=base_dir)
    table = f"{database.schema}.{TABLE_NAME}"

    print(f"[nhanes-metadata] ensuring index table {table}", flush=True)

    with connect(database) as conn, conn.cursor() as cur:
        rows = fetch_questionnaire_variable_rows(cur)
    with connect(database) as conn, conn.cursor() as cur:
        existing_rows = fetch_existing_metadata_rows(cur, table)
    print(f"[nhanes-metadata] loaded {len(rows)} questionnaire variable rows", flush=True)
    print(f"[nhanes-metadata] found {len(existing_rows)} existing indexed rows", flush=True)

    unchanged_rows, rows_to_embed, stale_keys = plan_metadata_sync(rows, existing_rows)
    print(
        f"[nhanes-metadata] sync plan: {len(unchanged_rows)} unchanged, {len(rows_to_embed)} to embed, {len(stale_keys)} stale",
        flush=True,
    )

    texts = [row["searchable_text"] for row in rows_to_embed]
    vectors: list[list[float]] = []
    total_batches = max(1, (len(texts) + embedding.batch_size - 1) // embedding.batch_size)
    for batch_index, start in enumerate(range(0, len(texts), embedding.batch_size), start=1):
        batch = texts[start : start + embedding.batch_size]
        print(
            f"[nhanes-metadata] embedding batch {batch_index}/{total_batches} ({len(batch)} rows)",
            flush=True,
        )
        batch_vectors = create_embeddings(
            base_url=embedding.base_url,
            api_key=embedding.api_key,
            model=embedding.model,
            texts=batch,
            dimensions=embedding.dimensions,
            batch_size=embedding.batch_size,
            timeout=embedding.timeout,
        )
        vectors.extend(batch_vectors)

    with connect(database) as conn, conn.cursor() as cur:
        if stale_keys:
            cur.execute(
                f"DELETE FROM {table} WHERE (variable_name, table_name) IN (SELECT * FROM UNNEST(%s::text[], %s::text[]));",
                (
                    [key[0] for key in stale_keys],
                    [key[1] for key in stale_keys],
                ),
            )
            conn.commit()
            print(f"[nhanes-metadata] deleted {len(stale_keys)} stale rows", flush=True)
        for row_index, (row, vector) in enumerate(zip(rows_to_embed, vectors, strict=False), start=1):
            cur.execute(
                f"""
                INSERT INTO {table} (
                    variable_name, table_name, canonical_label, component, cycle,
                    searchable_text, embedding_model, embedding_dimensions, embedding, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector, now())
                ON CONFLICT (variable_name, table_name)
                DO UPDATE SET
                    canonical_label = EXCLUDED.canonical_label,
                    component = EXCLUDED.component,
                    cycle = EXCLUDED.cycle,
                    searchable_text = EXCLUDED.searchable_text,
                    embedding_model = EXCLUDED.embedding_model,
                    embedding_dimensions = EXCLUDED.embedding_dimensions,
                    embedding = EXCLUDED.embedding,
                    updated_at = now();
                """,
                (
                    row["variable_name"],
                    row["table_name"],
                    row["canonical_label"],
                    row["component"],
                    row["cycle"],
                    row["searchable_text"],
                    embedding.model,
                    embedding.dimensions,
                    "[" + ",".join(f"{float(value):.10f}" for value in vector) + "]",
                ),
            )
            if row_index % 500 == 0:
                conn.commit()
                print(
                    f"[nhanes-metadata] upserted {row_index}/{len(rows_to_embed)} changed rows",
                    flush=True,
                )
        conn.commit()
    print(
        f"[nhanes-metadata] completed sync with {len(rows)} source rows and {len(rows_to_embed)} newly embedded rows",
        flush=True,
    )

    return {
        "ok": True,
        "row_count": len(rows),
        "unchanged_count": len(unchanged_rows),
        "embedded_count": len(rows_to_embed),
        "stale_deleted_count": len(stale_keys),
        "table": table,
        "embedding_model": embedding.model,
        "embedding_dimensions": embedding.dimensions,
    }


def _metadata_index_row_count(cur, table: str) -> int:
    cur.execute(f"SELECT COUNT(*) FROM {table};")
    return int(cur.fetchone()[0])


def search_metadata_candidates(
    *,
    query: str,
    cycles: list[str] | None = None,
    components: list[str] | None = None,
    top_k: int = 12,
    base_dir: str | None = None,
) -> list[MetadataCandidate]:
    database = load_database_config(base_dir)
    embedding = load_embedding_config(base_dir)
    table = f"{database.schema}.{TABLE_NAME}"

    with connect(database) as conn, conn.cursor() as cur:
        ensure_metadata_index(database, embedding, base_dir=base_dir)
        if _metadata_index_row_count(cur, table) == 0:
            raise RuntimeError(
                "NHANES metadata vector index is empty. Run rebuild_metadata_index() before asking variable queries."
            )

        query_vector = create_embeddings(
            base_url=embedding.base_url,
            api_key=embedding.api_key,
            model=embedding.model,
            texts=[query],
            dimensions=embedding.dimensions,
            batch_size=1,
            timeout=embedding.timeout,
        )[0]

        filters = []
        params: list[Any] = []
        if cycles:
            filters.append("cycle = ANY(%s)")
            params.append(cycles)
        if components:
            component_patterns = [f"%{item.lower()}%" for item in components if item.strip()]
            if component_patterns:
                filters.append("(LOWER(component) LIKE ANY(%s) OR LOWER(table_name) LIKE ANY(%s))")
                params.extend([component_patterns, component_patterns])
        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""

        vector_sql = f"""
            SELECT
                variable_name,
                table_name,
                canonical_label,
                component,
                cycle,
                searchable_text,
                1.0 - (embedding <=> %s::vector) AS vector_score
            FROM {table}
            {where_sql}
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """
        vector_params = ["[" + ",".join(f"{float(value):.10f}" for value in query_vector) + "]", *params, "[" + ",".join(f"{float(value):.10f}" for value in query_vector) + "]", top_k]
        cur.execute(vector_sql, vector_params)
        vector_rows = cur.fetchall()

        lexical_sql = f"""
            SELECT
                variable_name,
                table_name,
                canonical_label,
                component,
                cycle,
                searchable_text
            FROM {table}
            {where_sql if where_sql else 'WHERE TRUE'}
              AND (
                LOWER(variable_name) LIKE LOWER(%s)
                OR LOWER(table_name) LIKE LOWER(%s)
                OR LOWER(canonical_label) LIKE LOWER(%s)
                OR LOWER(component) LIKE LOWER(%s)
              )
            LIMIT %s;
        """
        pattern = f"%{query.strip()}%"
        cur.execute(lexical_sql, [*params, pattern, pattern, pattern, pattern, top_k])
        lexical_rows = cur.fetchall()

    merged: dict[tuple[str, str], MetadataCandidate] = {}
    for row in vector_rows:
        key = (str(row[0]), str(row[1]))
        merged[key] = MetadataCandidate(
            variable_name=str(row[0]),
            table_name=str(row[1]),
            canonical_label=str(row[2] or ""),
            component=str(row[3] or ""),
            cycle=str(row[4] or ""),
            searchable_text=str(row[5] or ""),
            vector_score=max(0.0, float(row[6] or 0.0)),
            lexical_score=0.0,
        )
    for row in lexical_rows:
        key = (str(row[0]), str(row[1]))
        candidate = merged.get(
            key,
            MetadataCandidate(
                variable_name=str(row[0]),
                table_name=str(row[1]),
                canonical_label=str(row[2] or ""),
                component=str(row[3] or ""),
                cycle=str(row[4] or ""),
                searchable_text=str(row[5] or ""),
            ),
        )
        candidate.lexical_score = max(candidate.lexical_score, 1.0)
        merged[key] = candidate

    query_upper = query.strip().upper()
    for candidate in merged.values():
        bonus = 0.0
        if candidate.variable_name == query_upper:
            bonus += 2.0
        if candidate.table_name == query_upper:
            bonus += 1.5
        if query.strip().lower() in candidate.canonical_label.lower():
            bonus += 1.0
        candidate.total_score = candidate.vector_score * 0.65 + candidate.lexical_score * 0.35 + bonus

    ranked = sorted(merged.values(), key=lambda row: (-row.total_score, row.variable_name, row.table_name))
    return ranked[:top_k]
