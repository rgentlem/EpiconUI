from __future__ import annotations

import argparse
import cgi
import json
import tempfile
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from project_store import ensure_project, ingest_pdf_to_project, read_json

APP_ROOT = Path(__file__).resolve().parent


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

        self.send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)

    def handle_project_create(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        payload = json.loads(raw.decode("utf-8") or "{}")
        project_name = str(payload.get("project_name", "")).strip()
        if not project_name:
            self.send_json({"error": "Project name is required."}, status=HTTPStatus.BAD_REQUEST)
            return

        self.send_json(project_payload(project_name, base_dir=self.base_dir))

    def handle_upload(self) -> None:
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            },
        )

        project_name = str(form.getfirst("project_name", "")).strip()
        file_item = form["file"] if "file" in form else None

        if not project_name:
            self.send_json({"error": "Project name is required."}, status=HTTPStatus.BAD_REQUEST)
            return
        if file_item is None or not getattr(file_item, "filename", ""):
            self.send_json({"error": "PDF upload is required."}, status=HTTPStatus.BAD_REQUEST)
            return

        upload_name = safe_upload_name(file_item.filename)
        temp_path: Path | None = None
        temp_dir: tempfile.TemporaryDirectory[str] | None = None
        try:
            temp_dir = tempfile.TemporaryDirectory()
            temp_path = Path(temp_dir.name) / upload_name
            temp_path.write_bytes(file_item.file.read())

            result = ingest_pdf_to_project(
                project_name,
                temp_path,
                base_dir=self.base_dir,
            )
            payload = {
                **result,
                "papers": project_payload(project_name, base_dir=self.base_dir)["papers"],
            }
            self.send_json(payload)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        finally:
            if temp_dir is not None:
                temp_dir.cleanup()

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
