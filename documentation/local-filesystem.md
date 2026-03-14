# Local Filesystem Layout

`EpiconUI` stores its local working state under `~/.EpiMind`.

## Top Level

```text
~/.EpiMind/
  config/
  Projects/
```

## Config Directory

```text
~/.EpiMind/config/
  llm.json
  rag.json
```

- `llm.json`: saved UI chat model settings
- `rag.json`: Postgres and embedding runtime settings written by the RAG pipeline

## Project Layout

```text
~/.EpiMind/Projects/<project-slug>/
  project.json
  papers/
```

`project.json` contains:

- project name and slug
- paper inventory
- top-level `rag` summary once indexing has happened

## Paper Layout

```text
~/.EpiMind/Projects/<project-slug>/papers/<paper-slug>/
  paper/
  chunks/
  markdown/
  captions/
  figures/
  tables/
  metadata/
  manifest.json
  paper.json
```

### Important Paper Files

- `paper/<original-file>.pdf`: uploaded source PDF
- `chunks/chunks.jsonl`: section-aware chunks used for indexing
- `markdown/<paper-slug>.md`: markdown representation of the paper
- `captions/captions.json`: extracted captions
- `metadata/tables.json`: table manifest
- `metadata/figures.json`: figure manifest
- `manifest.json`: extraction bundle summary
- `paper.json`: paper inventory record for the UI and indexer
- `metadata/vector_index.json`: written after Postgres indexing

## Files Written After Indexing

After `Embed Paper` or `python3 index_rag.py ...`, these metadata blocks are updated:

- `paper.json["rag"]`
- `project.json["rag"]`
- `metadata/vector_index.json`

These are intended to make later R or Python code able to:

- find the local files for a project/paper
- determine the Postgres schema and table names
- find the project and paper IDs in the DB
- identify the embedding model and chunk counts used
