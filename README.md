# EpiconUI

Browser-based prototype for a four-panel research workspace.

## Files

- `index.html` contains the app structure.
- `styles.css` defines the three-column layout and panel styling.
- `app.js` adds lightweight prompt and context interactions.
- `pdf_tools.py` extracts PDF markdown, captions, tables, figures, and section-aware chunks.
- `process_pdf.py` is the CLI entrypoint for the PDF pipeline.
- `project_store.py` manages the `~/.EpiMind/Projects/<project>/papers/<paper>/...` storage layout.
- `ingest_project_pdf.py` copies a PDF into a project and runs the extraction pipeline there.
- `server.py` serves the browser UI and API endpoints for project creation and PDF upload.
- `config_store.py` stores LLM connection settings server-side under `~/.EpiMind/config`.
- `llm_client.py` calls an OpenAI-compatible `/chat/completions` endpoint.
- `embedding_client.py` calls an OpenAI-compatible `/embeddings` endpoint.
- `rag_config.py` resolves Postgres and embedding settings for the RAG index.
- `rag_store.py` creates the pgvector schema, indexes paper chunks, and runs filtered retrieval.
- `init_rag_db.py`, `index_rag.py`, and `search_rag.py` are CLI entrypoints for the RAG workflow.
- `docker-compose.pgvector.yml` starts a local pgvector-backed Postgres container.

## Run

Start the local server:

```bash
python3 server.py
```

Then open `http://127.0.0.1:8765` in a browser.

The top bar can either open an existing project discovered under `~/.EpiMind/Projects` or create a new one.

## PDF Tools

Install the PDF dependencies in `requirements-pdf-tools.txt`, then run:

```bash
python3 process_pdf.py /path/to/paper.pdf --output-dir ./output/paper
```

To store papers inside the project-scoped hidden directory structure:

```bash
python3 ingest_project_pdf.py "My Project" /path/to/paper.pdf
```

The browser UI uses the same ingest pipeline through `POST /api/upload`.

## RAG Database

Install the database dependency:

```bash
python3 -m pip install -r requirements-rag.txt
```

Start a local pgvector Postgres container:

```bash
export EPIMIND_PGPASSWORD="postgres"
docker compose -f docker-compose.pgvector.yml up -d
```

Environment variables used by the RAG pipeline:

- `EPIMIND_PGHOST` default `127.0.0.1`
- `EPIMIND_PGPORT` default `5432`
- `EPIMIND_PGUSER` default `postgres`
- `EPIMIND_PGPASSWORD` required for password-authenticated Postgres
- `EPIMIND_PGDATABASE` default `epimind`
- `EPIMIND_PGSCHEMA` default `epimind`
- `OPENAI_API_KEY` or `OPENAI_EMBEDDING_API_KEY` for embeddings
- `OPENAI_EMBEDDING_MODEL` default `text-embedding-3-small`
- `OPENAI_EMBEDDING_DIMENSIONS` default `1536`

Initialize the schema:

```bash
python3 init_rag_db.py
```

Index one ingested paper:

```bash
python3 index_rag.py "My Project" "cobaltpaper"
```

Search the vector store, optionally filtered by project and paper:

```bash
python3 search_rag.py "What are the main exposure outcomes?" --project "My Project" --paper "cobaltpaper"
```

If you want uploads to index automatically after ingestion, start the web server with:

```bash
export EPIMIND_AUTO_INDEX_RAG=1
python3 server.py
```

## LLM Connection

The middle panel can be configured with:

- API base URL
- model name
- API key
- optional system prompt

These settings are stored server-side in `~/.EpiMind/config/llm.json` with restrictive file permissions when possible, instead of storing secrets in browser local storage.

The pipeline writes:

- paper markdown
- captions as both markdown and JSON
- extracted tables as markdown plus a JSON manifest
- extracted figures as image files plus a JSON manifest
- section-preserving equal-size chunks as JSONL

## Project Layout

Each project lives under `~/.EpiMind/Projects/<project-slug>`.
Each paper lives under `~/.EpiMind/Projects/<project-slug>/papers/<paper-slug>`.

Inside each paper directory:

- `paper/<original-file>.pdf`
- `chunks/chunks.jsonl`
- `markdown/<paper-slug>.md`
- `captions/captions.json`
- `figures/`
- `tables/`
- `metadata/`
- `manifest.json`

When a paper is indexed into Postgres, the pipeline also writes:

- `~/.EpiMind/config/rag.json` with non-secret database and embedding runtime settings
- `metadata/vector_index.json` with the Postgres schema, table names, project ID, paper ID, chunk count, and embedding model
- `paper.json["rag"]` and `project.json["rag"]` summaries so later R or Python code can discover the DB records directly from the project folders

## Database Layout

The pgvector schema mirrors the on-disk project hierarchy:

- `epimind.epimind_registry`: root workspace record for the local `~/.EpiMind` installation
- `epimind.projects`: one row per project
- `epimind.papers`: one row per paper inside a project
- `epimind.paper_assets`: filesystem artifacts such as `paper/`, `chunks/chunks.jsonl`, `manifest.json`, and figure/table metadata
- `epimind.paper_sections`: ordered section records derived from the chunk stream
- `epimind.paper_chunks`: chunk text and markdown payloads
- `epimind.chunk_embeddings`: pgvector embeddings keyed one-to-one to `paper_chunks`
