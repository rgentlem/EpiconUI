# Runtime Flows

This document shows the main execution paths that are active today.

## 1. Paper Ingestion Flow

```mermaid
sequenceDiagram
    participant UI as Browser UI
    participant S as server.py
    participant P as project_store.py
    participant PDF as pdf_tools.py
    participant FS as ~/.EpiMind

    UI->>S: POST /api/upload
    S->>P: ingest_pdf_to_project(project, pdf)
    P->>PDF: extract markdown / captions / tables / figures / chunks
    PDF->>FS: write paper assets
    P->>FS: write paper.json / project.json
    S-->>UI: updated project and paper payload
```

Active files:

- [server.py](/Users/robert/Projects/Epiconnector/EpiconUI/server.py)
- [project_store.py](/Users/robert/Projects/Epiconnector/EpiconUI/project_store.py)
- [pdf_tools.py](/Users/robert/Projects/Epiconnector/EpiconUI/pdf_tools.py)

## 2. Paper Vector Indexing Flow

```mermaid
sequenceDiagram
    participant UI as Browser UI
    participant S as server.py
    participant R as rag_store.py
    participant E as embedding_client.py
    participant DB as Postgres / epimind.*

    UI->>S: POST /api/paper-actions (index_rag)
    S->>R: index_project_paper(project, paper)
    R->>R: load paper chunks and metadata
    R->>E: create embeddings
    E-->>R: vectors
    R->>DB: upsert project/paper/chunk rows
    R->>DB: upsert chunk embeddings
    S-->>UI: indexing result + refreshed paper state
```

Active files:

- [server.py](/Users/robert/Projects/Epiconnector/EpiconUI/server.py)
- [rag_store.py](/Users/robert/Projects/Epiconnector/EpiconUI/rag_store.py)
- [embedding_client.py](/Users/robert/Projects/Epiconnector/EpiconUI/embedding_client.py)

## 3. Generic Chat Flow

This is the non-agent chat path used for simple LLM interaction.

```mermaid
sequenceDiagram
    participant UI as Browser UI
    participant S as server.py
    participant C as config_store.py
    participant L as llm_client.py
    participant FS as ~/.EpiMind

    UI->>S: POST /api/chat
    S->>C: load_llm_config()
    S->>FS: load paper context if selected
    S->>L: create_chat_completion(messages)
    L-->>S: answer
    S-->>UI: answer text
```

Active files:

- [server.py](/Users/robert/Projects/Epiconnector/EpiconUI/server.py)
- [config_store.py](/Users/robert/Projects/Epiconnector/EpiconUI/config_store.py)
- [llm_client.py](/Users/robert/Projects/Epiconnector/EpiconUI/llm_client.py)

## 4. NHANES Query Agent Flow

This is the most important flow for current development.

```mermaid
sequenceDiagram
    participant UI as Browser UI
    participant S as server.py
    participant A as legacy_nhanes_agent.py
    participant R as local_retrieval.py
    participant L as llm_client.py
    participant M as nhanes_metadata_index.py
    participant DB as NhanesLandingZone
    participant FS as ~/.EpiMind

    UI->>S: POST /api/agent/query
    S->>A: run_nhanes_extraction_query(...)
    A->>L: classify intent
    A->>R: retrieve paper chunks
    A->>L: interpret evidence
    A->>M: search metadata candidates
    M->>DB: vector + lexical metadata search
    A->>L: select DB-backed variable candidates
    A->>DB: validate variables/tables against Metadata.QuestionnaireVariables
    A->>FS: optionally write Markdown/JSON report
    S-->>UI: quick answer + optional output tile
```

Active files:

- [server.py](/Users/robert/Projects/Epiconnector/EpiconUI/server.py)
- [legacy_nhanes_agent.py](/Users/robert/Projects/Epiconnector/EpiconUI/legacy_nhanes_agent.py)
- [local_retrieval.py](/Users/robert/Projects/Epiconnector/EpiconUI/local_retrieval.py)
- [nhanes_metadata_index.py](/Users/robert/Projects/Epiconnector/EpiconUI/nhanes_metadata_index.py)

## 5. NHANES Metadata Index Build Flow

```mermaid
sequenceDiagram
    participant CLI as index_nhanes_metadata.py
    participant IDX as nhanes_metadata_index.py
    participant E as embedding_client.py
    participant DB as NhanesLandingZone

    CLI->>IDX: rebuild_metadata_index()
    IDX->>DB: read Metadata.QuestionnaireVariables
    IDX->>E: embed row text
    E-->>IDX: vectors
    IDX->>DB: write epimind.nhanes_variable_metadata
```

Active files:

- [index_nhanes_metadata.py](/Users/robert/Projects/Epiconnector/EpiconUI/index_nhanes_metadata.py)
- [nhanes_metadata_index.py](/Users/robert/Projects/Epiconnector/EpiconUI/nhanes_metadata_index.py)

## Boundary Rules

These are the runtime boundaries a developer should preserve:

- `server.py` should stay a transport layer, not a business-logic sink.
- `legacy_nhanes_agent.py` should orchestrate, not own storage or retrieval primitives.
- `nhanes_metadata_index.py` should search NHANES metadata, not render answers.
- `rag_store.py` should manage paper vector indexing, not NHANES semantics.
- `project_store.py` should manage the filesystem contract, not agent reasoning.
