import tempfile
import unittest
from pathlib import Path

from project_store import ensure_project, write_json
from rag_store import build_schema_statements, build_section_rows, load_chunk_rows, load_paper_metadata, vector_literal


class RagStoreTests(unittest.TestCase):
    def test_vector_literal_formats_pgvector_string(self) -> None:
        self.assertEqual(vector_literal([1, 2.5, 3]), "[1.0000000000,2.5000000000,3.0000000000]")

    def test_build_schema_statements_include_chunk_embeddings_dimension(self) -> None:
        sql = "\n".join(build_schema_statements("epimind", 1536))
        self.assertIn("chunk_embeddings", sql)
        self.assertIn("vector(1536)", sql)

    def test_build_section_rows_generates_stable_keys(self) -> None:
        sections, chunk_rows = build_section_rows(
            [
                {"section": "Abstract", "chunk_index": 1},
                {"section": "Abstract", "chunk_index": 2},
                {"section": "Methods", "chunk_index": 1},
            ]
        )
        self.assertEqual([section["section_key"] for section in sections], ["abstract-001", "methods-001"])
        self.assertEqual(chunk_rows[0]["chunk_key"], "abstract-001:001")
        self.assertEqual(chunk_rows[2]["chunk_key"], "methods-001:001")

    def test_load_chunk_rows_reads_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "chunks.jsonl"
            path.write_text('{"section":"Intro","chunk_index":1}\n{"section":"Intro","chunk_index":2}\n', encoding="utf-8")
            rows = load_chunk_rows(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1]["chunk_index"], 2)

    def test_load_paper_metadata_falls_back_to_paper_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project = ensure_project("Demo Project", base_dir=tmp_dir)
            paper_root = project.papers_dir / "cobaltpaper"
            paper_root.mkdir(parents=True)
            paper_json = paper_root / "paper.json"
            write_json(
                paper_json,
                {
                    "paper_name": "cobaltpaper",
                    "paper_slug": "cobaltpaper",
                    "paper_dir": str(paper_root),
                    "source_pdf": str(paper_root / "paper" / "cobaltpaper.pdf"),
                },
            )
            write_json(
                project.metadata_path,
                {
                    "project_name": "Demo Project",
                    "project_slug": "demo-project",
                    "papers": [
                        {
                            "paper_name": "cobaltpaper",
                            "paper_slug": "cobaltpaper",
                            "paper_dir": str(paper_root),
                            "metadata_path": "",
                        }
                    ],
                },
            )

            _project_meta, paper_meta, _project_path, paper_path = load_paper_metadata(
                "Demo Project",
                "cobaltpaper",
                base_dir=tmp_dir,
            )

            self.assertEqual(paper_meta["paper_slug"], "cobaltpaper")
            self.assertEqual(paper_path, paper_json)


if __name__ == "__main__":
    unittest.main()
