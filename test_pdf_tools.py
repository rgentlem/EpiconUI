import unittest

from pdf_tools import chunk_sections, sections_from_markdown, split_text_evenly


class PdfToolsTests(unittest.TestCase):
    def test_sections_from_markdown_uses_headings(self) -> None:
        markdown = "# Title\n\nIntro text.\n\n## Methods\n\nMethod text.\n\n## Results\n\nResult text."
        sections = sections_from_markdown(markdown)
        self.assertEqual(sections[0][0], "Title")
        self.assertEqual(sections[1][0], "Methods")
        self.assertEqual(sections[2][0], "Results")

    def test_split_text_evenly_returns_similar_chunks(self) -> None:
        text = " ".join(f"word{i}" for i in range(240))
        chunks = split_text_evenly(text, target_tokens=60)
        self.assertGreater(len(chunks), 1)
        lengths = [len(chunk.split()) for chunk in chunks]
        self.assertLess(max(lengths) - min(lengths), 25)

    def test_chunk_sections_preserves_section_names(self) -> None:
        markdown = "## Intro\n\n" + ("alpha " * 120) + "\n\n## Results\n\n" + ("beta " * 120)
        chunks = chunk_sections(markdown, paper_id="demo-paper", target_tokens=50)
        self.assertTrue(any(chunk.section == "Intro" for chunk in chunks))
        self.assertTrue(any(chunk.section == "Results" for chunk in chunks))
        intro_totals = {chunk.total_chunks_in_section for chunk in chunks if chunk.section == "Intro"}
        self.assertEqual(len(intro_totals), 1)


if __name__ == "__main__":
    unittest.main()
