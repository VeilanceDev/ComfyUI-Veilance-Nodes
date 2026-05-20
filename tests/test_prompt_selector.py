from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.helpers import import_repo_module


cache = import_repo_module("node_packages.prompt_selector.cache")
file_utils = import_repo_module("node_packages.prompt_selector.file_utils")
parsers = import_repo_module("node_packages.prompt_selector.parsers")


class PromptSelectorTests(unittest.TestCase):
    def tearDown(self):
        cache.refresh_cache()

    def test_csv_header_detection_and_favorites(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "prompts.csv"
            path.write_text(
                "name,positive,negative,favorite\n"
                "Hero,bright hero,dark,false\n"
                "Villain,sharp villain,soft,true\n",
                encoding="utf-8",
            )

            prompts = parsers.load_csv_file(path)

        self.assertEqual([entry.display_name for entry in prompts], ["Hero", "Villain"])
        self.assertFalse(prompts[0].is_favorite)
        self.assertTrue(prompts[1].is_favorite)

    def test_category_discovery_skips_examples_and_disambiguates_stems(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            category_dir = root / "characters" / "heroes"
            category_dir.mkdir(parents=True)
            (category_dir / "poses.csv").write_text("Standing,stand,,\n", encoding="utf-8")
            (category_dir / "poses.json").write_text(
                json.dumps([{"name": "Sitting", "positive": "sit"}]),
                encoding="utf-8",
            )
            examples_dir = root / "examples"
            examples_dir.mkdir()
            (examples_dir / "ignored.csv").write_text("Ignored,value,,\n", encoding="utf-8")

            cache.refresh_cache()
            categories = cache.discover_categories(root)
            files = cache.get_category_files("characters/heroes", root)

        self.assertEqual(categories, ["characters/heroes"])
        self.assertEqual(set(files.keys()), {"poses [csv]", "poses [json]"})

    def test_dropdown_options_favorites_duplicates_and_legacy_lookup(self):
        data = {
            "cat": {
                "file": [
                    parsers.PromptEntry("Same", "first", "neg1", False),
                    parsers.PromptEntry("Same", "second", "neg2", True),
                ]
            }
        }
        display_index, option_index, file_options = cache._build_indexes(data)

        cache._category_cache = data
        cache._display_index = display_index
        cache._option_index = option_index
        cache._file_options = file_options
        cache._cache_valid = True

        self.assertEqual(
            cache.get_file_dropdown_options("cat", "file"),
            [
                parsers.DISABLED_OPTION,
                parsers.RANDOM_OPTION,
                "⭐ Same (1)",
                "Same (2)",
            ],
        )
        self.assertEqual(
            cache.get_prompt_from_file("cat", "file", "Same (2)"),
            ("first", "neg1"),
        )
        self.assertEqual(
            cache.get_prompt_from_file("cat", "file", "⭐ Same (1)"),
            ("second", "neg2"),
        )

    def test_file_utils_preserves_compatibility_exports(self):
        self.assertIs(file_utils.PromptEntry, parsers.PromptEntry)
        self.assertIs(file_utils.get_prompt_from_file, cache.get_prompt_from_file)


if __name__ == "__main__":
    unittest.main()
