"""
Checkpoint + VAE loader nodes for ComfyUI.
Loads MODEL/CLIP from checkpoint and allows selecting baked VAE or an external VAE file.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from ..comfy_reflection import (
    build_required_kwargs,
    find_first_input,
    get_required_inputs,
    resolve_node_class,
    run_node,
)


class _BaseModelLoaderCheckpointVAE:
    _BAKED_OPTION = "(baked)"

    _CHECKPOINT_MODEL_KEYS = ("ckpt_name", "checkpoint", "model_name")
    _VAE_MODEL_KEYS = ("vae_name", "model_name")
    _TEXT_CONDITIONING_CLIP_KEYS = ("clip",)
    _TEXT_CONDITIONING_TEXT_KEYS = ("text", "prompt")
    _LATENT_WIDTH_KEYS = ("width",)
    _LATENT_HEIGHT_KEYS = ("height",)
    _LATENT_BATCH_KEYS = ("batch_size", "batch")

    @classmethod
    def _resolve_checkpoint_config(cls) -> Dict[str, Any]:
        checkpoint_class = resolve_node_class(
            "Load Checkpoint",
            ("CheckpointLoaderSimple", "CheckpointLoader"),
        )
        required_inputs = get_required_inputs(checkpoint_class)
        model_key, model_input = find_first_input(
            required_inputs, cls._CHECKPOINT_MODEL_KEYS
        )
        if model_key is None:
            raise RuntimeError(
                "Could not resolve the checkpoint model input key from "
                f"{list(required_inputs.keys())}."
            )

        return {
            "class": checkpoint_class,
            "required": required_inputs,
            "model_key": model_key,
            "model_input": model_input,
        }

    @classmethod
    def _resolve_vae_config(cls) -> Dict[str, Any]:
        vae_class = resolve_node_class(
            "Load VAE",
            ("VAELoader",),
        )
        required_inputs = get_required_inputs(vae_class)
        model_key, model_input = find_first_input(required_inputs, cls._VAE_MODEL_KEYS)
        if model_key is None:
            raise RuntimeError(
                "Could not resolve the VAE model input key from "
                f"{list(required_inputs.keys())}."
            )

        return {
            "class": vae_class,
            "required": required_inputs,
            "model_key": model_key,
            "model_input": model_input,
        }

    @classmethod
    def _vae_input_with_baked_option(cls):
        config = cls._resolve_vae_config()
        model_input = config["model_input"]

        if isinstance(model_input, tuple) and model_input:
            options = model_input[0]
            if isinstance(options, (list, tuple)):
                normalized = [cls._BAKED_OPTION]
                for option in options:
                    option_text = str(option)
                    if option_text != cls._BAKED_OPTION:
                        normalized.append(option_text)

                metadata = {}
                if len(model_input) > 1 and isinstance(model_input[1], dict):
                    metadata = dict(model_input[1])
                metadata["default"] = cls._BAKED_OPTION
                return (normalized, metadata)

        return ([cls._BAKED_OPTION], {"default": cls._BAKED_OPTION})

    @classmethod
    def INPUT_TYPES(cls):
        checkpoint_config = cls._resolve_checkpoint_config()
        return {
            "required": {
                "checkpoint_model": checkpoint_config["model_input"],
                "vae_model": cls._vae_input_with_baked_option(),
            },
            "optional": {
                "pipe": ("PIPE",),
            },
        }

    RETURN_TYPES = ("PIPE", "MODEL", "CLIP", "VAE")
    RETURN_NAMES = ("pipe", "model", "clip", "vae")
    CATEGORY = "Veilance/Loaders"

    @staticmethod
    def _pipe_tail(pipe: Any, replaced_items: int) -> Tuple[Any, ...]:
        if isinstance(pipe, tuple):
            return pipe[replaced_items:]
        if isinstance(pipe, list):
            return tuple(pipe[replaced_items:])
        return ()

    @classmethod
    def _load_checkpoint(cls, checkpoint_model):
        checkpoint_config = cls._resolve_checkpoint_config()
        checkpoint_kwargs = build_required_kwargs(
            checkpoint_config["required"],
            {
                checkpoint_config["model_key"]: checkpoint_model,
            },
        )
        checkpoint_outputs = run_node(
            checkpoint_config["class"], checkpoint_kwargs
        )
        if len(checkpoint_outputs) < 3:
            raise RuntimeError(
                "Load Checkpoint returned an unexpected output format; "
                "expected at least (MODEL, CLIP, VAE)."
            )
        return checkpoint_outputs[0], checkpoint_outputs[1], checkpoint_outputs[2]

    @classmethod
    def _load_vae(cls, vae_model):
        vae_config = cls._resolve_vae_config()
        vae_kwargs = build_required_kwargs(
            vae_config["required"],
            {
                vae_config["model_key"]: vae_model,
            },
        )
        vae_outputs = run_node(vae_config["class"], vae_kwargs)
        if not vae_outputs:
            raise RuntimeError("Load VAE returned no outputs.")
        return vae_outputs[0]

    @classmethod
    def _resolve_text_conditioning_config(cls) -> Dict[str, Any]:
        text_conditioning_class = resolve_node_class(
            "CLIP Text Encode",
            ("CLIPTextEncode",),
        )
        required_inputs = get_required_inputs(text_conditioning_class)

        clip_key, _ = find_first_input(required_inputs, cls._TEXT_CONDITIONING_CLIP_KEYS)
        if clip_key is None:
            raise RuntimeError(
                "Could not resolve the CLIP input key for CLIP Text Encode from "
                f"{list(required_inputs.keys())}."
            )

        text_key, _ = find_first_input(required_inputs, cls._TEXT_CONDITIONING_TEXT_KEYS)
        if text_key is None:
            raise RuntimeError(
                "Could not resolve the text input key for CLIP Text Encode from "
                f"{list(required_inputs.keys())}."
            )

        return {
            "class": text_conditioning_class,
            "required": required_inputs,
            "clip_key": clip_key,
            "text_key": text_key,
        }

    @classmethod
    def _resolve_empty_latent_config(cls) -> Dict[str, Any]:
        empty_latent_class = resolve_node_class(
            "Empty Latent Image",
            ("EmptyLatentImage",),
        )
        required_inputs = get_required_inputs(empty_latent_class)

        width_key, _ = find_first_input(required_inputs, cls._LATENT_WIDTH_KEYS)
        if width_key is None:
            raise RuntimeError(
                "Could not resolve the width input key for Empty Latent Image from "
                f"{list(required_inputs.keys())}."
            )

        height_key, _ = find_first_input(required_inputs, cls._LATENT_HEIGHT_KEYS)
        if height_key is None:
            raise RuntimeError(
                "Could not resolve the height input key for Empty Latent Image from "
                f"{list(required_inputs.keys())}."
            )

        batch_key, _ = find_first_input(required_inputs, cls._LATENT_BATCH_KEYS)
        if batch_key is None:
            raise RuntimeError(
                "Could not resolve the batch size input key for Empty Latent Image from "
                f"{list(required_inputs.keys())}."
            )

        return {
            "class": empty_latent_class,
            "required": required_inputs,
            "width_key": width_key,
            "height_key": height_key,
            "batch_key": batch_key,
        }

    @classmethod
    def _encode_text_conditioning(cls, clip, prompt: str):
        config = cls._resolve_text_conditioning_config()
        kwargs = build_required_kwargs(
            config["required"],
            {
                config["clip_key"]: clip,
                config["text_key"]: str(prompt),
            },
        )
        return run_node(config["class"], kwargs)[0]

    @classmethod
    def _create_empty_latent(cls, width: int, height: int, batch_size: int):
        config = cls._resolve_empty_latent_config()
        kwargs = build_required_kwargs(
            config["required"],
            {
                config["width_key"]: int(width),
                config["height_key"]: int(height),
                config["batch_key"]: int(batch_size),
            },
        )
        return run_node(config["class"], kwargs)[0]

    @classmethod
    def _load_checkpoint_vae_pair(cls, checkpoint_model, vae_model):
        model, clip, baked_vae = cls._load_checkpoint(checkpoint_model)

        vae_model_text = (
            cls._BAKED_OPTION if vae_model is None else str(vae_model).strip()
        )
        use_baked_vae = (
            not vae_model_text or vae_model_text == cls._BAKED_OPTION
        )

        vae = baked_vae if use_baked_vae else cls._load_vae(vae_model_text)
        if use_baked_vae and vae is None:
            raise RuntimeError(
                "Selected baked VAE, but checkpoint did not provide one. "
                "Pick an external VAE in 'vae_model'."
            )

        return (model, clip, vae)


class ModelLoaderCheckpointVAE(_BaseModelLoaderCheckpointVAE):
    FUNCTION = "load_models"

    def load_models(self, checkpoint_model, vae_model, pipe=None):
        model, clip, vae = self._load_checkpoint_vae_pair(checkpoint_model, vae_model)
        pipe_out = (model, clip, vae, *self._pipe_tail(pipe, 3))
        return (pipe_out, model, clip, vae)


class ModelLoaderCheckpointVAEWithParams(_BaseModelLoaderCheckpointVAE):
    @classmethod
    def INPUT_TYPES(cls):
        checkpoint_config = cls._resolve_checkpoint_config()
        return {
            "required": {
                "checkpoint_model": checkpoint_config["model_input"],
                "vae_model": cls._vae_input_with_baked_option(),
                "width": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                "height": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                "positive_prompt": ("STRING", {"default": "", "multiline": True}),
                "negative_prompt": ("STRING", {"default": "", "multiline": True}),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 64, "step": 1}),
            },
            "optional": {
                "pipe": ("PIPE",),
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
    )
    RETURN_NAMES = (
        "pipe",
        "model",
        "clip",
        "vae",
        "positive_conditioning",
        "negative_conditioning",
        "latent_image",
    )
    FUNCTION = "load_models_with_params"

    def load_models_with_params(
        self,
        checkpoint_model,
        vae_model,
        width,
        height,
        positive_prompt,
        negative_prompt,
        batch_size,
        pipe=None,
    ):
        model, clip, vae = self._load_checkpoint_vae_pair(checkpoint_model, vae_model)
        positive_conditioning = self._encode_text_conditioning(clip, positive_prompt)
        negative_conditioning = self._encode_text_conditioning(clip, negative_prompt)
        latent_image = self._create_empty_latent(width, height, batch_size)
        pipe_out = (
            model,
            clip,
            vae,
            positive_conditioning,
            negative_conditioning,
            latent_image,
            *self._pipe_tail(pipe, 6),
        )

        return (
            pipe_out,
            model,
            clip,
            vae,
            positive_conditioning,
            negative_conditioning,
            latent_image,
        )


NODE_CLASS_MAPPINGS = {
    "ModelLoaderCheckpointVAE": ModelLoaderCheckpointVAE,
    "ModelLoaderCheckpointVAEWithParams": ModelLoaderCheckpointVAEWithParams,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelLoaderCheckpointVAE": "Load Checkpoint + VAE",
    "ModelLoaderCheckpointVAEWithParams": "Load Checkpoint + VAE (Adv.)",
}
