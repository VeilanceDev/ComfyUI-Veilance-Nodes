"""
Pipe-aware KSampler node for ComfyUI.
"""

from __future__ import annotations

from typing import Any

from ...utils.comfy_reflection import (
    decode_latent_to_image,
    encode_image_to_latent,
    preview_image,
    resolve_ksampler_config,
    run_ksampler,
    seed_input_with_control,
)
from ...utils.pipe_utils import (
    PIPE_CLIP_INDEX,
    PIPE_LATENT_INDEX,
    PIPE_MODEL_INDEX,
    PIPE_NEGATIVE_INDEX,
    PIPE_POSITIVE_INDEX,
    PIPE_SEED_INDEX,
    PIPE_VAE_INDEX,
    pipe_item,
    pipe_tail,
)


class PipeKSamplerFull:
    _PIPE_MODEL_INDEX = PIPE_MODEL_INDEX
    _PIPE_CLIP_INDEX = PIPE_CLIP_INDEX
    _PIPE_VAE_INDEX = PIPE_VAE_INDEX
    _PIPE_POSITIVE_INDEX = PIPE_POSITIVE_INDEX
    _PIPE_NEGATIVE_INDEX = PIPE_NEGATIVE_INDEX
    _PIPE_LATENT_INDEX = PIPE_LATENT_INDEX
    _PIPE_SEED_INDEX = PIPE_SEED_INDEX

    @classmethod
    def _resolve_ksampler_config(cls) -> dict[str, Any]:
        return resolve_ksampler_config()

    @classmethod
    def INPUT_TYPES(cls):
        ksampler_config = cls._resolve_ksampler_config()
        return {
            "required": {
                "steps": ksampler_config["steps_input"],
                "cfg": ksampler_config["cfg_input"],
                "sampler_name": ksampler_config["sampler_input"],
                "scheduler": ksampler_config["scheduler_input"],
                "denoise": ksampler_config["denoise_input"],
                "image_output": (["Preview", "Hide"], {"default": "Preview"}),
                "seed": seed_input_with_control(ksampler_config["seed_input"]),
            },
            "optional": {
                "pipe": ("PIPE",),
                "model": ("MODEL",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "latent": ("LATENT",),
                "vae": ("VAE",),
                "clip": ("CLIP",),
                "xyPlot": ("XYPLOT",),
                "image": ("IMAGE",),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = (
        "PIPE",
        "IMAGE",
        "MODEL",
        "CONDITIONING",
        "CONDITIONING",
        "LATENT",
        "VAE",
        "CLIP",
        "INT",
    )
    RETURN_NAMES = (
        "pipe",
        "image",
        "model",
        "positive",
        "negative",
        "latent",
        "vae",
        "clip",
        "seed",
    )
    FUNCTION = "sample"
    CATEGORY = "Veilance/Sampling"

    @staticmethod
    def _pipe_item(pipe: Any, index: int) -> Any:
        return pipe_item(pipe, index)

    @staticmethod
    def _pipe_tail(pipe: Any, replaced_items: int) -> tuple[Any, ...]:
        return pipe_tail(pipe, replaced_items)

    @classmethod
    def _encode_image_to_latent(cls, image, vae):
        return encode_image_to_latent(image, vae)

    @classmethod
    def _decode_latent_to_image(cls, latent, vae):
        return decode_latent_to_image(latent, vae)

    @classmethod
    def _run_ksampler(
        cls,
        model,
        positive,
        negative,
        latent,
        seed: int,
        steps: int,
        cfg: float,
        sampler_name: str,
        scheduler: str,
        denoise: float,
    ):
        return run_ksampler(
            model=model,
            positive=positive,
            negative=negative,
            latent=latent,
            seed=int(seed),
            steps=int(steps),
            cfg=float(cfg),
            sampler_name=sampler_name,
            scheduler=scheduler,
            denoise=float(denoise),
        )

    @classmethod
    def _preview_image(cls, image, prompt=None, extra_pnginfo=None):
        preview_image(image, prompt=prompt, extra_pnginfo=extra_pnginfo)

    def sample(
        self,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise,
        image_output,
        seed,
        pipe=None,
        model=None,
        positive=None,
        negative=None,
        latent=None,
        vae=None,
        clip=None,
        xyPlot=None,
        image=None,
        prompt=None,
        extra_pnginfo=None,
    ):
        del xyPlot  # Passthrough compatibility input; not consumed by this node.

        model_value = model if model is not None else self._pipe_item(pipe, self._PIPE_MODEL_INDEX)
        clip_value = clip if clip is not None else self._pipe_item(pipe, self._PIPE_CLIP_INDEX)
        vae_value = vae if vae is not None else self._pipe_item(pipe, self._PIPE_VAE_INDEX)
        positive_value = (
            positive
            if positive is not None
            else self._pipe_item(pipe, self._PIPE_POSITIVE_INDEX)
        )
        negative_value = (
            negative
            if negative is not None
            else self._pipe_item(pipe, self._PIPE_NEGATIVE_INDEX)
        )
        latent_value = latent if latent is not None else self._pipe_item(pipe, self._PIPE_LATENT_INDEX)
        seed_value = int(seed) if seed is not None else self._pipe_item(pipe, self._PIPE_SEED_INDEX)

        if model_value is None:
            raise RuntimeError("Missing required MODEL input. Provide model or a pipe containing model.")
        if positive_value is None:
            raise RuntimeError(
                "Missing required positive CONDITIONING input. Provide positive or pipe[3]."
            )
        if negative_value is None:
            raise RuntimeError(
                "Missing required negative CONDITIONING input. Provide negative or pipe[4]."
            )

        if latent_value is None:
            if image is None:
                raise RuntimeError(
                    "Missing LATENT input. Provide latent, a pipe with latent, or an IMAGE + VAE."
                )
            if vae_value is None:
                raise RuntimeError(
                    "Missing VAE input for IMAGE -> LATENT encode. Provide vae or pipe[2]."
                )
            latent_value = self._encode_image_to_latent(image, vae_value)

        sampled_latent = self._run_ksampler(
            model=model_value,
            positive=positive_value,
            negative=negative_value,
            latent=latent_value,
            seed=int(seed_value),
            steps=int(steps),
            cfg=float(cfg),
            sampler_name=sampler_name,
            scheduler=scheduler,
            denoise=float(denoise),
        )

        if vae_value is None:
            raise RuntimeError("Missing VAE input. Provide vae or pipe[2] to decode sampled latent.")
        image_value = self._decode_latent_to_image(sampled_latent, vae_value)

        if image_output == "Preview":
            self._preview_image(image_value, prompt=prompt, extra_pnginfo=extra_pnginfo)

        pipe_out = (
            model_value,
            clip_value,
            vae_value,
            positive_value,
            negative_value,
            sampled_latent,
            int(seed_value),
            *self._pipe_tail(pipe, 7),
        )

        return (
            pipe_out,
            image_value,
            model_value,
            positive_value,
            negative_value,
            sampled_latent,
            vae_value,
            clip_value,
            int(seed_value),
        )


NODE_CLASS_MAPPINGS = {
    "PipeKSamplerFull": PipeKSamplerFull,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PipeKSamplerFull": "KSampler (Pipe Full)",
}
