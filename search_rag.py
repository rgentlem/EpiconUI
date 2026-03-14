from __future__ import annotations

import argparse
import json

from rag_store import search_chunks


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search the EpiconUI pgvector store.")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--project", help="Project name or slug filter")
    parser.add_argument("--paper", help="Paper name or slug filter")
    parser.add_argument("--top-k", type=int, default=6, help="Number of chunks to return")
    parser.add_argument("--base-dir", help="Override ~/.EpiMind for testing or custom deployments")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    result = search_chunks(
        args.query,
        project_name_or_slug=args.project,
        paper_name_or_slug=args.paper,
        top_k=args.top_k,
        base_dir=args.base_dir,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
