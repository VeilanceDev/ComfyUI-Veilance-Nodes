from __future__ import annotations

import unittest

from tests.helpers import import_repo_module


source_nodes = import_repo_module("node_packages.workflow_utils.source_filename_nodes")


class SourceFilenameTests(unittest.TestCase):
    def test_traces_checkpoint_loader_output(self):
        node = source_nodes.SourceFilename()
        prompt = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "models/base.safetensors"},
            }
        }

        self.assertEqual(
            node.get_filename(["1", 0], prompt=prompt),
            ("base.safetensors",),
        )

    def test_traces_pipe_builder_component_to_loader(self):
        node = source_nodes.SourceFilename()
        prompt = {
            "1": {
                "class_type": "ModelLoaderTrio",
                "inputs": {
                    "diffusion_model": "unet/foo.safetensors",
                    "clip_model": "clip/bar.safetensors",
                    "vae_model": "vae/baz.safetensors",
                },
            },
            "2": {
                "class_type": "PipeBuilder",
                "inputs": {"pipe": ["1", 0]},
            },
        }

        self.assertEqual(
            node.get_filename(["2", 3], prompt=prompt),
            ("baz.safetensors",),
        )

    def test_baked_vae_falls_back_to_checkpoint_filename(self):
        node = source_nodes.SourceFilename()
        prompt = {
            "1": {
                "class_type": "ModelLoaderCheckpointVAE",
                "inputs": {
                    "checkpoint_model": "checkpoints/model.ckpt",
                    "vae_model": "(baked)",
                },
            },
        }

        self.assertEqual(
            node.get_filename(["1", 3], prompt=prompt),
            ("model.ckpt",),
        )

    def test_unknown_when_source_is_not_link(self):
        node = source_nodes.SourceFilename()

        self.assertEqual(
            node.get_filename("not-a-link", prompt={}),
            (source_nodes.UNKNOWN_FILENAME,),
        )


if __name__ == "__main__":
    unittest.main()
