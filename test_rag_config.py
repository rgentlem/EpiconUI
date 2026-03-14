import os
import tempfile
import unittest
from unittest import mock

from rag_config import load_database_config, load_embedding_config, save_rag_runtime_config


class RagConfigTests(unittest.TestCase):
    def test_load_database_config_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, mock.patch.dict(os.environ, {}, clear=True):
            config = load_database_config(tmp_dir)
            self.assertEqual(config.host, "127.0.0.1")
            self.assertEqual(config.dbname, "epimind")
            self.assertEqual(config.schema, "epimind")

    def test_saved_runtime_config_becomes_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, mock.patch.dict(os.environ, {}, clear=True):
            save_rag_runtime_config(
                base_dir=tmp_dir,
                tables={"projects": "epimind.projects"},
            )
            config = load_embedding_config(tmp_dir)
            self.assertEqual(config.model, "text-embedding-3-small")


if __name__ == "__main__":
    unittest.main()
