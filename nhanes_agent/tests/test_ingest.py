import unittest

from nhanes_agent.app.services.ingest.markdown_cleaner import clean_markdown


class IngestTests(unittest.TestCase):
    def test_pdf_markdown_cleaning_is_deterministic(self) -> None:
        self.assertEqual(clean_markdown("A\n\n\nB\r\n"), "A\n\nB")


if __name__ == "__main__":
    unittest.main()
