import unittest

from embedding_client import build_embeddings_endpoint


class EmbeddingClientTests(unittest.TestCase):
    def test_build_embeddings_endpoint_appends_suffix(self) -> None:
        self.assertEqual(build_embeddings_endpoint("https://api.openai.com/v1"), "https://api.openai.com/v1/embeddings")

    def test_build_embeddings_endpoint_preserves_existing_suffix(self) -> None:
        self.assertEqual(
            build_embeddings_endpoint("https://example.test/v1/embeddings"),
            "https://example.test/v1/embeddings",
        )


if __name__ == "__main__":
    unittest.main()
