from __future__ import annotations

import unittest

from tests.helpers import import_repo_module


save_module = import_repo_module("node_packages.save_image_civitai.save_image_civitai")


class SaveImageCivitaiTests(unittest.TestCase):
    def test_parse_output_path_handles_folder_and_extension(self):
        cls = save_module.SaveImageCivitaiMetadata

        self.assertEqual(
            cls._parse_output_path("CivitAI/", "png").replace("\\", "/"),
            "CivitAI/CivitAI",
        )
        self.assertEqual(
            cls._parse_output_path("folder/name.jpg", "jpg").replace("\\", "/"),
            "folder/name",
        )
        self.assertEqual(cls._parse_output_path("", "webp"), "CivitAI")

    def test_parse_output_path_rejects_absolute_paths(self):
        cls = save_module.SaveImageCivitaiMetadata

        with self.assertRaisesRegex(ValueError, "relative"):
            cls._parse_output_path("C:/outside/file.png", "png")

    def test_sampler_mapping(self):
        cls = save_module.SaveImageCivitaiMetadata

        self.assertEqual(
            cls._map_sampler_name_for_civitai("dpmpp_2m", "karras"),
            "DPM++ 2M Karras",
        )
        self.assertEqual(
            cls._map_sampler_name_for_civitai("custom", "sgm_uniform"),
            "custom_sgm_uniform",
        )


if __name__ == "__main__":
    unittest.main()
