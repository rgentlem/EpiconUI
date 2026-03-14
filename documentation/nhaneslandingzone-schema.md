# NhanesLandingZone / epimind Schema

The recommended setup is:

- database: `NhanesLandingZone`
- schema for new paper/RAG tables: `epimind`

This keeps `EpiconUI` in the same Postgres database as the existing `EpiMind` / NHANES environment while isolating the paper-index tables in their own schema.

## Why Use The Same Database

- one Postgres instance to manage
- easy joins later between NHANES data and paper metadata
- simpler R and Python connection code
- schema-level separation avoids collisions

## Tables In `epimind`

### `epimind.epimind_registry`

One workspace-level record for the local `~/.EpiMind` installation.

Key columns:

- `registry_id`
- `workspace_key`
- `workspace_name`
- `home_dir`
- `config_path`

### `epimind.projects`

One row per project created in the UI.

Key columns:

- `project_id`
- `registry_id`
- `project_name`
- `project_slug`
- `project_dir`
- `metadata_path`

### `epimind.papers`

One row per paper within a project.

Key columns:

- `paper_id`
- `project_id`
- `paper_name`
- `paper_slug`
- `paper_dir`
- `source_pdf`
- `manifest_path`
- `metadata_path`

### `epimind.paper_assets`

Filesystem artifacts associated with a paper.

Examples:

- `paper_pdf`
- `chunks_jsonl`
- `paper_markdown`
- `captions_json`
- `tables_json`
- `figures_json`

Key columns:

- `asset_id`
- `paper_id`
- `asset_type`
- `relative_path`
- `absolute_path`
- `metadata`

### `epimind.paper_sections`

Ordered section records derived from the chunk stream.

Key columns:

- `section_id`
- `paper_id`
- `section_key`
- `section_name`
- `section_order`
- `chunk_count`

### `epimind.paper_chunks`

The text chunks used for retrieval and RAG.

Key columns:

- `chunk_id`
- `paper_id`
- `section_id`
- `chunk_key`
- `chunk_index`
- `total_chunks_in_section`
- `token_estimate`
- `text`
- `markdown`
- `source_json`

### `epimind.chunk_embeddings`

The actual pgvector rows.

Key columns:

- `chunk_id`
- `embedding_model`
- `embedding_dimensions`
- `embedding`
- `embedded_at`

## Logical Relationships

```text
epimind_registry
  -> projects
    -> papers
      -> paper_assets
      -> paper_sections
      -> paper_chunks
           -> chunk_embeddings
```

## Practical Meaning

- `projects` and `papers` let you filter by project name and paper name
- `paper_chunks` contains the actual text payloads
- `chunk_embeddings` contains the vectors used for semantic retrieval
- `paper_assets` and local `paper.json` / `project.json` connect DB rows back to the `~/.EpiMind` filesystem
