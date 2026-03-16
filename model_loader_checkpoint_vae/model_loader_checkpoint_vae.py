"""
Checkpoint + VAE loader nodes for ComfyUI.
Loads MODEL/CLIP from checkpoint and allows selecting baked VAE or an external VAE file.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from ..comfy_reflection import (
    build_required_kwargs,
    ensure_legacy_node_alias,
    find_first_input,
    get_required_inputs,
    resolve_node_class,
    run_node,
    try_resolve_node_class,
)


class _BaseModelLoaderCheckpointVAE:
    _BAKED_OPTION = "(baked)"

    _CHECKPOINT_MODEL_KEYS = ("ckpt_name", "checkpoint", "model_name")
    _VAE_MODEL_KEYS = ("vae_name", "model_name")
    _TEXT_CONDITIONING_CLIP_KEYS = ("clip",)
    _TEXT_CONDITIONING_TEXT_KEYS = ("text", "prompt")
    _A1111_TEXT_G_KEYS = ("text_g",)
    _A1111_TEXT_L_KEYS = ("text_l",)
    _A1111_PARSER_KEYS = ("parser",)
    _A1111_WITH_SDXL_KEYS = ("with_SDXL", "with_sdxl")
    _A1111_WIDTH_KEYS = ("width",)
    _A1111_HEIGHT_KEYS = ("height",)
    _A1111_TARGET_WIDTH_KEYS = ("target_width",)
    _A1111_TARGET_HEIGHT_KEYS = ("target_height",)
    _A1111_CROP_W_KEYS = ("crop_w",)
    _A1111_CROP_H_KEYS = ("crop_h",)
    _CLIP_SET_LAST_LAYER_CLIP_KEYS = ("clip",)
    _CLIP_SET_LAST_LAYER_LAYER_KEYS = ("stop_at_clip_layer", "last_layer", "clip_skip")
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
    def _resolve_a1111_text_conditioning_config(cls) -> Dict[str, Any] | None:
        cls._ensure_smz_sdxl_compatibility()
        text_conditioning_class = try_resolve_node_class(
            "CLIP Text Encode++",
            ("smZ CLIPTextEncode", "smZ_CLIPTextEncode"),
        )
        if text_conditioning_class is None:
            return None

        required_inputs = get_required_inputs(text_conditioning_class)

        clip_key, _ = find_first_input(required_inputs, cls._TEXT_CONDITIONING_CLIP_KEYS)
        text_key, _ = find_first_input(required_inputs, cls._TEXT_CONDITIONING_TEXT_KEYS)
        if clip_key is None or text_key is None:
            raise RuntimeError(
                "Could not resolve the required CLIP/text inputs for "
                "CLIP Text Encode++."
            )

        def _optional_key(candidates):
            key, _ = find_first_input(required_inputs, candidates)
            return key

        return {
            "class": text_conditioning_class,
            "required": required_inputs,
            "clip_key": clip_key,
            "text_key": text_key,
            "text_g_key": _optional_key(cls._A1111_TEXT_G_KEYS),
            "text_l_key": _optional_key(cls._A1111_TEXT_L_KEYS),
            "parser_key": _optional_key(cls._A1111_PARSER_KEYS),
            "with_sdxl_key": _optional_key(cls._A1111_WITH_SDXL_KEYS),
            "width_key": _optional_key(cls._A1111_WIDTH_KEYS),
            "height_key": _optional_key(cls._A1111_HEIGHT_KEYS),
            "target_width_key": _optional_key(cls._A1111_TARGET_WIDTH_KEYS),
            "target_height_key": _optional_key(cls._A1111_TARGET_HEIGHT_KEYS),
            "crop_w_key": _optional_key(cls._A1111_CROP_W_KEYS),
            "crop_h_key": _optional_key(cls._A1111_CROP_H_KEYS),
        }

    @classmethod
    def _ensure_smz_sdxl_compatibility(cls):
        try:
            from comfy_extras.nodes_clip_sdxl import (  # type: ignore
                CLIPTextEncodeSDXL,
                CLIPTextEncodeSDXLRefiner,
            )
        except Exception:
            return

        ensure_legacy_node_alias(CLIPTextEncodeSDXL, "encode")
        ensure_legacy_node_alias(CLIPTextEncodeSDXLRefiner, "encode")

    @classmethod
    def _resolve_clip_skip_config(cls) -> Dict[str, Any]:
        clip_skip_class = resolve_node_class(
            "CLIP Set Last Layer",
            ("CLIPSetLastLayer",),
        )
        required_inputs = get_required_inputs(clip_skip_class)
        clip_key, _ = find_first_input(
            required_inputs,
            cls._CLIP_SET_LAST_LAYER_CLIP_KEYS,
        )
        layer_key, _ = find_first_input(
            required_inputs,
            cls._CLIP_SET_LAST_LAYER_LAYER_KEYS,
        )
        if clip_key is None or layer_key is None:
            raise RuntimeError(
                "Could not resolve the required inputs for CLIP Set Last Layer."
            )

        return {
            "class": clip_skip_class,
            "required": required_inputs,
            "clip_key": clip_key,
            "layer_key": layer_key,
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
    def _apply_clip_skip(cls, clip, clip_skip: int):
        if int(clip_skip) == -1:
            return clip

        config = cls._resolve_clip_skip_config()
        kwargs = build_required_kwargs(
            config["required"],
            {
                config["clip_key"]: clip,
                config["layer_key"]: int(clip_skip),
            },
        )
        return run_node(config["class"], kwargs)[0]

    @classmethod
    def _encode_text_conditioning(
        cls,
        clip,
        prompt: str,
        width: int,
        height: int,
        a1111_prompt_style: bool = False,
    ):
        if a1111_prompt_style:
            config = cls._resolve_a1111_text_conditioning_config()
            if config is None:
                raise RuntimeError(
                    "A1111 prompt style requires ComfyUI_smZNodes "
                    "(CLIP Text Encode++)."
                )

            explicit_values = {
                config["clip_key"]: clip,
                config["text_key"]: str(prompt),
            }
            if config["text_g_key"] is not None:
                explicit_values[config["text_g_key"]] = str(prompt)
            if config["text_l_key"] is not None:
                explicit_values[config["text_l_key"]] = str(prompt)
            if config["parser_key"] is not None:
                explicit_values[config["parser_key"]] = "A1111"
            if config["with_sdxl_key"] is not None:
                explicit_values[config["with_sdxl_key"]] = True
            if config["width_key"] is not None:
                explicit_values[config["width_key"]] = int(width)
            if config["height_key"] is not None:
                explicit_values[config["height_key"]] = int(height)
            if config["target_width_key"] is not None:
                explicit_values[config["target_width_key"]] = int(width)
            if config["target_height_key"] is not None:
                explicit_values[config["target_height_key"]] = int(height)
            if config["crop_w_key"] is not None:
                explicit_values[config["crop_w_key"]] = 0
            if config["crop_h_key"] is not None:
                explicit_values[config["crop_h_key"]] = 0

            kwargs = build_required_kwargs(config["required"], explicit_values)
            return run_node(config["class"], kwargs)[0]

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
                "clip_skip": ("INT", {"default": -1, "min": -24, "max": -1, "step": 1}),
                "a1111_prompt_style": ("BOOLEAN", {"default": False}),
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
        clip_skip,
        a1111_prompt_style,
        batch_size,
        pipe=None,
    ):
        model, clip, vae = self._load_checkpoint_vae_pair(checkpoint_model, vae_model)
        clip = self._apply_clip_skip(clip, clip_skip)
        positive_conditioning = self._encode_text_conditioning(
            clip,
            positive_prompt,
            width,
            height,
            a1111_prompt_style=a1111_prompt_style,
        )
        negative_conditioning = self._encode_text_conditioning(
            clip,
            negative_prompt,
            width,
            height,
            a1111_prompt_style=a1111_prompt_style,
        )
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
