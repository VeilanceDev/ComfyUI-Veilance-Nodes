"""
Resolution Selector Node for ComfyUI.
Calculates width and height from a pixel budget and aspect ratio.
"""

from __future__ import annotations

import math
from typing import Tuple


class ResolutionSelector:
    """
    Outputs dimensions that keep a target pixel budget near base_resolution^2.
    Supports preset or custom ratios.
    """

    ASPECT_RATIOS = [
        ("1:1", 1, 1),
        ("landscape (5:4)", 5, 4),
        ("landscape (4:3)", 4, 3),
        ("landscape (3:2)", 3, 2),
        ("landscape (16:10)", 16, 10),
        ("landscape (16:9)", 16, 9),
        ("landscape (21:9)", 21, 9),
        ("portrait (4:5)", 4, 5),
        ("portrait (3:4)", 3, 4),
        ("portrait (2:3)", 2, 3),
        ("portrait (9:10)", 9, 10),
        ("portrait (9:16)", 9, 16),
        ("portrait (9:21)", 9, 21),
        ("custom", 1, 1),
    ]

    ALIGNMENT_MULTIPLE = 8
    MIN_DIMENSION = 64
    MAX_DIMENSION = 8192

    @classmethod
    def INPUT_TYPES(cls):
        aspect_ratio_names = [name for name, _, _ in cls.ASPECT_RATIOS]

        return {
            "required": {
                "base_resolution": (
                    "INT",
                    {
                        "default": 1024,
                        "min": 64,
                        "max": 8192,
                        "step": 64,
                        "display": "number",
                    },
                ),
                "aspect_ratio": (aspect_ratio_names, {"default": "1:1"}),
                "custom_ratio_width": (
                    "INT",
                    {"default": 1, "min": 1, "max": 256, "step": 1},
                ),
                "custom_ratio_height": (
                    "INT",
                    {"default": 1, "min": 1, "max": 256, "step": 1},
                ),
            },
        }

    RETURN_TYPES = ("INT", "INT", "FLOAT", "STRING", "INT")
    RETURN_NAMES = (
        "width",
        "height",
        "megapixels",
        "aspect_ratio_actual",
        "pixel_delta",
    )
    FUNCTION = "calculate_resolution"
    CATEGORY = "Veilance/Utils"

    @classmethod
    def _resolve_ratio(
        cls,
        aspect_ratio_name: str,
        custom_ratio_width: int,
        custom_ratio_height: int,
    ) -> Tuple[int, int]:
        if aspect_ratio_name == "custom":
            return max(1, int(custom_ratio_width)), max(1, int(custom_ratio_height))

        for name, width_ratio, height_ratio in cls.ASPECT_RATIOS:
            if name == aspect_ratio_name:
                return width_ratio, height_ratio

        return 1, 1

    @staticmethod
    def _clamp_aligned(value: float, minimum: int, maximum: int, multiple: int) -> int:
        clamped = max(minimum, min(maximum, int(round(value))))

        aligned = int(round(clamped / multiple) * multiple)
        min_aligned = int(math.ceil(minimum / multiple) * multiple)
        max_aligned = int(math.floor(maximum / multiple) * multiple)

        if aligned < min_aligned:
            aligned = min_aligned
        if aligned > max_aligned:
            aligned = max_aligned

        return max(multiple, aligned)

    @staticmethod
    def _format_ratio(width: int, height: int) -> str:
        gcd = math.gcd(width, height)
        if gcd <= 0:
            return "0:0"
        return f"{width // gcd}:{height // gcd}"

    @classmethod
    def calculate_dimensions(
        cls,
        base_resolution: int,
        aspect_ratio_name: str,
        custom_ratio_width: int,
        custom_ratio_height: int,
    ) -> Tuple[int, int, float, str, int]:
        width_ratio, height_ratio = cls._resolve_ratio(
            aspect_ratio_name, custom_ratio_width, custom_ratio_height
        )

        target_pixels = int(base_resolution) * int(base_resolution)
        ratio = width_ratio / height_ratio

        width = math.sqrt(target_pixels * ratio)
        height = math.sqrt(target_pixels / ratio)

        width_int = cls._clamp_aligned(
            width, cls.MIN_DIMENSION, cls.MAX_DIMENSION, cls.ALIGNMENT_MULTIPLE
        )
        height_int = cls._clamp_aligned(
            height, cls.MIN_DIMENSION, cls.MAX_DIMENSION, cls.ALIGNMENT_MULTIPLE
        )

        actual_pixels = width_int * height_int
        megapixels = actual_pixels / 1_000_000.0
        pixel_delta = actual_pixels - target_pixels
        aspect_ratio_actual = cls._format_ratio(width_int, height_int)

        return width_int, height_int, megapixels, aspect_ratio_actual, pixel_delta

    def calculate_resolution(
        self,
        base_resolution: int,
        aspect_ratio: str,
        custom_ratio_width: int,
        custom_ratio_height: int,
    ):
        return self.calculate_dimensions(
            base_resolution,
            aspect_ratio,
            custom_ratio_width,
            custom_ratio_height,
        )


NODE_CLASS_MAPPINGS = {
    "ResolutionSelector": ResolutionSelector,
    "VeilanceResolutionSelector": ResolutionSelector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ResolutionSelector": "Resolution Selector",
    "VeilanceResolutionSelector": "Resolution Selector (Veilance)",
}
