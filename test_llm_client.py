import unittest

from llm_client import build_chat_endpoint, extract_text_content


class LlmClientTests(unittest.TestCase):
    def test_build_chat_endpoint_appends_route(self) -> None:
        self.assertEqual(
            build_chat_endpoint("https://example.com/v1"),
            "https://example.com/v1/chat/completions",
        )

    def test_extract_text_content_handles_openai_style_parts(self) -> None:
        content = extract_text_content(
            [
                {"type": "text", "text": "Hello"},
                {"type": "text", "text": "world"},
            ]
        )
        self.assertEqual(content, "Hello\nworld")


if __name__ == "__main__":
    unittest.main()
