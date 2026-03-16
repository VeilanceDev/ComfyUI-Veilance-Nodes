"""
Combined model loader nodes for ComfyUI.
Wrap built-in Diffusion Model, CLIP, and VAE loaders into single convenience nodes.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from ..comfy_reflection import (
    build_required_kwargs,
    ensure_legacy_node_alias,
    extract_default_value,
    find_first_input,
    get_required_inputs,
    resolve_node_class,
    run_node,
    try_resolve_node_class,
)


def _fallback_clip_device_input_spec():
    return (
        ["default", "cpu", "cuda", "mps"],
        {"default": "default"},
    )


class _BaseModelLoaderTrio:
    _DIFFUSION_MODEL_KEYS = ("unet_name", "model_name", "diffusion_model", "ckpt_name")
    _DIFFUSION_DTYPE_KEYS = ("weight_dtype", "dtype")
    _CLIP_MODEL_KEYS = ("clip_name", "model_name", "text_encoder")
    _CLIP_TYPE_KEYS = ("type", "clip_type", "model_type")
    _CLIP_DEVICE_KEYS = ("device", "load_device")
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
    def _resolve_config(cls) -> Dict[str, Dict[str, Any]]:
        diffusion_class = resolve_node_class(
            "Load Diffusion Model",
            ("UNETLoader", "DiffusionModelLoader"),
        )
        clip_class = resolve_node_class(
            "Load CLIP",
            ("CLIPLoader",),
        )
        vae_class = resolve_node_class(
            "Load VAE",
            ("VAELoader",),
        )

        diffusion_required = get_required_inputs(diffusion_class)
        clip_required = get_required_inputs(clip_class)
        vae_required = get_required_inputs(vae_class)

        diffusion_model_key, diffusion_model_input = find_first_input(
            diffusion_required, cls._DIFFUSION_MODEL_KEYS
        )
        if diffusion_model_key is None:
            raise RuntimeError(
                "Could not resolve the diffusion model input key from "
                f"{list(diffusion_required.keys())}."
            )

        diffusion_dtype_key, diffusion_dtype_input = find_first_input(
            diffusion_required, cls._DIFFUSION_DTYPE_KEYS
        )

        clip_model_key, clip_model_input = find_first_input(
            clip_required, cls._CLIP_MODEL_KEYS
        )
        if clip_model_key is None:
            raise RuntimeError(
                "Could not resolve the CLIP model input key from "
                f"{list(clip_required.keys())}."
            )

        clip_type_key, clip_type_input = find_first_input(
            clip_required, cls._CLIP_TYPE_KEYS
        )
        clip_device_key, clip_device_input = find_first_input(
            clip_required, cls._CLIP_DEVICE_KEYS
        )
        if clip_device_input is None:
            clip_device_input = _fallback_clip_device_input_spec()

        vae_model_key, vae_model_input = find_first_input(
            vae_required, cls._VAE_MODEL_KEYS
        )
        if vae_model_key is None:
            raise RuntimeError(
                "Could not resolve the VAE model input key from "
                f"{list(vae_required.keys())}."
            )

        return {
            "diffusion": {
                "class": diffusion_class,
                "required": diffusion_required,
                "model_key": diffusion_model_key,
                "model_input": diffusion_model_input,
                "dtype_key": diffusion_dtype_key,
                "dtype_input": diffusion_dtype_input,
            },
            "clip": {
                "class": clip_class,
                "required": clip_required,
                "model_key": clip_model_key,
                "model_input": clip_model_input,
                "type_key": clip_type_key,
                "type_input": clip_type_input,
                "device_key": clip_device_key,
                "device_input": clip_device_input,
            },
            "vae": {
                "class": vae_class,
                "required": vae_required,
                "model_key": vae_model_key,
                "model_input": vae_model_input,
            },
        }

    @classmethod
    def _base_required_inputs(cls) -> Dict[str, Any]:
        config = cls._resolve_config()
        required: Dict[str, Any] = {}
        required["diffusion_model"] = config["diffusion"]["model_input"]
        if config["diffusion"]["dtype_input"] is not None:
            required["diffusion_weight_dtype"] = config["diffusion"]["dtype_input"]
        required["clip_model"] = config["clip"]["model_input"]
        if config["clip"]["type_input"] is not None:
            required["clip_type"] = config["clip"]["type_input"]
        required["clip_device"] = config["clip"]["device_input"]
        required["vae_model"] = config["vae"]["model_input"]
        return required

    @classmethod
    def _load_trio(
        cls,
        diffusion_model,
        clip_model,
        vae_model,
        diffusion_weight_dtype=None,
        clip_type=None,
        clip_device=None,
    ):
        config = cls._resolve_config()

        diffusion_explicit = {
            config["diffusion"]["model_key"]: diffusion_model,
        }
        if config["diffusion"]["dtype_key"] is not None:
            selected_dtype = diffusion_weight_dtype
            if selected_dtype is None:
                selected_dtype = extract_default_value(config["diffusion"]["dtype_input"])
            diffusion_explicit[config["diffusion"]["dtype_key"]] = selected_dtype

        clip_explicit = {
            config["clip"]["model_key"]: clip_model,
        }
        if config["clip"]["type_key"] is not None:
            selected_type = clip_type
            if selected_type is None:
                selected_type = extract_default_value(config["clip"]["type_input"])
            clip_explicit[config["clip"]["type_key"]] = selected_type
        if config["clip"]["device_key"] is not None:
            selected_device = clip_device
            if selected_device is None:
                selected_device = extract_default_value(config["clip"]["device_input"])
            clip_explicit[config["clip"]["device_key"]] = selected_device

        vae_explicit = {
            config["vae"]["model_key"]: vae_model,
        }

        diffusion_kwargs = build_required_kwargs(
            config["diffusion"]["required"], diffusion_explicit
        )
        clip_kwargs = build_required_kwargs(config["clip"]["required"], clip_explicit)
        vae_kwargs = build_required_kwargs(config["vae"]["required"], vae_explicit)

        model = run_node(config["diffusion"]["class"], diffusion_kwargs)[0]
        clip = run_node(config["clip"]["class"], clip_kwargs)[0]
        vae = run_node(config["vae"]["class"], vae_kwargs)[0]
        return (model, clip, vae)

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

    @staticmethod
    def _pipe_tail(pipe: Any, replaced_items: int) -> Tuple[Any, ...]:
        if isinstance(pipe, tuple):
            return pipe[replaced_items:]
        if isinstance(pipe, list):
            return tuple(pipe[replaced_items:])
        return ()


class ModelLoaderTrio(_BaseModelLoaderTrio):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": cls._base_required_inputs(),
            "optional": {
                "pipe": ("PIPE",),
            },
        }

    RETURN_TYPES = ("PIPE", "MODEL", "CLIP", "VAE")
    RETURN_NAMES = ("pipe", "model", "clip", "vae")
    FUNCTION = "load_models"
    CATEGORY = "Veilance/Loaders"

    def load_models(
        self,
        diffusion_model,
        clip_model,
        vae_model,
        diffusion_weight_dtype=None,
        clip_type=None,
        clip_device=None,
        pipe=None,
    ):
        model, clip, vae = self._load_trio(
            diffusion_model=diffusion_model,
            clip_model=clip_model,
            vae_model=vae_model,
            diffusion_weight_dtype=diffusion_weight_dtype,
            clip_type=clip_type,
            clip_device=clip_device,
        )
        pipe_out = (model, clip, vae, *self._pipe_tail(pipe, 3))
        return (pipe_out, model, clip, vae)


class ModelLoaderTrioWithParams(_BaseModelLoaderTrio):
    @classmethod
    def INPUT_TYPES(cls):
        required = cls._base_required_inputs()
        required["width"] = ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8})
        required["height"] = ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8})
        required["positive_prompt"] = ("STRING", {"default": "", "multiline": True})
        required["negative_prompt"] = ("STRING", {"default": "", "multiline": True})
        required["clip_skip"] = ("INT", {"default": -1, "min": -24, "max": -1, "step": 1})
        required["a1111_prompt_style"] = ("BOOLEAN", {"default": False})
        required["batch_size"] = ("INT", {"default": 1, "min": 1, "max": 64, "step": 1})
        return {
            "required": required,
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
    CATEGORY = "Veilance/Loaders"

    def load_models_with_params(
        self,
        diffusion_model,
        clip_model,
        vae_model,
        width,
        height,
        positive_prompt,
        negative_prompt,
        clip_skip,
        a1111_prompt_style,
        batch_size,
        diffusion_weight_dtype=None,
        clip_type=None,
        clip_device=None,
        pipe=None,
    ):
        model, clip, vae = self._load_trio(
            diffusion_model=diffusion_model,
            clip_model=clip_model,
            vae_model=vae_model,
            diffusion_weight_dtype=diffusion_weight_dtype,
            clip_type=clip_type,
            clip_device=clip_device,
        )
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
    "ModelLoaderTrio": ModelLoaderTrio,
    "ModelLoaderTrioWithParams": ModelLoaderTrioWithParams,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelLoaderTrio": "Load Model + Clip + VAE",
    "ModelLoaderTrioWithParams": "Load Model + Clip + VAE (Adv.)",
}
