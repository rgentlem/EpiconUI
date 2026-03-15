from __future__ import annotations

import argparse
import json

from nhanes_metadata_index import rebuild_metadata_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or refresh the NHANES metadata vector index.")
    parser.add_argument("--base-dir", default=None, help="Optional override for the .EpiMind root.")
    args = parser.parse_args()
    print(json.dumps(rebuild_metadata_index(base_dir=args.base_dir), indent=2))


if __name__ == "__main__":
    main()
