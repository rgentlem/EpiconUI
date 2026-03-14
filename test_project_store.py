import tempfile
import unittest
from pathlib import Path

from project_store import ensure_paper_paths, ensure_project, list_projects


class ProjectStoreTests(unittest.TestCase):
    def test_ensure_project_creates_expected_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project = ensure_project("Exposure Mapping", base_dir=tmp_dir)
            self.assertTrue(project.root_dir.exists())
            self.assertTrue(project.papers_dir.exists())
            self.assertEqual(project.project_slug, "exposure-mapping")

    def test_ensure_paper_paths_uses_pdf_stem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project = ensure_project("Paper Links", base_dir=tmp_dir)
            pdf_path = Path(tmp_dir) / "cohort-study.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")

            paper = ensure_paper_paths(project, pdf_path)

            self.assertEqual(paper.paper_slug, "cohort-study")
            self.assertTrue(paper.paper_dir.exists())
            self.assertTrue(paper.chunks_dir.exists())
            self.assertEqual(paper.source_pdf_path.name, "cohort-study.pdf")

    def test_list_projects_returns_created_projects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ensure_project("Exposure Mapping", base_dir=tmp_dir)
            ensure_project("Air Quality", base_dir=tmp_dir)

            projects = list_projects(tmp_dir)

            self.assertEqual([project["project_slug"] for project in projects], ["air-quality", "exposure-mapping"])


if __name__ == "__main__":
    unittest.main()
