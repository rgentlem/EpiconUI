import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config_store import DEFAULT_OPENAI_BASE_URL, DEFAULT_OPENAI_MODEL, llm_config_path, load_llm_config, save_llm_config


class ConfigStoreTests(unittest.TestCase):
    def test_save_and_load_llm_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            saved = save_llm_config(
                base_url="https://example.com/v1",
                model="gpt-4o-mini",
                api_key="secret-key-123",
                system_prompt="Be concise.",
                base_dir=tmp_dir,
            )
            loaded = load_llm_config(tmp_dir)

            self.assertTrue(saved["configured"])
            self.assertEqual(loaded["base_url"], "https://example.com/v1")
            self.assertEqual(loaded["model"], "gpt-4o-mini")
            self.assertEqual(loaded["system_prompt"], "Be concise.")
            self.assertTrue(Path(llm_config_path(tmp_dir)).exists())

    def test_load_llm_config_uses_environment_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"OPENAI_API_KEY": "env-secret-key"}, clear=False):
                loaded = load_llm_config(tmp_dir)

            self.assertTrue(loaded["has_api_key"])
            self.assertEqual(loaded["api_key"], "env-secret-key")
            self.assertEqual(loaded["api_key_source"], "environment")
            self.assertEqual(loaded["base_url"], DEFAULT_OPENAI_BASE_URL)
            self.assertEqual(loaded["model"], DEFAULT_OPENAI_MODEL)

    def test_save_llm_config_allows_missing_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            saved = save_llm_config(
                base_url="https://example.com/v1",
                model="gpt-4o-mini",
                api_key="",
                system_prompt="",
                base_dir=tmp_dir,
            )

            self.assertFalse(saved["configured"])
            self.assertEqual(saved["base_url"], "https://example.com/v1")
            self.assertEqual(saved["model"], "gpt-4o-mini")

    def test_save_llm_config_reuses_defaults_when_fields_blank(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"OPENAI_API_KEY": "env-secret-key"}, clear=False):
                saved = save_llm_config(
                    base_url="",
                    model="",
                    api_key="",
                    system_prompt="",
                    base_dir=tmp_dir,
                )

            self.assertEqual(saved["base_url"], DEFAULT_OPENAI_BASE_URL)
            self.assertEqual(saved["model"], DEFAULT_OPENAI_MODEL)


if __name__ == "__main__":
    unittest.main()
