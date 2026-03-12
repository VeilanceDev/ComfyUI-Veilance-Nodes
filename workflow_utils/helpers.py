from __future__ import annotations

from typing import Any

import torch


def build_switch_input_types() -> dict[str, dict[str, Any]]:
    return {
        "required": {
            "select": ("INT", {"default": 1, "min": 1, "max": 2, "step": 1}),
        },
        "optional": {
            "input_1": ("*",),
            "input_2": ("*",),
        },
    }


def build_inverse_switch_input_types() -> dict[str, dict[str, Any]]:
    return {
        "required": {
            "select": ("INT", {"default": 1, "min": 1, "max": 2, "step": 1}),
        },
        "optional": {
            "input_any": ("*",),
        },
    }


def build_empty_latent(image: Any, batch_size: int) -> dict[str, torch.Tensor]:
    height = image.shape[1]
    width = image.shape[2]
    latent_tensor = torch.zeros(
        [batch_size, 4, height // 8, width // 8],
        device="cpu",
    )
    return {"samples": latent_tensor}
