import json
import unittest

from nhanes_agent.app.services.output.markdown_renderer import render_markdown_answer


class OutputTests(unittest.TestCase):
    def test_markdown_renderer_always_emits_required_sections(self) -> None:
        markdown = render_markdown_answer(
            {
                "query": "test",
                "summary": "summary",
                "evidence": [],
                "cycles": [],
                "components": [],
                "variables": [],
                "notes": [],
                "machine_summary": {"query": "test", "cycles": [], "components": [], "variables": [], "evidence_chunk_ids": []},
            }
        )
        self.assertIn("# Query Result", markdown)
        self.assertIn("## Query", markdown)
        self.assertIn("## Summary", markdown)
        self.assertIn("## Retrieved Evidence", markdown)
        self.assertIn("## NHANES Cycles", markdown)
        self.assertIn("## NHANES Components", markdown)
        self.assertIn("## NHANES Variables", markdown)
        self.assertIn("## Notes", markdown)
        self.assertIn("## Machine-Readable Summary", markdown)

    def test_machine_readable_json_block_is_valid(self) -> None:
        markdown = render_markdown_answer(
            {
                "query": "test",
                "summary": "summary",
                "evidence": [],
                "cycles": [],
                "components": [],
                "variables": [],
                "notes": [],
                "machine_summary": {"query": "test", "cycles": [], "components": [], "variables": [], "evidence_chunk_ids": []},
            }
        )
        json_block = markdown.split("```json\n", 1)[1].split("\n```", 1)[0]
        self.assertEqual(json.loads(json_block)["query"], "test")


if __name__ == "__main__":
    unittest.main()
