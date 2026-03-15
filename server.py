from __future__ import annotations

import argparse
import json
import os
import tempfile
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from config_store import clear_llm_config, llm_config_summary, load_llm_config, save_llm_config
from llm_client import create_chat_completion
from project_store import ensure_project, ingest_pdf_to_project, list_projects, read_json

APP_ROOT = Path(__file__).resolve().parent
AUTO_INDEX_RAG = os.environ.get("EPIMIND_AUTO_INDEX_RAG", "").strip().lower() in {"1", "true", "yes", "on"}


def parse_multipart_form_data(content_type: str, body: bytes) -> dict[str, list[dict[str, str | bytes]]]:
    if not content_type.startswith("multipart/form-data"):
        raise ValueError("Expected multipart/form-data content type.")

    header_block = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=default).parsebytes(header_block + body)

    fields: dict[str, list[dict[str, str | bytes]]] = {}
    for part in message.iter_parts():
        disposition = part.get_content_disposition()
        if disposition != "form-data":
            continue

        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        content = part.get_payload(decode=True) or b""
        if not name:
            continue

        fields.setdefault(name, []).append(
            {
                "filename": filename or "",
                "value": content.decode("utf-8", errors="replace") if not filename else "",
                "content": content,
            }
        )
    return fields


def safe_upload_name(filename: str) -> str:
    candidate = Path(filename).name.strip() or "upload.pdf"
    cleaned = "".join(char for char in candidate if char.isalnum() or char in {"-", "_", ".", " "}).strip()
    return cleaned or "upload.pdf"


def project_payload(project_name: str, base_dir: str | Path | None = None) -> dict:
    project = ensure_project(project_name, base_dir=base_dir)
    metadata = read_json(project.metadata_path, {})
    return {
        "project": {
            "project_name": project.project_name,
            "project_slug": project.project_slug,
            "root_dir": str(project.root_dir),
            "papers_dir": str(project.papers_dir),
            "metadata_path": str(project.metadata_path),
        },
        "papers": metadata.get("papers", []),
    }


def paper_record(project_name: str, paper_slug: str, base_dir: str | Path | None = None) -> dict | None:
    project = ensure_project(project_name, base_dir=base_dir)
    metadata = read_json(project.metadata_path, {})
    for item in metadata.get("papers", []):
        if item.get("paper_slug") == paper_slug:
            return item
    return None


def output_record(
    project_name: str,
    paper_slug: str,
    output_id: str,
    base_dir: str | Path | None = None,
) -> tuple[dict | None, dict | None]:
    paper = paper_record(project_name, paper_slug, base_dir=base_dir)
    if not paper:
        return None, None
    for item in paper.get("outputs", []):
        if item.get("output_id") == output_id:
            return paper, item
    return paper, None


def run_paper_action(action: str, project_name: str, paper_slug: str, base_dir: str | Path | None = None) -> dict:
    normalized = action.strip().lower()
    if normalized == "index_rag":
        from rag_store import index_project_paper

        return index_project_paper(project_name, paper_slug, base_dir=base_dir)
    raise ValueError(f"Unsupported paper action: {action}")


def load_paper_context(project_name: str, paper_slug: str, base_dir: str | Path | None = None) -> str:
    record = paper_record(project_name, paper_slug, base_dir=base_dir)
    if not record:
        return ""

    manifest = record.get("manifest", {})
    markdown_path = Path(manifest.get("paper_markdown", ""))
    chunks_path = Path(manifest.get("chunks_jsonl", ""))

    sections: list[str] = []
    if markdown_path.exists():
        markdown_text = markdown_path.read_text(encoding="utf-8")
        excerpt = markdown_text[:5000].strip()
        if excerpt:
            sections.append(f"Paper markdown excerpt:\n{excerpt}")

    if chunks_path.exists():
        chunk_lines = chunks_path.read_text(encoding="utf-8").splitlines()[:4]
        chunk_texts: list[str] = []
        for line in chunk_lines:
            payload = json.loads(line)
            chunk_texts.append(
                f"[{payload.get('section', 'document')} chunk {payload.get('chunk_index', 1)}] {payload.get('text', '')}"
            )
        if chunk_texts:
            sections.append("Chunk excerpts:\n" + "\n\n".join(chunk_texts))

    return "\n\n".join(part for part in sections if part.strip())


class EpiMindHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, base_dir: str | Path | None = None, **kwargs):
        self.base_dir = base_dir
        super().__init__(*args, directory=str(APP_ROOT if directory is None else directory), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json({"ok": True})
            return

        if parsed.path == "/api/project":
            query = parse_qs(parsed.query)
            project_name = (query.get("name") or [""])[0].strip()
            if not project_name:
                self.send_json({"error": "Missing project name."}, status=HTTPStatus.BAD_REQUEST)
                return
            self.send_json(project_payload(project_name, base_dir=self.base_dir))
            return

        if parsed.path == "/api/projects":
            self.send_json({"projects": list_projects(self.base_dir)})
            return

        if parsed.path == "/api/llm/config":
            self.send_json(llm_config_summary(self.base_dir))
            return

        if parsed.path == "/api/output-file":
            self.handle_output_file(parsed.query)
            return

        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/projects":
            self.handle_project_create()
            return

        if parsed.path == "/api/upload":
            self.handle_upload()
            return

        if parsed.path == "/api/llm/config":
            self.handle_llm_config_upsert()
            return

        if parsed.path == "/api/chat":
            self.handle_chat()
            return

        if parsed.path == "/api/agent/query":
            self.handle_agent_query()
            return

        if parsed.path == "/api/paper-actions":
            self.handle_paper_action()
            return

        self.send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/llm/config":
            clear_llm_config(self.base_dir)
            self.send_json({"ok": True})
            return
        self.send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)

    def handle_project_create(self) -> None:
        payload = self.read_json_body()
        project_name = str(payload.get("project_name", "")).strip()
        if not project_name:
            self.send_json({"error": "Project name is required."}, status=HTTPStatus.BAD_REQUEST)
            return

        self.send_json(project_payload(project_name, base_dir=self.base_dir))

    def read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def handle_llm_config_upsert(self) -> None:
        payload = self.read_json_body()
        try:
            summary = save_llm_config(
                base_url=str(payload.get("base_url", "")),
                model=str(payload.get("model", "")),
                api_key=str(payload.get("api_key", "")),
                system_prompt=str(payload.get("system_prompt", "")),
                base_dir=self.base_dir,
            )
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        self.send_json(summary)

    def handle_chat(self) -> None:
        payload = self.read_json_body()
        message = str(payload.get("message", "")).strip()
        project_name = str(payload.get("project_name", "")).strip()
        paper_slug = str(payload.get("paper_slug", "")).strip()

        if not message:
            self.send_json({"error": "Message is required."}, status=HTTPStatus.BAD_REQUEST)
            return

        config = load_llm_config(self.base_dir)
        if not config["configured"]:
            self.send_json(
                {"error": "LLM connection is not configured yet. Save the API URL, model, and API key first."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        base_system_prompt = config.get("system_prompt") or (
            "You are assisting inside EpiconUI. Use the supplied project and paper context when it is available."
        )
        messages = [{"role": "system", "content": base_system_prompt}]

        if project_name and paper_slug:
            context = load_paper_context(project_name, paper_slug, base_dir=self.base_dir)
            if context:
                messages.append(
                    {
                        "role": "system",
                        "content": (
                            f"Selected project: {project_name}\nSelected paper: {paper_slug}\n\n{context}"
                        ),
                    }
                )

        messages.append({"role": "user", "content": message})

        try:
            result = create_chat_completion(
                base_url=config["base_url"],
                api_key=config["api_key"],
                model=config["model"],
                messages=messages,
            )
        except RuntimeError as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
            return

        self.send_json(
            {
                "answer": result["content"],
                "model": config["model"],
                "paper_slug": paper_slug,
            }
        )

    def handle_agent_query(self) -> None:
        payload = self.read_json_body()
        message = str(payload.get("message", "")).strip()
        project_name = str(payload.get("project_name", "")).strip()
        paper_slug = str(payload.get("paper_slug", "")).strip()
        save_output = bool(payload.get("save_output", True))

        if not message:
            self.send_json({"error": "Message is required."}, status=HTTPStatus.BAD_REQUEST)
            return
        if not project_name:
            self.send_json({"error": "Project name is required."}, status=HTTPStatus.BAD_REQUEST)
            return
        if not paper_slug:
            self.send_json({"error": "Paper slug is required."}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            from nhanes_agent import run_nhanes_extraction_query

            result = run_nhanes_extraction_query(
                project_name,
                paper_slug,
                message,
                base_dir=self.base_dir,
                save_output=save_output,
            )
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        refreshed = project_payload(project_name, base_dir=self.base_dir)
        self.send_json(
            {
                **result,
                "project": refreshed["project"],
                "papers": refreshed["papers"],
                "paper": paper_record(project_name, paper_slug, base_dir=self.base_dir),
            }
        )

    def handle_paper_action(self) -> None:
        payload = self.read_json_body()
        action = str(payload.get("action", "")).strip()
        project_name = str(payload.get("project_name", "")).strip()
        paper_slug = str(payload.get("paper_slug", "")).strip()

        if not action:
            self.send_json({"error": "Action is required."}, status=HTTPStatus.BAD_REQUEST)
            return
        if not project_name:
            self.send_json({"error": "Project name is required."}, status=HTTPStatus.BAD_REQUEST)
            return
        if not paper_slug:
            self.send_json({"error": "Paper slug is required."}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            result = run_paper_action(action, project_name, paper_slug, base_dir=self.base_dir)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        refreshed = project_payload(project_name, base_dir=self.base_dir)
        self.send_json(
            {
                "ok": True,
                "action": action,
                "result": result,
                "project": refreshed["project"],
                "papers": refreshed["papers"],
                "paper": paper_record(project_name, paper_slug, base_dir=self.base_dir),
            }
        )

    def handle_upload(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""

        try:
            form = parse_multipart_form_data(content_type, body)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        project_name = str((form.get("project_name") or [{"value": ""}])[0]["value"]).strip()
        file_item = (form.get("file") or [None])[0]

        if not project_name:
            self.send_json({"error": "Project name is required."}, status=HTTPStatus.BAD_REQUEST)
            return
        if file_item is None or not str(file_item.get("filename", "")).strip():
            self.send_json({"error": "PDF upload is required."}, status=HTTPStatus.BAD_REQUEST)
            return

        upload_name = safe_upload_name(str(file_item["filename"]))
        temp_path: Path | None = None
        temp_dir: tempfile.TemporaryDirectory[str] | None = None
        try:
            temp_dir = tempfile.TemporaryDirectory()
            temp_path = Path(temp_dir.name) / upload_name
            temp_path.write_bytes(bytes(file_item["content"]))

            result = ingest_pdf_to_project(
                project_name,
                temp_path,
                base_dir=self.base_dir,
            )
            rag_payload = None
            if AUTO_INDEX_RAG:
                try:
                    from rag_store import index_project_paper

                    rag_payload = index_project_paper(
                        result["project"]["project_slug"],
                        result["paper"]["paper_slug"],
                        base_dir=self.base_dir,
                    )
                except Exception as exc:
                    rag_payload = {
                        "indexed": False,
                        "error": str(exc),
                    }
            payload = {
                **result,
                "papers": project_payload(project_name, base_dir=self.base_dir)["papers"],
                "rag": rag_payload,
            }
            self.send_json(payload)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        finally:
            if temp_dir is not None:
                temp_dir.cleanup()

    def handle_output_file(self, query_string: str) -> None:
        query = parse_qs(query_string)
        project_name = (query.get("project_name") or [""])[0].strip()
        paper_slug = (query.get("paper_slug") or [""])[0].strip()
        output_id = (query.get("output_id") or [""])[0].strip()
        output_format = (query.get("format") or ["markdown"])[0].strip().lower()

        if not project_name or not paper_slug or not output_id:
            self.send_json({"error": "project_name, paper_slug, and output_id are required."}, status=HTTPStatus.BAD_REQUEST)
            return

        paper, record = output_record(project_name, paper_slug, output_id, base_dir=self.base_dir)
        if not paper or not record:
            self.send_json({"error": "Output not found."}, status=HTTPStatus.NOT_FOUND)
            return

        file_key = "json_path" if output_format == "json" else "markdown_path"
        path = Path(str(record.get(file_key) or ""))
        if not path.exists():
            self.send_json({"error": "Output file is missing."}, status=HTTPStatus.NOT_FOUND)
            return

        content = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        if output_format == "json":
            self.send_header("Content-Type", "application/json; charset=utf-8")
        else:
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def build_handler(base_dir: str | Path | None = None):
    def handler(*args, **kwargs):
        EpiMindHandler(*args, base_dir=base_dir, **kwargs)

    return handler


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the EpiconUI local web server.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8765, help="Bind port")
    parser.add_argument("--base-dir", help="Override ~/.EpiMind for testing")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    handler = build_handler(base_dir=args.base_dir)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving EpiconUI at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
