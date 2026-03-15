# NHANES Agent Backend

FastAPI backend scaffold for NHANES-aware document ingestion, retrieval, validation, and structured answer generation.

## Structure

- `app/api/`: FastAPI routes
- `app/core/`: config, logging, database wiring
- `app/models/sql/`: SQLAlchemy models
- `app/models/schemas/`: Pydantic request and response models
- `app/services/`: ingestion, embeddings, retrieval, NHANES validation, agent orchestration, output rendering
- `app/prompts/`: prompt templates
- `app/utils/`: deterministic helper functions
- `scripts/`: metadata loading and reindex helpers
- `tests/`: deterministic unit tests

## Install

```bash
cd /Users/robert/Projects/Epiconnector/EpiconUI
python3 -m pip install -r requirements-pdf-tools.txt
python3 -m pip install -r requirements-rag.txt
python3 -m pip install -r requirements-nhanes-agent.txt
```

## Environment

Use the same Postgres settings as the rest of `EpiconUI`:

```bash
export EPIMIND_PGHOST=127.0.0.1
export EPIMIND_PGPORT=5432
export EPIMIND_PGUSER=sa
export EPIMIND_PGPASSWORD=NHAN35
export EPIMIND_PGDATABASE=NhanesLandingZone
export EPIMIND_PGSCHEMA=epimind
export OPENAI_API_KEY="your-key"
```

## Run

Example with `uvicorn`:

```bash
cd /Users/robert/Projects/Epiconnector/EpiconUI
uvicorn nhanes_agent.main:app --reload
```

## Endpoints

- `POST /ingest/pdf`
- `POST /query`
- `GET /documents/{document_id}`
- `GET /chunks/{chunk_id}`
- `POST /admin/reindex`

## Notes

- The current implementation reuses the existing `EpiconUI` ingestion and vector-indexing code where practical.
- NHANES validation is database-backed and deterministic.
- Answer rendering follows the required strict Markdown section order.
- LLM-assisted extraction is not yet wired into the FastAPI package; the current path is rule-based plus DB validation.
