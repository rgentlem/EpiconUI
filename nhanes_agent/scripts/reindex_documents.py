from __future__ import annotations

import argparse

from project_store import ensure_project, read_json
from rag_store import index_project_paper


def main() -> None:
    """Reindex all papers in a project."""
    parser = argparse.ArgumentParser()
    parser.add_argument("project_name")
    args = parser.parse_args()

    project = ensure_project(args.project_name)
    metadata = read_json(project.metadata_path, {})
    for paper in metadata.get("papers", []):
        index_project_paper(args.project_name, paper["paper_slug"])
        print(f"Reindexed {paper['paper_slug']}")


if __name__ == "__main__":
    main()
