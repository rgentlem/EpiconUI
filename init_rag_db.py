from __future__ import annotations

import argparse
import json

from rag_config import rag_runtime_summary
from rag_store import ensure_schema


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize the EpiconUI pgvector schema.")
    parser.add_argument("--base-dir", help="Override ~/.EpiMind for testing or custom deployments")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    tables = ensure_schema(base_dir=args.base_dir)
    summary = rag_runtime_summary(args.base_dir)
    summary["tables"] = tables
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
