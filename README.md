# EpiconUI

Browser-based workspace for uploading papers, chunking them into structured assets, indexing them into Postgres/pgvector, and connecting those papers to LLM and R-based analysis workflows.

This project is designed to work well alongside the local [phonto](https://github.com/epiconnector/phonto) package for NHANES-side R access and analysis.

## Main Files

- `index.html`, `styles.css`, `app.js`: browser UI
- `server.py`: local web server and API endpoints
- `pdf_tools.py`: PDF to markdown/captions/tables/figures/chunks
- `project_store.py`: `~/.EpiMind` project and paper layout
- `rag_store.py`: Postgres schema creation, indexing, and retrieval
- `rag_config.py`: DB and embedding runtime config
- `embedding_client.py`: OpenAI-compatible embeddings client
- `init_rag_db.py`, `index_rag.py`, `search_rag.py`: RAG CLI tools

## Install

```bash
python3 -m pip install -r requirements-pdf-tools.txt
python3 -m pip install -r requirements-rag.txt
```

## Environment Variables

These are the important variables for this project.

### Postgres

If you are using the existing `EpiMind` database defaults, these are the values:

```bash
export EPIMIND_PGHOST=127.0.0.1
export EPIMIND_PGPORT=5432
export EPIMIND_PGUSER=sa
export EPIMIND_PGPASSWORD=NHAN35
export EPIMIND_PGDATABASE=NhanesLandingZone
export EPIMIND_PGSCHEMA=epimind
```

Notes:

- `EPIMIND_PGDATABASE` should usually stay `NhanesLandingZone`
- `EPIMIND_PGSCHEMA` should stay `epimind` so the paper/RAG tables remain separate from the NHANES tables

### Embeddings

```bash
export OPENAI_API_KEY="your-key"
export OPENAI_EMBEDDING_MODEL=text-embedding-3-small
export OPENAI_EMBEDDING_DIMENSIONS=1536
```

Optional overrides:

```bash
export OPENAI_EMBEDDING_API_KEY="your-key"
export OPENAI_EMBEDDING_BASE_URL="https://api.openai.com/v1"
export OPENAI_EMBEDDING_BATCH_SIZE=32
export OPENAI_EMBEDDING_TIMEOUT=180
```

### Chat / LLM UI

The browser UI can also use:

```bash
export OPENAI_API_KEY="your-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4o-mini"
```

### Optional Upload Auto-Indexing

If you want paper uploads to index into Postgres immediately after ingestion:

```bash
export EPIMIND_AUTO_INDEX_RAG=1
```

## Start The UI

```bash
cd /Users/robert/Projects/Epiconnector/EpiconUI
python3 server.py
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765).

## Initialize The Database

This creates the `epimind` schema and the project/paper/chunk/embedding tables inside `NhanesLandingZone`.

```bash
python3 init_rag_db.py
```

## Index A Paper

From the UI, select a paper and use `Embed Paper`.

From the command line:

```bash
python3 index_rag.py "My Project" "cobaltpaper"
```

## Search The Vector Store

```bash
python3 search_rag.py "What are the main exposure outcomes?" --project "My Project" --paper "cobaltpaper"
```

## Project Storage

Projects are stored under `~/.EpiMind/Projects/<project-slug>`.
Each paper lives under `~/.EpiMind/Projects/<project-slug>/papers/<paper-slug>`.

When a paper is indexed into Postgres, `EpiconUI` also writes:

- `~/.EpiMind/config/rag.json`
- `metadata/vector_index.json`
- `paper.json["rag"]`
- `project.json["rag"]`

## Additional Documentation

- [Local Filesystem Layout](/Users/robert/Projects/Epiconnector/EpiconUI/documentation/local-filesystem.md)
- [NhanesLandingZone / epimind Schema](/Users/robert/Projects/Epiconnector/EpiconUI/documentation/nhaneslandingzone-schema.md)
- [Database Checks And SQL](/Users/robert/Projects/Epiconnector/EpiconUI/documentation/database-checks.md)
- [R And dplyr Examples](/Users/robert/Projects/Epiconnector/EpiconUI/documentation/r-dplyr-access.md)
- [phonto And DB Access](/Users/robert/Projects/Epiconnector/EpiconUI/documentation/phonto-db-access.md)
