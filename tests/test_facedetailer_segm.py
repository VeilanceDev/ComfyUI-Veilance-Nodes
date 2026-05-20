from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import TestCase, mock

import torch

from tests.helpers import import_repo_module


facedetailer = import_repo_module("node_packages.facedetailer_segm.facedetailer_segm")


class FakeDetector:
    def __init__(self, labels):
        self.labels = labels
        self.calls = []

    def detect(self, image, threshold, dilation, crop_factor, drop_size):
        self.calls.append((image, threshold, dilation, crop_factor, drop_size))
        return ((64, 64), [SimpleNamespace(label=label) for label in self.labels])


class FakeCore:
    @staticmethod
    def segs_to_combined_mask(segs):
        return torch.ones((64, 64), dtype=torch.float32) * len(segs[1])


class FakeDetailerForEach:
    calls = []

    @classmethod
    def do_detail(cls, image, segs, *args, **kwargs):
        cls.calls.append((image, segs, args, kwargs))
        return (image + 0.25, None, [image + 0.5])


def run_detailer(node, **overrides):
    FakeDetailerForEach.calls = []
    image = torch.zeros((1, 64, 64, 3), dtype=torch.float32)
    pipe = (
        "pipe-model",
        "pipe-clip",
        "pipe-vae",
        "pipe-positive",
        "pipe-negative",
        "old-latent",
        123,
        "tail",
    )
    kwargs = {
        "image": image,
        "segm_detector": FakeDetector(["face", "left_eye"]),
        "target_labels": "*",
        "wildcard": "[LAB]",
        "threshold": 0.5,
        "dilation": 10,
        "crop_factor": 3.0,
        "drop_size": 10,
        "guide_size": 512,
        "guide_size_for": True,
        "max_size": 1024,
        "steps": 12,
        "cfg": 6.0,
        "sampler_name": "euler",
        "scheduler": "normal",
        "denoise": 0.45,
        "feather": 5,
        "noise_mask": True,
        "force_inpaint": True,
        "cycle": 1,
        "image_output": "Hide",
        "seed": None,
        "pipe": pipe,
        "model": None,
        "clip": None,
        "vae": None,
        "positive": None,
        "negative": None,
        "detailer_hook": None,
        "scheduler_func_opt": None,
        "inpaint_model": False,
        "noise_mask_feather": 20,
        "tiled_encode": False,
        "tiled_decode": False,
    }
    kwargs.update(overrides)

    with (
        mock.patch.object(node, "_resolve_impact_helpers", return_value=(FakeCore, FakeDetailerForEach)),
        mock.patch.object(node, "_encode_image_to_latent", return_value="new-latent"),
        mock.patch.object(node, "_preview_image"),
    ):
        return node.detail(**kwargs)


class FaceDetailerSegmTests(TestCase):
    def test_label_patterns_support_empty_exact_case_insensitive_and_glob(self):
        node = facedetailer.VeilanceSegmFaceDetailer()
        segs = (
            (64, 64),
            [
                SimpleNamespace(label="Face"),
                SimpleNamespace(label="left_eye"),
                SimpleNamespace(label="mouth"),
            ],
        )

        self.assertEqual(node._filter_segs_by_label(segs, "")[1], segs[1])
        self.assertEqual(
            [seg.label for seg in node._filter_segs_by_label(segs, "face")[1]],
            ["Face"],
        )
        self.assertEqual(
            [seg.label for seg in node._filter_segs_by_label(segs, "LEFT_*")[1]],
            ["left_eye"],
        )

    def test_pipe_fallback_replaces_latent_and_preserves_tail(self):
        node = facedetailer.VeilanceSegmFaceDetailer()

        image, pipe, mask, cropped_refined = run_detailer(node)

        self.assertTrue(torch.allclose(image, torch.full((1, 64, 64, 3), 0.25)))
        self.assertEqual(pipe[:7], ("pipe-model", "pipe-clip", "pipe-vae", "pipe-positive", "pipe-negative", "new-latent", 123))
        self.assertEqual(pipe[7:], ("tail",))
        self.assertEqual(mask.shape, (1, 64, 64))
        self.assertEqual(len(cropped_refined), 1)

    def test_target_labels_filter_segs_before_detailing(self):
        node = facedetailer.VeilanceSegmFaceDetailer()

        run_detailer(node, target_labels="left_*")

        detailed_segs = FakeDetailerForEach.calls[0][1]
        self.assertEqual([seg.label for seg in detailed_segs[1]], ["left_eye"])

    def test_no_matching_detections_returns_original_image_zero_mask_and_placeholder_crop(self):
        node = facedetailer.VeilanceSegmFaceDetailer()

        image, pipe, mask, cropped_refined = run_detailer(node, target_labels="hand")

        self.assertTrue(torch.allclose(image, torch.zeros((1, 64, 64, 3))))
        self.assertEqual(pipe[5], "new-latent")
        self.assertTrue(torch.count_nonzero(mask) == 0)
        self.assertEqual(FakeDetailerForEach.calls, [])
        self.assertEqual(len(cropped_refined), 1)

    def test_missing_required_pipe_values_raise_targeted_errors(self):
        node = facedetailer.VeilanceSegmFaceDetailer()
        broken_pipe = (None, "clip", "vae", "positive", "negative", "latent", 1)

        with self.assertRaisesRegex(RuntimeError, "Missing required MODEL"):
            run_detailer(node, pipe=broken_pipe)

        broken_pipe = ("model", "clip", None, "positive", "negative", "latent", 1)
        with self.assertRaisesRegex(RuntimeError, "Missing required VAE"):
            run_detailer(node, pipe=broken_pipe)


if __name__ == "__main__":
    unittest.main()
