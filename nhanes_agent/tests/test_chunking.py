import unittest

from nhanes_agent.app.services.ingest.chunker import chunk_sections


class ChunkingTests(unittest.TestCase):
    def test_chunks_created_deterministically(self) -> None:
        sections = [{"heading": "Methods", "text": "word " * 200}]
        first = chunk_sections(sections, target_tokens=40, overlap_tokens=0)
        second = chunk_sections(sections, target_tokens=40, overlap_tokens=0)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
