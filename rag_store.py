from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError:  # pragma: no cover - optional dependency
    psycopg = None

from embedding_client import create_embeddings
from pdf_tools import slugify
from project_store import epimind_home, projects_root, read_json, write_json
from rag_config import DatabaseConfig, EmbeddingConfig, load_database_config, load_embedding_config, save_rag_runtime_config

TABLE_KEYS = (
    "epimind_registry",
    "projects",
    "papers",
    "paper_assets",
    "paper_sections",
    "paper_chunks",
    "chunk_embeddings",
)


@dataclass
class IndexSummary:
    project_name: str
    project_slug: str
    paper_name: str
    paper_slug: str
    project_id: int
    paper_id: int
    section_count: int
    chunk_count: int
    asset_count: int
    embedding_model: str
    embedding_dimensions: int
    indexed_at: str
    schema: str
    tables: dict[str, str]
    vector_index_path: str


def now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def require_psycopg() -> None:
    if psycopg is None:
        raise RuntimeError("psycopg is required for RAG indexing. Install requirements-rag.txt first.")


def fully_qualified_tables(schema: str) -> dict[str, str]:
    return {key: f"{schema}.{key}" for key in TABLE_KEYS}


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.10f}" for value in values) + "]"


def build_schema_statements(schema: str, dimensions: int) -> list[str]:
    return [
        "CREATE EXTENSION IF NOT EXISTS vector;",
        f"CREATE SCHEMA IF NOT EXISTS {schema};",
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.epimind_registry (
            registry_id bigserial PRIMARY KEY,
            workspace_key text NOT NULL UNIQUE,
            workspace_name text NOT NULL,
            home_dir text NOT NULL,
            config_path text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.projects (
            project_id bigserial PRIMARY KEY,
            registry_id bigint NOT NULL REFERENCES {schema}.epimind_registry(registry_id) ON DELETE CASCADE,
            project_name text NOT NULL,
            project_slug text NOT NULL UNIQUE,
            project_dir text NOT NULL,
            metadata_path text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.papers (
            paper_id bigserial PRIMARY KEY,
            project_id bigint NOT NULL REFERENCES {schema}.projects(project_id) ON DELETE CASCADE,
            paper_name text NOT NULL,
            paper_slug text NOT NULL,
            paper_title text,
            paper_dir text NOT NULL,
            source_pdf text NOT NULL,
            manifest_path text,
            metadata_path text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (project_id, paper_slug)
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.paper_assets (
            asset_id bigserial PRIMARY KEY,
            paper_id bigint NOT NULL REFERENCES {schema}.papers(paper_id) ON DELETE CASCADE,
            asset_type text NOT NULL,
            relative_path text NOT NULL,
            absolute_path text NOT NULL,
            metadata jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (paper_id, asset_type, relative_path)
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.paper_sections (
            section_id bigserial PRIMARY KEY,
            paper_id bigint NOT NULL REFERENCES {schema}.papers(paper_id) ON DELETE CASCADE,
            section_key text NOT NULL,
            section_name text NOT NULL,
            section_order integer NOT NULL,
            chunk_count integer NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (paper_id, section_key)
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.paper_chunks (
            chunk_id bigserial PRIMARY KEY,
            paper_id bigint NOT NULL REFERENCES {schema}.papers(paper_id) ON DELETE CASCADE,
            section_id bigint REFERENCES {schema}.paper_sections(section_id) ON DELETE SET NULL,
            chunk_key text NOT NULL,
            chunk_index integer NOT NULL,
            total_chunks_in_section integer NOT NULL,
            token_estimate integer NOT NULL,
            text text NOT NULL,
            markdown text NOT NULL,
            source_json jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (paper_id, chunk_key)
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.chunk_embeddings (
            chunk_id bigint PRIMARY KEY REFERENCES {schema}.paper_chunks(chunk_id) ON DELETE CASCADE,
            embedding_model text NOT NULL,
            embedding_dimensions integer NOT NULL,
            embedding vector({dimensions}) NOT NULL,
            embedded_at timestamptz NOT NULL DEFAULT now()
        );
        """,
        f"CREATE INDEX IF NOT EXISTS projects_project_slug_idx ON {schema}.projects (project_slug);",
        f"CREATE INDEX IF NOT EXISTS papers_project_id_slug_idx ON {schema}.papers (project_id, paper_slug);",
        f"CREATE INDEX IF NOT EXISTS paper_chunks_paper_id_idx ON {schema}.paper_chunks (paper_id);",
        f"CREATE INDEX IF NOT EXISTS paper_sections_paper_id_idx ON {schema}.paper_sections (paper_id);",
    ]


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


def ensure_schema(
    database: DatabaseConfig | None = None,
    embedding: EmbeddingConfig | None = None,
    *,
    base_dir: str | Path | None = None,
) -> dict[str, str]:
    database = database or load_database_config(base_dir)
    embedding = embedding or load_embedding_config(base_dir)
    tables = fully_qualified_tables(database.schema)

    with connect(database) as conn, conn.cursor() as cur:
        for statement in build_schema_statements(database.schema, embedding.dimensions):
            cur.execute(statement)
        conn.commit()
        try:
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS chunk_embeddings_cosine_idx ON {tables['chunk_embeddings']} USING hnsw (embedding vector_cosine_ops);"
            )
        except Exception:
            conn.rollback()
            with conn.cursor() as retry_cur:
                retry_cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                retry_cur.execute(
                    f"CREATE INDEX IF NOT EXISTS chunk_embeddings_ivfflat_idx ON {tables['chunk_embeddings']} USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
                )
        conn.commit()

    save_rag_runtime_config(base_dir=base_dir, database=database, embedding=embedding, tables=tables)
    return tables


def load_project_metadata(project_name_or_slug: str, base_dir: str | Path | None = None) -> tuple[dict[str, Any], Path]:
    root = projects_root(base_dir)
    lookup = project_name_or_slug.strip().lower()
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        metadata_path = child / "project.json"
        metadata = read_json(metadata_path, {})
        if not metadata:
            continue
        if metadata.get("project_slug", "").lower() == lookup or metadata.get("project_name", "").lower() == lookup:
            return metadata, metadata_path
    raise FileNotFoundError(f"Project not found in {root}: {project_name_or_slug}")


def load_paper_metadata(
    project_name_or_slug: str,
    paper_name_or_slug: str,
    base_dir: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    project_metadata, project_metadata_path = load_project_metadata(project_name_or_slug, base_dir=base_dir)
    lookup = paper_name_or_slug.strip().lower()
    for item in project_metadata.get("papers", []):
        if item.get("paper_slug", "").lower() == lookup or item.get("paper_name", "").lower() == lookup:
            paper_root = Path(str(item.get("paper_dir") or ""))
            paper_metadata_path = Path(str(item.get("metadata_path") or "")).expanduser()
            if not str(paper_metadata_path).strip() or paper_metadata_path == Path(".") or paper_metadata_path.is_dir():
                if paper_root:
                    paper_metadata_path = paper_root / "paper.json"
            paper_metadata = read_json(paper_metadata_path, {})
            if not paper_metadata:
                raise FileNotFoundError(f"Paper metadata missing: {paper_metadata_path}")
            return project_metadata, paper_metadata, project_metadata_path, paper_metadata_path
    raise FileNotFoundError(f"Paper not found in project {project_metadata.get('project_name')}: {paper_name_or_slug}")


def load_chunk_rows(chunks_jsonl_path: str | Path) -> list[dict[str, Any]]:
    path = Path(chunks_jsonl_path)
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        rows.append(json.loads(stripped))
    return rows


def build_section_rows(chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sections: list[dict[str, Any]] = []
    section_counts: dict[str, int] = {}
    chunk_rows: list[dict[str, Any]] = []
    current_key = ""
    current_name = ""

    for chunk in chunks:
        section_name = str(chunk.get("section") or "document").strip() or "document"
        if section_name != current_name:
            current_name = section_name
            section_counts[section_name] = section_counts.get(section_name, 0) + 1
            current_key = f"{slugify(section_name)}-{section_counts[section_name]:03d}"
            sections.append(
                {
                    "section_key": current_key,
                    "section_name": section_name,
                    "section_order": len(sections) + 1,
                    "chunk_count": 0,
                }
            )

        sections[-1]["chunk_count"] += 1
        chunk_rows.append(
            {
                **chunk,
                "section_key": current_key,
                "chunk_key": f"{current_key}:{int(chunk.get('chunk_index', 1)):03d}",
            }
        )

    return sections, chunk_rows


def relative_path(path: str | Path, root_dir: str | Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root_dir).resolve()))
    except ValueError:
        return str(path)


def collect_asset_rows(paper_metadata: dict[str, Any]) -> list[dict[str, Any]]:
    root_dir = Path(str(paper_metadata["paper_dir"]))
    manifest = paper_metadata.get("manifest", {})
    assets: list[dict[str, Any]] = []

    simple_paths = {
        "paper_pdf": paper_metadata.get("source_pdf"),
        "paper_dir": paper_metadata.get("paper_dir"),
        "chunks_dir": paper_metadata.get("chunks_dir"),
        "markdown_dir": paper_metadata.get("markdown_dir"),
        "captions_dir": paper_metadata.get("captions_dir"),
        "figures_dir": paper_metadata.get("figures_dir"),
        "tables_dir": paper_metadata.get("tables_dir"),
        "metadata_dir": paper_metadata.get("metadata_dir"),
        "paper_json": paper_metadata.get("metadata_path"),
        "manifest_json": root_dir / "manifest.json",
        "paper_markdown": manifest.get("paper_markdown"),
        "captions_markdown": manifest.get("captions_markdown"),
        "captions_json": manifest.get("captions_json"),
        "tables_json": manifest.get("tables_json"),
        "figures_json": manifest.get("figures_json"),
        "chunks_jsonl": manifest.get("chunks_jsonl"),
    }

    for asset_type, asset_path in simple_paths.items():
        if not asset_path:
            continue
        path = Path(str(asset_path))
        assets.append(
            {
                "asset_type": asset_type,
                "absolute_path": str(path),
                "relative_path": relative_path(path, root_dir),
                "metadata": {"kind": "directory" if path.is_dir() else "file"},
            }
        )

    return assets


def chunk_embedding_text(project_name: str, paper_name: str, chunk: dict[str, Any]) -> str:
    section = str(chunk.get("section") or "document")
    text = str(chunk.get("text") or "").strip()
    return f"Project: {project_name}\nPaper: {paper_name}\nSection: {section}\n\n{text}".strip()


def upsert_registry(cur, schema: str, home_dir: str, config_path: str) -> int:
    cur.execute(
        f"""
        INSERT INTO {schema}.epimind_registry (workspace_key, workspace_name, home_dir, config_path, updated_at)
        VALUES (%s, %s, %s, %s, now())
        ON CONFLICT (workspace_key) DO UPDATE
        SET workspace_name = EXCLUDED.workspace_name,
            home_dir = EXCLUDED.home_dir,
            config_path = EXCLUDED.config_path,
            updated_at = now()
        RETURNING registry_id;
        """,
        ("default", "EpiMind", home_dir, config_path),
    )
    return int(cur.fetchone()[0])


def upsert_project(cur, schema: str, registry_id: int, project_metadata: dict[str, Any], project_metadata_path: Path) -> int:
    cur.execute(
        f"""
        INSERT INTO {schema}.projects (registry_id, project_name, project_slug, project_dir, metadata_path, updated_at)
        VALUES (%s, %s, %s, %s, %s, now())
        ON CONFLICT (project_slug) DO UPDATE
        SET project_name = EXCLUDED.project_name,
            project_dir = EXCLUDED.project_dir,
            metadata_path = EXCLUDED.metadata_path,
            updated_at = now()
        RETURNING project_id;
        """,
        (
            registry_id,
            project_metadata["project_name"],
            project_metadata["project_slug"],
            str(project_metadata_path.parent),
            str(project_metadata_path),
        ),
    )
    return int(cur.fetchone()[0])


def upsert_paper(cur, schema: str, project_id: int, paper_metadata: dict[str, Any], paper_metadata_path: Path) -> int:
    paper_dir = str(paper_metadata["paper_dir"])
    manifest_path = str(Path(paper_dir) / "manifest.json")
    cur.execute(
        f"""
        INSERT INTO {schema}.papers (
            project_id,
            paper_name,
            paper_slug,
            paper_dir,
            source_pdf,
            manifest_path,
            metadata_path,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (project_id, paper_slug) DO UPDATE
        SET paper_name = EXCLUDED.paper_name,
            paper_dir = EXCLUDED.paper_dir,
            source_pdf = EXCLUDED.source_pdf,
            manifest_path = EXCLUDED.manifest_path,
            metadata_path = EXCLUDED.metadata_path,
            updated_at = now()
        RETURNING paper_id;
        """,
        (
            project_id,
            paper_metadata["paper_name"],
            paper_metadata["paper_slug"],
            paper_dir,
            paper_metadata["source_pdf"],
            manifest_path,
            str(paper_metadata_path),
        ),
    )
    return int(cur.fetchone()[0])


def replace_paper_rows(
    cur,
    schema: str,
    paper_id: int,
    chunks: list[dict[str, Any]],
    embedding_vectors: list[list[float]],
    assets: list[dict[str, Any]],
) -> tuple[int, int, int]:
    cur.execute(f"DELETE FROM {schema}.paper_assets WHERE paper_id = %s;", (paper_id,))
    cur.execute(f"DELETE FROM {schema}.paper_chunks WHERE paper_id = %s;", (paper_id,))
    cur.execute(f"DELETE FROM {schema}.paper_sections WHERE paper_id = %s;", (paper_id,))

    for asset in assets:
        cur.execute(
            f"""
            INSERT INTO {schema}.paper_assets (paper_id, asset_type, relative_path, absolute_path, metadata)
            VALUES (%s, %s, %s, %s, %s::jsonb);
            """,
            (
                paper_id,
                asset["asset_type"],
                asset["relative_path"],
                asset["absolute_path"],
                json.dumps(asset["metadata"]),
            ),
        )

    section_rows, chunk_rows = build_section_rows(chunks)
    section_ids: dict[str, int] = {}

    for section in section_rows:
        cur.execute(
            f"""
            INSERT INTO {schema}.paper_sections (paper_id, section_key, section_name, section_order, chunk_count)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING section_id;
            """,
            (
                paper_id,
                section["section_key"],
                section["section_name"],
                section["section_order"],
                section["chunk_count"],
            ),
        )
        section_ids[section["section_key"]] = int(cur.fetchone()[0])

    chunk_ids: list[int] = []
    for chunk in chunk_rows:
        section_id = section_ids[chunk["section_key"]]
        cur.execute(
            f"""
            INSERT INTO {schema}.paper_chunks (
                paper_id,
                section_id,
                chunk_key,
                chunk_index,
                total_chunks_in_section,
                token_estimate,
                text,
                markdown,
                source_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING chunk_id;
            """,
            (
                paper_id,
                section_id,
                chunk["chunk_key"],
                int(chunk.get("chunk_index", 1)),
                int(chunk.get("total_chunks_in_section", 1)),
                int(chunk.get("token_estimate", 0)),
                str(chunk.get("text", "")),
                str(chunk.get("markdown", "")),
                json.dumps(chunk),
            ),
        )
        chunk_ids.append(int(cur.fetchone()[0]))

    if len(chunk_ids) != len(embedding_vectors):
        raise RuntimeError("Chunk/embedding count mismatch during index insert.")

    return len(assets), len(section_rows), len(chunk_rows)


def write_index_metadata(
    project_metadata: dict[str, Any],
    paper_metadata: dict[str, Any],
    project_metadata_path: Path,
    paper_metadata_path: Path,
    summary: IndexSummary,
) -> None:
    vector_index_path = Path(summary.vector_index_path)
    vector_payload = {
        "project_name": summary.project_name,
        "project_slug": summary.project_slug,
        "paper_name": summary.paper_name,
        "paper_slug": summary.paper_slug,
        "project_id": summary.project_id,
        "paper_id": summary.paper_id,
        "section_count": summary.section_count,
        "chunk_count": summary.chunk_count,
        "asset_count": summary.asset_count,
        "embedding_model": summary.embedding_model,
        "embedding_dimensions": summary.embedding_dimensions,
        "indexed_at": summary.indexed_at,
        "schema": summary.schema,
        "tables": summary.tables,
    }
    write_json(vector_index_path, vector_payload)

    paper_metadata["rag"] = {
        **vector_payload,
        "vector_index_path": str(vector_index_path),
    }
    write_json(paper_metadata_path, paper_metadata)

    project_metadata.setdefault("rag", {})
    project_metadata["rag"].update(
        {
            "schema": summary.schema,
            "tables": summary.tables,
            "last_indexed_at": summary.indexed_at,
        }
    )
    for item in project_metadata.get("papers", []):
        if item.get("paper_slug") == summary.paper_slug:
            item["rag"] = {
                "project_id": summary.project_id,
                "paper_id": summary.paper_id,
                "indexed_at": summary.indexed_at,
                "chunk_count": summary.chunk_count,
                "section_count": summary.section_count,
                "vector_index_path": str(vector_index_path),
            }
    project_metadata["rag"]["indexed_papers"] = sum(1 for item in project_metadata.get("papers", []) if item.get("rag"))
    write_json(project_metadata_path, project_metadata)


def index_project_paper(
    project_name_or_slug: str,
    paper_name_or_slug: str,
    *,
    base_dir: str | Path | None = None,
    database: DatabaseConfig | None = None,
    embedding: EmbeddingConfig | None = None,
) -> dict[str, Any]:
    database = database or load_database_config(base_dir)
    embedding = embedding or load_embedding_config(base_dir)
    if not embedding.api_key:
        raise RuntimeError("No embedding API key is configured. Set OPENAI_API_KEY or OPENAI_EMBEDDING_API_KEY.")

    tables = ensure_schema(database, embedding, base_dir=base_dir)
    project_metadata, paper_metadata, project_metadata_path, paper_metadata_path = load_paper_metadata(
        project_name_or_slug,
        paper_name_or_slug,
        base_dir=base_dir,
    )
    manifest = paper_metadata.get("manifest", {})
    chunk_path = manifest.get("chunks_jsonl")
    if not chunk_path:
        raise RuntimeError(f"Paper manifest is missing chunks_jsonl: {paper_metadata_path}")

    chunks = load_chunk_rows(chunk_path)
    embed_inputs = [
        chunk_embedding_text(project_metadata["project_name"], paper_metadata["paper_name"], chunk)
        for chunk in chunks
    ]
    embeddings = create_embeddings(
        base_url=embedding.base_url,
        api_key=embedding.api_key,
        model=embedding.model,
        texts=embed_inputs,
        dimensions=embedding.dimensions,
        batch_size=embedding.batch_size,
        timeout=embedding.timeout,
    )

    vector_index_path = Path(str(paper_metadata["metadata_dir"])) / "vector_index.json"
    assets = collect_asset_rows(paper_metadata)

    with connect(database) as conn, conn.cursor() as cur:
        registry_id = upsert_registry(
            cur,
            database.schema,
            str(epimind_home(base_dir)),
            str(Path(epimind_home(base_dir)) / "config" / "rag.json"),
        )
        project_id = upsert_project(cur, database.schema, registry_id, project_metadata, project_metadata_path)
        paper_id = upsert_paper(cur, database.schema, project_id, paper_metadata, paper_metadata_path)
        asset_count, section_count, chunk_count = replace_paper_rows(
            cur,
            database.schema,
            paper_id,
            chunks,
            embeddings,
            assets,
        )

        cur.execute(
            f"SELECT chunk_id FROM {database.schema}.paper_chunks WHERE paper_id = %s ORDER BY chunk_id;",
            (paper_id,),
        )
        inserted_chunk_ids = [int(row[0]) for row in cur.fetchall()]
        if len(inserted_chunk_ids) != len(embeddings):
            raise RuntimeError("Inserted chunk row count did not match embedding count.")

        for chunk_id, vector in zip(inserted_chunk_ids, embeddings, strict=False):
            cur.execute(
                f"""
                INSERT INTO {database.schema}.chunk_embeddings (
                    chunk_id,
                    embedding_model,
                    embedding_dimensions,
                    embedding,
                    embedded_at
                )
                VALUES (%s, %s, %s, %s::vector, now())
                ON CONFLICT (chunk_id) DO UPDATE
                SET embedding_model = EXCLUDED.embedding_model,
                    embedding_dimensions = EXCLUDED.embedding_dimensions,
                    embedding = EXCLUDED.embedding,
                    embedded_at = now();
                """,
                (
                    chunk_id,
                    embedding.model,
                    embedding.dimensions,
                    vector_literal(vector),
                ),
            )
        conn.commit()

    indexed_at = now_iso()
    summary = IndexSummary(
        project_name=project_metadata["project_name"],
        project_slug=project_metadata["project_slug"],
        paper_name=paper_metadata["paper_name"],
        paper_slug=paper_metadata["paper_slug"],
        project_id=project_id,
        paper_id=paper_id,
        section_count=section_count,
        chunk_count=chunk_count,
        asset_count=asset_count,
        embedding_model=embedding.model,
        embedding_dimensions=embedding.dimensions,
        indexed_at=indexed_at,
        schema=database.schema,
        tables=tables,
        vector_index_path=str(vector_index_path),
    )
    write_index_metadata(project_metadata, paper_metadata, project_metadata_path, paper_metadata_path, summary)
    return {
        "project_name": summary.project_name,
        "project_slug": summary.project_slug,
        "paper_name": summary.paper_name,
        "paper_slug": summary.paper_slug,
        "project_id": summary.project_id,
        "paper_id": summary.paper_id,
        "section_count": summary.section_count,
        "chunk_count": summary.chunk_count,
        "asset_count": summary.asset_count,
        "embedding_model": summary.embedding_model,
        "embedding_dimensions": summary.embedding_dimensions,
        "indexed_at": summary.indexed_at,
        "schema": summary.schema,
        "tables": summary.tables,
        "vector_index_path": summary.vector_index_path,
    }


def search_chunks(
    query: str,
    *,
    project_name_or_slug: str | None = None,
    paper_name_or_slug: str | None = None,
    top_k: int = 6,
    base_dir: str | Path | None = None,
    database: DatabaseConfig | None = None,
    embedding: EmbeddingConfig | None = None,
) -> list[dict[str, Any]]:
    database = database or load_database_config(base_dir)
    embedding = embedding or load_embedding_config(base_dir)
    if not embedding.api_key:
        raise RuntimeError("No embedding API key is configured. Set OPENAI_API_KEY or OPENAI_EMBEDDING_API_KEY.")

    query_vector = create_embeddings(
        base_url=embedding.base_url,
        api_key=embedding.api_key,
        model=embedding.model,
        texts=[query],
        dimensions=embedding.dimensions,
        batch_size=1,
        timeout=embedding.timeout,
    )[0]

    project_filter = (project_name_or_slug or "").strip().lower()
    paper_filter = (paper_name_or_slug or "").strip().lower()
    sql = f"""
        SELECT
            pr.project_name,
            pr.project_slug,
            pa.paper_name,
            pa.paper_slug,
            ps.section_name,
            pc.chunk_index,
            pc.total_chunks_in_section,
            pc.text,
            pc.markdown,
            ce.embedding <=> %s::vector AS distance
        FROM {database.schema}.chunk_embeddings ce
        JOIN {database.schema}.paper_chunks pc ON pc.chunk_id = ce.chunk_id
        JOIN {database.schema}.papers pa ON pa.paper_id = pc.paper_id
        JOIN {database.schema}.projects pr ON pr.project_id = pa.project_id
        LEFT JOIN {database.schema}.paper_sections ps ON ps.section_id = pc.section_id
        WHERE (%s = '' OR lower(pr.project_slug) = %s OR lower(pr.project_name) = %s)
          AND (%s = '' OR lower(pa.paper_slug) = %s OR lower(pa.paper_name) = %s)
        ORDER BY ce.embedding <=> %s::vector
        LIMIT %s;
    """
    results: list[dict[str, Any]] = []

    with connect(database) as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                vector_literal(query_vector),
                project_filter,
                project_filter,
                project_filter,
                paper_filter,
                paper_filter,
                paper_filter,
                vector_literal(query_vector),
                int(top_k),
            ),
        )
        for row in cur.fetchall():
            results.append(
                {
                    "project_name": row[0],
                    "project_slug": row[1],
                    "paper_name": row[2],
                    "paper_slug": row[3],
                    "section": row[4] or "document",
                    "chunk_index": row[5],
                    "total_chunks_in_section": row[6],
                    "text": row[7],
                    "markdown": row[8],
                    "distance": float(row[9]),
                }
            )

    return results
