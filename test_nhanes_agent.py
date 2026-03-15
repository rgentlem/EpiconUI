import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from legacy_nhanes_agent import (
    build_markdown_report,
    build_structured_summary,
    canonicalize_cycle_mention,
    classify_query_intent,
    run_nhanes_extraction_query,
)
from project_store import ensure_project, write_json


def build_demo_paper(tmp_dir: str, chunk_rows: list[dict]) -> tuple[Path, Path]:
    project = ensure_project("Demo Project", base_dir=tmp_dir)
    paper_root = project.papers_dir / "cobaltpaper"
    (paper_root / "outputs").mkdir(parents=True, exist_ok=True)
    chunks_dir = paper_root / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = chunks_dir / "chunks.jsonl"
    chunks_path.write_text(
        "\n".join(json.dumps(row) for row in chunk_rows) + "\n",
        encoding="utf-8",
    )

    paper_json = paper_root / "paper.json"
    write_json(
        paper_json,
        {
            "paper_name": "cobaltpaper",
            "paper_slug": "cobaltpaper",
            "paper_dir": str(paper_root),
            "source_pdf": str(paper_root / "paper" / "cobaltpaper.pdf"),
            "outputs_dir": str(paper_root / "outputs"),
            "metadata_path": str(paper_json),
            "manifest": {"chunks_jsonl": str(chunks_path)},
            "outputs": [],
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
                    "outputs_dir": str(paper_root / "outputs"),
                    "metadata_path": str(paper_json),
                    "manifest": {"chunks_jsonl": str(chunks_path)},
                    "outputs": [],
                }
            ],
        },
    )
    return project.metadata_path, paper_json


class NhanesAgentTests(unittest.TestCase):
    def test_classify_query_intent_uses_llm(self) -> None:
        with mock.patch(
            "legacy_nhanes_agent.load_llm_config",
            return_value={"configured": True, "base_url": "x", "api_key": "y", "model": "z"},
        ):
            with mock.patch(
                "legacy_nhanes_agent.create_chat_completion",
                return_value={"content": json.dumps({"intent": "variable_identification", "reason": "Asked for variables."})},
            ):
                intent = classify_query_intent("What NHANES variables were used in this paper?")
        self.assertEqual(intent, "variable_identification")

    def test_canonicalize_cycle_mention_expands_pooled_range(self) -> None:
        self.assertEqual(
            canonicalize_cycle_mention("2015-2018"),
            ["2015-2016", "2017-2018"],
        )

    def test_run_nhanes_extraction_query_uses_llm_for_cycle_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, paper_json = build_demo_paper(
                tmp_dir,
                [{"section": "Abstract", "chunk_index": 1, "text": "The study used NHANES data from 2015-2018."}],
            )

            fake_cursor = mock.MagicMock()
            fake_cursor.fetchall.side_effect = [[], []]
            fake_cursor.description = [
                mock.Mock(name="Variable"),
                mock.Mock(name="TableName"),
                mock.Mock(name="VariableDescription"),
                mock.Mock(name="Component"),
            ]
            fake_connection = mock.MagicMock()
            fake_connection.__enter__.return_value = fake_connection
            fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

            llm_responses = [
                {"content": json.dumps({"intent": "cycle_identification", "reason": "Asked which NHANES cycles were used."})},
                {
                    "content": json.dumps(
                        {
                            "summary": "The abstract reports NHANES 2015-2018.",
                            "cycles": [
                                {
                                    "raw_mention": "2015-2018",
                                    "evidence_chunk_id": "Abstract:1",
                                    "evidence_quote": "used NHANES data from 2015-2018",
                                    "confidence": 0.98,
                                }
                            ],
                            "components": [],
                            "tables": [],
                            "variables": [],
                            "notes": ["Found in the abstract."],
                        }
                    )
                },
            ]

            with mock.patch("legacy_nhanes_agent.connect_database", return_value=fake_connection):
                with mock.patch(
                    "legacy_nhanes_agent.load_llm_config",
                    return_value={"configured": True, "base_url": "x", "api_key": "y", "model": "z"},
                ):
                    with mock.patch("legacy_nhanes_agent.create_chat_completion", side_effect=llm_responses):
                        result = run_nhanes_extraction_query(
                            "Demo Project",
                            "cobaltpaper",
                            "What cycles of NHANES data were used in this paper?",
                            base_dir=tmp_dir,
                            save_output=False,
                        )

            self.assertTrue(result["analysis"]["llm_used"])
            self.assertIn("2015-2016", result["quick_answer"])
            self.assertIn("2017-2018", result["quick_answer"])
            self.assertIn("Found in the abstract.", result["analysis"]["interpretation_notes"])
            paper_payload = json.loads(paper_json.read_text(encoding="utf-8"))
            self.assertEqual(paper_payload["outputs"], [])

    def test_run_nhanes_extraction_query_does_not_fallback_when_variables_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            build_demo_paper(
                tmp_dir,
                [{"section": "Methods", "chunk_index": 1, "text": "The analysis included BMI and age as covariates."}],
            )

            fake_cursor = mock.MagicMock()
            fake_cursor.fetchall.side_effect = [[], []]
            fake_cursor.description = [
                mock.Mock(name="Variable"),
                mock.Mock(name="TableName"),
                mock.Mock(name="VariableDescription"),
                mock.Mock(name="Component"),
            ]
            fake_connection = mock.MagicMock()
            fake_connection.__enter__.return_value = fake_connection
            fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

            llm_responses = [
                {"content": json.dumps({"intent": "variable_identification", "reason": "Asked for variables."})},
                {"content": json.dumps({"summary": "", "cycles": [], "components": [], "tables": [], "variables": [], "notes": []})},
                {"content": json.dumps({"variables": [], "tables": [], "notes": []})},
            ]

            with mock.patch("legacy_nhanes_agent.connect_database", return_value=fake_connection):
                with mock.patch(
                    "legacy_nhanes_agent.load_llm_config",
                    return_value={"configured": True, "base_url": "x", "api_key": "y", "model": "z"},
                ):
                    with mock.patch("legacy_nhanes_agent.create_chat_completion", side_effect=llm_responses):
                        with mock.patch("legacy_nhanes_agent.search_metadata_candidates", return_value=[]):
                            result = run_nhanes_extraction_query(
                                "Demo Project",
                                "cobaltpaper",
                                "What NHANES variables were used in this paper?",
                                base_dir=tmp_dir,
                                save_output=False,
                        )

            self.assertEqual(result["analysis"]["validated"]["variables"], [])
            self.assertIn("could not determine validated nhanes variable names", result["quick_answer"].lower())

    def test_run_nhanes_extraction_query_uses_metadata_candidates_for_variables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            build_demo_paper(
                tmp_dir,
                [{"section": "Methods", "chunk_index": 1, "text": "Serum cobalt and age in years at screening were included in the analysis."}],
            )

            fake_cursor = mock.MagicMock()
            fake_cursor.fetchall.side_effect = [
                [("DEMO_I",), ("LAB_I",)],
                [("RIDAGEYR", "DEMO_I", "Age in years at screening", "Demographics"), ("LBXBCD", "LAB_I", "Cobalt", "Laboratory")],
            ]
            fake_cursor.description = [
                mock.Mock(name="Variable"),
                mock.Mock(name="TableName"),
                mock.Mock(name="VariableDescription"),
                mock.Mock(name="Component"),
            ]
            fake_connection = mock.MagicMock()
            fake_connection.__enter__.return_value = fake_connection
            fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

            llm_responses = [
                {"content": json.dumps({"intent": "variable_identification", "reason": "Asked for variables."})},
                {
                    "content": json.dumps(
                        {
                            "summary": "The methods mention serum cobalt and age in years at screening.",
                            "cycles": [{"raw_mention": "2015-2018", "evidence_chunk_id": "Methods:1", "confidence": 0.9}],
                            "components": [{"raw_mention": "laboratory", "evidence_chunk_id": "Methods:1", "confidence": 0.8}],
                            "tables": [],
                            "variables": [
                                {"raw_mention": "cobalt", "evidence_chunk_id": "Methods:1", "confidence": 0.8},
                                {"raw_mention": "age in years at screening", "evidence_chunk_id": "Methods:1", "confidence": 0.9},
                            ],
                            "notes": [],
                        }
                    )
                },
                {
                    "content": json.dumps(
                        {
                            "variables": [
                                {
                                    "paper_mention": "cobalt",
                                    "variable_name": "LBXBCD",
                                    "table_name": "LAB_I",
                                    "canonical_label": "Cobalt",
                                    "component": "Laboratory",
                                    "cycle": "2015-2016",
                                    "evidence_chunk_id": "Methods:1",
                                    "confidence": 0.92,
                                },
                                {
                                    "paper_mention": "age in years at screening",
                                    "variable_name": "RIDAGEYR",
                                    "table_name": "DEMO_I",
                                    "canonical_label": "Age in years at screening",
                                    "component": "Demographics",
                                    "cycle": "2015-2016",
                                    "evidence_chunk_id": "Methods:1",
                                    "confidence": 0.95,
                                },
                            ],
                            "tables": [],
                            "notes": [],
                        }
                    )
                },
            ]

            mock_candidates = [
                mock.Mock(
                    variable_name="LBXBCD",
                    table_name="LAB_I",
                    canonical_label="Cobalt",
                    component="Laboratory",
                    cycle="2015-2016",
                    searchable_text="",
                    total_score=1.9,
                ),
                mock.Mock(
                    variable_name="RIDAGEYR",
                    table_name="DEMO_I",
                    canonical_label="Age in years at screening",
                    component="Demographics",
                    cycle="2015-2016",
                    searchable_text="",
                    total_score=1.8,
                ),
            ]

            with mock.patch("legacy_nhanes_agent.connect_database", return_value=fake_connection):
                with mock.patch(
                    "legacy_nhanes_agent.load_llm_config",
                    return_value={"configured": True, "base_url": "x", "api_key": "y", "model": "z"},
                ):
                    with mock.patch("legacy_nhanes_agent.create_chat_completion", side_effect=llm_responses):
                        with mock.patch("legacy_nhanes_agent.search_metadata_candidates", return_value=mock_candidates):
                            result = run_nhanes_extraction_query(
                                "Demo Project",
                                "cobaltpaper",
                                "What NHANES variables were used in this paper?",
                                base_dir=tmp_dir,
                                save_output=False,
                            )

            variable_names = [row["variable"] for row in result["analysis"]["validated"]["variables"]]
            self.assertIn("LBXBCD", variable_names)
            self.assertIn("RIDAGEYR", variable_names)
            self.assertIn("selected_metadata_variables", result["analysis"])
            for row in result["analysis"]["validated"]["variables"]:
                for match in row.get("matches", []):
                    self.assertIn(match["cycle"], {"2015-2016", "2017-2018"})

    def test_variable_validation_is_constrained_by_inferred_cycles_and_selected_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            build_demo_paper(
                tmp_dir,
                [{"section": "Abstract", "chunk_index": 1, "text": "The study used NHANES 2015-2018 data and measured cobalt."}],
            )

            fake_cursor = mock.MagicMock()
            fake_cursor.fetchall.side_effect = [
                [("LAB_I",)],
                [
                    ("LBXBCD", "LAB_A", "Cobalt", "Laboratory"),
                    ("LBXBCD", "LAB_I", "Cobalt", "Laboratory"),
                    ("LBXBCD", "LAB_J", "Cobalt", "Laboratory"),
                ],
            ]
            fake_cursor.description = [
                mock.Mock(name="Variable"),
                mock.Mock(name="TableName"),
                mock.Mock(name="VariableDescription"),
                mock.Mock(name="Component"),
            ]
            fake_connection = mock.MagicMock()
            fake_connection.__enter__.return_value = fake_connection
            fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

            llm_responses = [
                {"content": json.dumps({"intent": "variable_identification", "reason": "Asked for variables."})},
                {
                    "content": json.dumps(
                        {
                            "summary": "The abstract reports NHANES 2015-2018 and cobalt.",
                            "cycles": [{"raw_mention": "2015-2018", "evidence_chunk_id": "Abstract:1", "confidence": 0.98}],
                            "components": [{"raw_mention": "laboratory", "evidence_chunk_id": "Abstract:1", "confidence": 0.8}],
                            "tables": [],
                            "variables": [{"raw_mention": "cobalt", "evidence_chunk_id": "Abstract:1", "confidence": 0.85}],
                            "notes": [],
                        }
                    )
                },
                {
                    "content": json.dumps(
                        {
                            "variables": [
                                {
                                    "paper_mention": "cobalt",
                                    "variable_name": "LBXBCD",
                                    "table_name": "LAB_I",
                                    "canonical_label": "Cobalt",
                                    "component": "Laboratory",
                                    "cycle": "2015-2016",
                                    "evidence_chunk_id": "Abstract:1",
                                    "confidence": 0.94,
                                }
                            ],
                            "tables": [],
                            "notes": [],
                        }
                    )
                },
            ]

            mock_candidates = [
                mock.Mock(
                    variable_name="LBXBCD",
                    table_name="LAB_I",
                    canonical_label="Cobalt",
                    component="Laboratory",
                    cycle="2015-2016",
                    searchable_text="",
                    total_score=1.9,
                )
            ]

            with mock.patch("legacy_nhanes_agent.connect_database", return_value=fake_connection):
                with mock.patch(
                    "legacy_nhanes_agent.load_llm_config",
                    return_value={"configured": True, "base_url": "x", "api_key": "y", "model": "z"},
                ):
                    with mock.patch("legacy_nhanes_agent.create_chat_completion", side_effect=llm_responses):
                        with mock.patch("legacy_nhanes_agent.search_metadata_candidates", return_value=mock_candidates):
                            result = run_nhanes_extraction_query(
                                "Demo Project",
                                "cobaltpaper",
                                "What NHANES variables were used in this paper?",
                                base_dir=tmp_dir,
                                save_output=False,
                            )

            lbxbcd_row = next(
                row for row in result["analysis"]["validated"]["variables"] if row["variable"] == "LBXBCD"
            )
            matches = lbxbcd_row["matches"]
            self.assertEqual([match["table_name"] for match in matches], ["LAB_I"])

    def test_variable_output_reports_translated_nhanes_variables_not_raw_concepts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            build_demo_paper(
                tmp_dir,
                [{"section": "Methods", "chunk_index": 1, "text": "Age, BMI, HDL-C, and LDL-C were included in the models."}],
            )

            fake_cursor = mock.MagicMock()
            fake_cursor.fetchall.side_effect = [
                [("DEMO_I",)],
                [("RIDAGEYR", "DEMO_I", "Age in years at screening", "Demographics")],
            ]
            fake_cursor.description = [
                mock.Mock(name="Variable"),
                mock.Mock(name="TableName"),
                mock.Mock(name="VariableDescription"),
                mock.Mock(name="Component"),
            ]
            fake_connection = mock.MagicMock()
            fake_connection.__enter__.return_value = fake_connection
            fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

            llm_responses = [
                {"content": json.dumps({"intent": "variable_identification", "reason": "Asked for variables."})},
                {
                    "content": json.dumps(
                        {
                            "summary": "The methods mention age, BMI, HDL-C, and LDL-C.",
                            "cycles": [{"raw_mention": "2015-2018", "evidence_chunk_id": "Methods:1", "confidence": 0.9}],
                            "components": [{"raw_mention": "demographics", "evidence_chunk_id": "Methods:1", "confidence": 0.75}],
                            "tables": [],
                            "variables": [
                                {"raw_mention": "Age", "evidence_chunk_id": "Methods:1", "confidence": 0.95},
                                {"raw_mention": "BMI", "evidence_chunk_id": "Methods:1", "confidence": 0.85},
                                {"raw_mention": "HDL-C", "evidence_chunk_id": "Methods:1", "confidence": 0.8},
                                {"raw_mention": "LDL-C", "evidence_chunk_id": "Methods:1", "confidence": 0.8},
                            ],
                            "notes": [],
                        }
                    )
                },
                {
                    "content": json.dumps(
                        {
                            "variables": [
                                {
                                    "paper_mention": "Age",
                                    "variable_name": "RIDAGEYR",
                                    "table_name": "DEMO_I",
                                    "canonical_label": "Age in years at screening",
                                    "component": "Demographics",
                                    "cycle": "2015-2016",
                                    "evidence_chunk_id": "Methods:1",
                                    "confidence": 0.95,
                                }
                            ],
                            "tables": [],
                            "notes": [],
                        }
                    )
                },
            ]

            mock_candidates = [
                mock.Mock(
                    variable_name="RIDAGEYR",
                    table_name="DEMO_I",
                    canonical_label="Age in years at screening",
                    component="Demographics",
                    cycle="2015-2016",
                    searchable_text="",
                    total_score=1.8,
                )
            ]

            with mock.patch("legacy_nhanes_agent.connect_database", return_value=fake_connection):
                with mock.patch(
                    "legacy_nhanes_agent.load_llm_config",
                    return_value={"configured": True, "base_url": "x", "api_key": "y", "model": "z"},
                ):
                    with mock.patch("legacy_nhanes_agent.create_chat_completion", side_effect=llm_responses):
                        with mock.patch("legacy_nhanes_agent.search_metadata_candidates", return_value=mock_candidates):
                            result = run_nhanes_extraction_query(
                                "Demo Project",
                                "cobaltpaper",
                                "Please describe the NHANES variables you have detected in this paper.",
                                base_dir=tmp_dir,
                                save_output=False,
                            )

            variable_names = [row["variable"] for row in result["analysis"]["validated"]["variables"]]
            self.assertEqual(variable_names, ["RIDAGEYR"])
            structured_json = json.dumps(result["analysis"]["structured_summary"])
            self.assertIn("DEMO_I", structured_json)
            self.assertIn("\"paper_mentions\": [\"Age\"]", structured_json)
            notes_text = " ".join(result["analysis"]["interpretation_notes"])
            self.assertIn("BMI", notes_text)
            self.assertIn("HDL-C", notes_text)
            self.assertIn("LDL-C", notes_text)

    def test_build_markdown_report_contains_machine_parseable_json(self) -> None:
        analysis = {
            "query": "What NHANES variables were used in this paper?",
            "summary": "The paper uses the NHANES variables RIDAGEYR.",
            "intent": "variable_identification",
            "project_name": "Demo Project",
            "paper_name": "cobaltpaper",
            "retrieval": {
                "chunks": [{"section": "Methods", "chunk_index": 1, "text": "RIDAGEYR was included.", "score": 5.4}],
            },
            "validated": {
                "cycles": [],
                "tables": [],
                "variables": [{"variable": "RIDAGEYR", "status": "validated", "matches": [{"table_name": "DEMO_I", "cycle": "2015-2016", "component": "Demographics", "description": "Age in years at screening"}]}],
            },
            "interpretation_notes": [],
            "llm_summary": "",
        }
        analysis["structured_summary"] = build_structured_summary(analysis)

        markdown = build_markdown_report(analysis)

        self.assertIn("## Structured Summary", markdown)
        self.assertIn("\"table_name\": \"DEMO_I\"", markdown)
        self.assertIn("## Machine Parseable JSON", markdown)
        self.assertIn("- RIDAGEYR: validated", markdown)
        self.assertIn("  - DEMO_I | 2015-2016 | Demographics | Age in years at screening", markdown)


if __name__ == "__main__":
    unittest.main()
