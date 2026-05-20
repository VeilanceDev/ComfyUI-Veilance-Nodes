"""
Pipe Builder node for ComfyUI.
Builds or merges PIPE payloads and exposes split outputs.
"""

from __future__ import annotations

from typing import Any

from ...utils.pipe_utils import (
    PIPE_CLIP_INDEX,
    PIPE_CORE_LENGTH,
    PIPE_LATENT_INDEX,
    PIPE_MODEL_INDEX,
    PIPE_NEGATIVE_INDEX,
    PIPE_POSITIVE_INDEX,
    PIPE_SEED_INDEX,
    PIPE_VAE_INDEX,
    pipe_item,
    pipe_tail,
)

class PipeBuilder:
    _MODEL_INDEX = PIPE_MODEL_INDEX
    _CLIP_INDEX = PIPE_CLIP_INDEX
    _VAE_INDEX = PIPE_VAE_INDEX
    _POSITIVE_INDEX = PIPE_POSITIVE_INDEX
    _NEGATIVE_INDEX = PIPE_NEGATIVE_INDEX
    _LATENT_INDEX = PIPE_LATENT_INDEX
    _SEED_INDEX = PIPE_SEED_INDEX
    _PIPE_CORE_LENGTH = PIPE_CORE_LENGTH

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "preserve_tail": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "pipe": ("PIPE",),
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "latent": ("LATENT",),
                "seed": (
                    "INT",
                    {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF, "step": 1},
                ),
            },
        }

    RETURN_TYPES = (
        "PIPE",
        "MODEL",
        "CLIP",
        "VAE",
        "CONDITIONING",
        "CONDITIONING",
        "LATENT",
        "INT",
    )
    RETURN_NAMES = (
        "pipe",
        "model",
        "clip",
        "vae",
        "positive",
        "negative",
        "latent",
        "seed",
    )
    FUNCTION = "build_pipe"
    CATEGORY = "Veilance/Pipe"

    @staticmethod
    def _pipe_item(pipe: Any, index: int) -> Any:
        return pipe_item(pipe, index)

    @classmethod
    def _pipe_tail(cls, pipe: Any, preserve_tail: bool) -> tuple[Any, ...]:
        if not preserve_tail:
            return ()
        return pipe_tail(pipe, cls._PIPE_CORE_LENGTH)

    def build_pipe(
        self,
        preserve_tail,
        pipe=None,
        model=None,
        clip=None,
        vae=None,
        positive=None,
        negative=None,
        latent=None,
        seed=None,
    ):
        model_value = (
            model if model is not None else self._pipe_item(pipe, self._MODEL_INDEX)
        )
        clip_value = clip if clip is not None else self._pipe_item(pipe, self._CLIP_INDEX)
        vae_value = vae if vae is not None else self._pipe_item(pipe, self._VAE_INDEX)
        positive_value = (
            positive
            if positive is not None
            else self._pipe_item(pipe, self._POSITIVE_INDEX)
        )
        negative_value = (
            negative
            if negative is not None
            else self._pipe_item(pipe, self._NEGATIVE_INDEX)
        )
        latent_value = (
            latent if latent is not None else self._pipe_item(pipe, self._LATENT_INDEX)
        )

        seed_source = seed if seed is not None else self._pipe_item(pipe, self._SEED_INDEX)
        seed_value = int(seed_source) if seed_source is not None else 0

        pipe_out = (
            model_value,
            clip_value,
            vae_value,
            positive_value,
            negative_value,
            latent_value,
            seed_value,
            *self._pipe_tail(pipe, bool(preserve_tail)),
        )

        return (
            pipe_out,
            model_value,
            clip_value,
            vae_value,
            positive_value,
            negative_value,
            latent_value,
            seed_value,
        )


NODE_CLASS_MAPPINGS = {
    "PipeBuilder": PipeBuilder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PipeBuilder": "Pipe Builder",
}
