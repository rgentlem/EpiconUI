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

## Run

Start the local server:

```bash
python3 server.py
```

Then open `http://127.0.0.1:8765` in a browser.

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
