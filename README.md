# EpiconUI

Browser-based workspace for uploading papers, chunking them into structured assets, indexing them into Postgres/pgvector, and connecting those papers to LLM and R-based analysis workflows.

This project is designed to work well alongside the local [phonto](https://github.com/epiconnector/phonto) package for NHANES-side R access and analysis.

It now also includes a local NHANES extraction workflow that:

- retrieves relevant chunk text from the selected paper without sending content off-machine
- extracts NHANES cycle, table, variable, and component mentions
- validates those mentions against the local `NhanesLandingZone` metadata tables
- writes strict Markdown and JSON output documents into each paper's `outputs/` directory

## Main Files

- `index.html`, `styles.css`, `app.js`: browser UI
- `server.py`: local web server and API endpoints
- `pdf_tools.py`: PDF to markdown/captions/tables/figures/chunks
- `project_store.py`: `~/.EpiMind` project and paper layout
- `rag_store.py`: Postgres schema creation, indexing, and retrieval
- `rag_config.py`: DB and embedding runtime config
- `embedding_client.py`: OpenAI-compatible embeddings client
- `nhanes_metadata_index.py`: vector-backed NHANES metadata index over `Metadata.QuestionnaireVariables`
- `local_retrieval.py`: local chunk retrieval without embedding calls
- `legacy_nhanes_agent.py`: current local NHANES extraction, validation, orchestration, and output writing used by the browser UI
- `nhanes_agent/`: new FastAPI package scaffold for ingestion, retrieval, validation, and structured query answers
- `init_rag_db.py`, `index_rag.py`, `search_rag.py`: RAG CLI tools

## Install

```bash
python3 -m pip install -r requirements-pdf-tools.txt
python3 -m pip install -r requirements-rag.txt
python3 -m pip install -r requirements-nhanes-agent.txt
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

The local NHANES extraction workflow uses these same Postgres settings to validate extracted variables and table names against `Metadata.QuestionnaireVariables`.

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

## Build The NHANES Metadata Index

This builds a separate pgvector-backed index over `Metadata.QuestionnaireVariables` so concept queries such as `cobalt`, `glycohemoglobin`, or `age in years at screening` can be matched to candidate NHANES variables before final validation.

```bash
python3 index_nhanes_metadata.py
```

Recommended query flow for variable questions:

1. infer likely NHANES cycles from the paper evidence
2. extract raw variable concepts from the paper with the LLM
3. search the metadata index with those concepts, filtered by cycle/component when available
4. let the LLM choose among DB-backed candidates
5. validate the selected variable codes and tables against `Metadata.QuestionnaireVariables`

## Search The Vector Store

```bash
python3 search_rag.py "What are the main exposure outcomes?" --project "My Project" --paper "cobaltpaper"
```

## Run Local NHANES Extraction From The UI

1. Open a project
2. Select a paper
3. Type a NHANES-oriented prompt in the middle console
4. Press `Enter`

The server will run a local workflow and create:

- a Markdown report in `outputs/`
- a JSON sidecar in `outputs/`
- a new output tile in the right panel

## Project Storage

Projects are stored under `~/.EpiMind/Projects/<project-slug>`.
Each paper lives under `~/.EpiMind/Projects/<project-slug>/papers/<paper-slug>`.

Each paper may also contain:

- `outputs/` for generated Markdown and JSON documents

When a paper is indexed into Postgres, `EpiconUI` also writes:

- `~/.EpiMind/config/rag.json`
- `metadata/vector_index.json`
- `paper.json["rag"]`
- `project.json["rag"]`

## Additional Documentation

- [Local Filesystem Layout](/Users/robert/Projects/Epiconnector/EpiconUI/documentation/local-filesystem.md)
- [Architecture Overview](/Users/robert/Projects/Epiconnector/EpiconUI/documentation/architecture-overview.md)
- [Runtime Flows](/Users/robert/Projects/Epiconnector/EpiconUI/documentation/runtime-flows.md)
- [Module Map](/Users/robert/Projects/Epiconnector/EpiconUI/documentation/module-map.md)
- [NhanesLandingZone / epimind Schema](/Users/robert/Projects/Epiconnector/EpiconUI/documentation/nhaneslandingzone-schema.md)
- [Database Checks And SQL](/Users/robert/Projects/Epiconnector/EpiconUI/documentation/database-checks.md)
- [R And dplyr Examples](/Users/robert/Projects/Epiconnector/EpiconUI/documentation/r-dplyr-access.md)
- [phonto And DB Access](/Users/robert/Projects/Epiconnector/EpiconUI/documentation/phonto-db-access.md)
- [NHANES Agent Backend README](/Users/robert/Projects/Epiconnector/EpiconUI/nhanes_agent/README.md)
