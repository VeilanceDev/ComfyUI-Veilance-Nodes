from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.helpers import import_repo_module


alias_store = import_repo_module("node_packages.nano_gpt.alias_store")


class AliasStoreTests(unittest.TestCase):
    def test_normalize_alias_config_sanitizes_key_source(self):
        config = alias_store.normalize_alias_config(
            {
                "api_provider": " Custom ",
                "custom_api_url": " https://example.test/v1 ",
                "model": " model-name ",
                "key_source": "bad",
                "api_key_env": " API_KEY ",
            }
        )

        self.assertEqual(config["api_provider"], "Custom")
        self.assertEqual(config["custom_api_url"], "https://example.test/v1")
        self.assertEqual(config["model"], "model-name")
        self.assertEqual(config["key_source"], "keyring")
        self.assertEqual(config["api_key_env"], "API_KEY")

    def test_save_list_get_delete_alias_uses_local_file(self):
        original_alias_file = alias_store._ALIAS_FILE
        original_legacy_alias_file = alias_store._LEGACY_ALIAS_FILE

        with tempfile.TemporaryDirectory() as tmp_dir:
            alias_store._ALIAS_FILE = Path(tmp_dir) / "aliases.local.json"
            alias_store._LEGACY_ALIAS_FILE = Path(tmp_dir) / "aliases.json"
            try:
                alias_store.save_alias(
                    "Test",
                    {
                        "api_provider": "NanoGPT",
                        "custom_api_url": "",
                        "model": "test-model",
                        "key_source": "none",
                    },
                )

                self.assertTrue(alias_store._ALIAS_FILE.exists())
                aliases = alias_store.list_aliases()
                self.assertEqual(len(aliases), 1)
                self.assertEqual(aliases[0]["name"], "Test")
                self.assertEqual(alias_store.get_alias("Test")["model"], "test-model")
                self.assertTrue(alias_store.delete_alias("Test"))
                self.assertIsNone(alias_store.get_alias("Test"))
            finally:
                alias_store._ALIAS_FILE = original_alias_file
                alias_store._LEGACY_ALIAS_FILE = original_legacy_alias_file


if __name__ == "__main__":
    unittest.main()
