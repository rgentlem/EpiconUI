from __future__ import annotations

import argparse
import json

from rag_store import index_project_paper


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Index a project paper into the EpiconUI pgvector store.")
    parser.add_argument("project", help="Project name or project slug")
    parser.add_argument("paper", help="Paper name or paper slug")
    parser.add_argument("--base-dir", help="Override ~/.EpiMind for testing or custom deployments")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    result = index_project_paper(args.project, args.paper, base_dir=args.base_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
