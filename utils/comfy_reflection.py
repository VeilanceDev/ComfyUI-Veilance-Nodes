"""
Shared ComfyUI reflection helpers used by compatibility wrapper nodes.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple


KSAMPLER_INPUT_CANDIDATES = {
    "model": ("model",),
    "positive": ("positive",),
    "negative": ("negative",),
    "latent": ("latent_image", "latent", "samples"),
    "seed": ("seed", "noise_seed"),
    "steps": ("steps",),
    "cfg": ("cfg",),
    "sampler": ("sampler_name",),
    "scheduler": ("scheduler",),
    "denoise": ("denoise",),
}

VAE_ENCODE_INPUT_CANDIDATES = {
    "image": ("pixels", "image"),
    "vae": ("vae",),
}

VAE_DECODE_INPUT_CANDIDATES = {
    "samples": ("samples", "latent", "latent_image"),
    "vae": ("vae",),
}

TEXT_CONDITIONING_INPUT_CANDIDATES = {
    "clip": ("clip",),
    "text": ("text", "prompt"),
}

A1111_TEXT_CONDITIONING_OPTIONAL_CANDIDATES = {
    "text_g": ("text_g",),
    "text_l": ("text_l",),
    "parser": ("parser",),
    "with_sdxl": ("with_SDXL", "with_sdxl"),
    "width": ("width",),
    "height": ("height",),
    "target_width": ("target_width",),
    "target_height": ("target_height",),
    "crop_w": ("crop_w",),
    "crop_h": ("crop_h",),
}

CLIP_SET_LAST_LAYER_INPUT_CANDIDATES = {
    "clip": ("clip",),
    "layer": ("stop_at_clip_layer", "last_layer", "clip_skip"),
}

EMPTY_LATENT_INPUT_CANDIDATES = {
    "width": ("width",),
    "height": ("height",),
    "batch": ("batch_size", "batch"),
}


def resolve_node_class(display_name: str, fallback_class_names: Iterable[str]):
    import nodes  # type: ignore

    for class_name in fallback_class_names:
        node_class = nodes.NODE_CLASS_MAPPINGS.get(class_name)
        if node_class is not None:
            return node_class

    for class_name, mapped_display_name in nodes.NODE_DISPLAY_NAME_MAPPINGS.items():
        if mapped_display_name == display_name:
            node_class = nodes.NODE_CLASS_MAPPINGS.get(class_name)
            if node_class is not None:
                return node_class

    raise RuntimeError(
        f"Could not find ComfyUI node for '{display_name}'. "
        f"Checked fallback class names: {list(fallback_class_names)}."
    )


def try_resolve_node_class(display_name: str, fallback_class_names: Iterable[str]):
    try:
        return resolve_node_class(display_name, fallback_class_names)
    except RuntimeError:
        return None


def ensure_legacy_node_alias(node_class, alias_name: str = "encode") -> bool:
    if hasattr(node_class, alias_name):
        return False

    function_name = getattr(node_class, "FUNCTION", None)
    if function_name and function_name in getattr(node_class, "__dict__", {}):
        setattr(node_class, alias_name, node_class.__dict__[function_name])
        return True

    if "execute" in getattr(node_class, "__dict__", {}):
        setattr(node_class, alias_name, node_class.__dict__["execute"])
        return True

    return False


def get_required_inputs(node_class) -> Dict[str, Any]:
    input_types = node_class.INPUT_TYPES()
    required_inputs = input_types.get("required", {})
    if not isinstance(required_inputs, dict):
        return {}
    return required_inputs


def extract_default_value(input_spec: Any) -> Any:
    if isinstance(input_spec, tuple) and len(input_spec) > 1:
        config = input_spec[1]
        if isinstance(config, dict):
            return config.get("default")
    return None


def input_with_default(input_spec: Any, default_value: Any) -> Any:
    if not isinstance(input_spec, tuple):
        return input_spec

    parts = list(input_spec)
    metadata: Dict[str, Any] = {}
    if len(parts) > 1 and isinstance(parts[1], dict):
        metadata = dict(parts[1])
        parts[1] = metadata
    else:
        parts.append(metadata)

    metadata["default"] = default_value
    return tuple(parts)


def seed_input_with_control(seed_input_spec: Any) -> Any:
    if isinstance(seed_input_spec, tuple) and len(seed_input_spec) > 1:
        metadata = seed_input_spec[1]
        if isinstance(metadata, dict):
            updated_metadata = dict(metadata)
            updated_metadata["control_after_generate"] = True
            return (seed_input_spec[0], updated_metadata)
    return seed_input_spec


def find_first_input(
    required_inputs: Dict[str, Any],
    candidates: Iterable[str],
) -> Tuple[Optional[str], Any]:
    for name in candidates:
        if name in required_inputs:
            return name, required_inputs[name]
    return None, None


def build_required_kwargs(
    required_inputs: Dict[str, Any],
    explicit_values: Dict[str, Any],
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}
    for input_name, input_spec in required_inputs.items():
        if input_name in explicit_values and explicit_values[input_name] is not None:
            kwargs[input_name] = explicit_values[input_name]
            continue

        default_value = extract_default_value(input_spec)
        if default_value is not None:
            kwargs[input_name] = default_value
            continue

        raise RuntimeError(
            f"Required node input '{input_name}' has no explicit value and no default."
        )
    return kwargs


def resolve_required_input_config(
    *,
    display_name: str,
    fallback_class_names: Iterable[str],
    required_candidates: Dict[str, Iterable[str]],
) -> Dict[str, Any]:
    node_class = resolve_node_class(display_name, fallback_class_names)
    required_inputs = get_required_inputs(node_class)

    config: Dict[str, Any] = {
        "class": node_class,
        "required": required_inputs,
    }
    missing: List[str] = []
    for logical_name, candidates in required_candidates.items():
        input_key, input_spec = find_first_input(required_inputs, candidates)
        if input_key is None:
            missing.append(logical_name)
        config[f"{logical_name}_key"] = input_key
        config[f"{logical_name}_input"] = input_spec

    if missing:
        raise RuntimeError(
            f"Could not resolve {display_name} required input keys for: "
            + ", ".join(missing)
            + f". Available keys: {list(required_inputs.keys())}."
        )

    return config


def resolve_ksampler_config() -> Dict[str, Any]:
    return resolve_required_input_config(
        display_name="KSampler",
        fallback_class_names=("KSampler",),
        required_candidates=KSAMPLER_INPUT_CANDIDATES,
    )


def run_node(node_class, kwargs: Dict[str, Any]) -> Tuple[Any, ...]:
    node = node_class()
    function_name = getattr(node_class, "FUNCTION", None) or getattr(
        node, "FUNCTION", None
    )
    if not function_name:
        raise RuntimeError(f"Node class '{node_class.__name__}' has no FUNCTION.")

    node_fn = getattr(node, function_name)
    result = node_fn(**kwargs)

    node_result = getattr(result, "result", None)
    if hasattr(result, "args") and node_result is not None:
        if isinstance(node_result, tuple):
            return node_result
        if isinstance(node_result, list):
            return tuple(node_result)
        return (node_result,)
    if isinstance(result, tuple):
        return result
    if isinstance(result, list):
        return tuple(result)
    return (result,)


def encode_image_to_latent(image: Any, vae: Any) -> Any:
    config = resolve_required_input_config(
        display_name="VAE Encode",
        fallback_class_names=("VAEEncode",),
        required_candidates=VAE_ENCODE_INPUT_CANDIDATES,
    )
    kwargs = build_required_kwargs(
        config["required"],
        {
            config["image_key"]: image,
            config["vae_key"]: vae,
        },
    )
    return run_node(config["class"], kwargs)[0]


def decode_latent_to_image(latent: Any, vae: Any) -> Any:
    config = resolve_required_input_config(
        display_name="VAE Decode",
        fallback_class_names=("VAEDecode",),
        required_candidates=VAE_DECODE_INPUT_CANDIDATES,
    )
    kwargs = build_required_kwargs(
        config["required"],
        {
            config["samples_key"]: latent,
            config["vae_key"]: vae,
        },
    )
    return run_node(config["class"], kwargs)[0]


def run_ksampler(
    *,
    model: Any,
    positive: Any,
    negative: Any,
    latent: Any,
    seed: int,
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    denoise: float,
) -> Any:
    config = resolve_ksampler_config()
    kwargs = build_required_kwargs(
        config["required"],
        {
            config["model_key"]: model,
            config["positive_key"]: positive,
            config["negative_key"]: negative,
            config["latent_key"]: latent,
            config["seed_key"]: int(seed),
            config["steps_key"]: int(steps),
            config["cfg_key"]: float(cfg),
            config["sampler_key"]: sampler_name,
            config["scheduler_key"]: scheduler,
            config["denoise_key"]: float(denoise),
        },
    )
    return run_node(config["class"], kwargs)[0]


def preview_image(image: Any, prompt: Any = None, extra_pnginfo: Any = None) -> None:
    try:
        preview_class = resolve_node_class("Preview Image", ("PreviewImage",))
    except RuntimeError:
        return

    required_inputs = get_required_inputs(preview_class)
    images_key, _ = find_first_input(required_inputs, ("images", "image"))
    if images_key is None:
        return

    try:
        kwargs = build_required_kwargs(required_inputs, {images_key: image})
    except RuntimeError:
        return

    preview_node = preview_class()
    function_name = getattr(preview_class, "FUNCTION", None) or getattr(
        preview_node, "FUNCTION", None
    )
    if not function_name:
        return

    preview_fn = getattr(preview_node, function_name)
    try:
        preview_fn(**kwargs, prompt=prompt, extra_pnginfo=extra_pnginfo)
    except TypeError:
        try:
            preview_fn(**kwargs)
        except Exception:
            return


def ensure_smz_sdxl_compatibility() -> None:
    try:
        from comfy_extras.nodes_clip_sdxl import (  # type: ignore
            CLIPTextEncodeSDXL,
            CLIPTextEncodeSDXLRefiner,
        )
    except Exception:
        return

    ensure_legacy_node_alias(CLIPTextEncodeSDXL, "encode")
    ensure_legacy_node_alias(CLIPTextEncodeSDXLRefiner, "encode")


def resolve_text_conditioning_config() -> Dict[str, Any]:
    return resolve_required_input_config(
        display_name="CLIP Text Encode",
        fallback_class_names=("CLIPTextEncode",),
        required_candidates=TEXT_CONDITIONING_INPUT_CANDIDATES,
    )


def resolve_a1111_text_conditioning_config() -> Dict[str, Any] | None:
    ensure_smz_sdxl_compatibility()
    text_conditioning_class = try_resolve_node_class(
        "CLIP Text Encode++",
        ("smZ CLIPTextEncode", "smZ_CLIPTextEncode"),
    )
    if text_conditioning_class is None:
        return None

    required_inputs = get_required_inputs(text_conditioning_class)
    clip_key, _ = find_first_input(
        required_inputs,
        TEXT_CONDITIONING_INPUT_CANDIDATES["clip"],
    )
    text_key, _ = find_first_input(
        required_inputs,
        TEXT_CONDITIONING_INPUT_CANDIDATES["text"],
    )
    if clip_key is None or text_key is None:
        raise RuntimeError(
            "Could not resolve the required CLIP/text inputs for CLIP Text Encode++."
        )

    config: Dict[str, Any] = {
        "class": text_conditioning_class,
        "required": required_inputs,
        "clip_key": clip_key,
        "text_key": text_key,
    }
    for logical_name, candidates in A1111_TEXT_CONDITIONING_OPTIONAL_CANDIDATES.items():
        optional_key, _ = find_first_input(required_inputs, candidates)
        config[f"{logical_name}_key"] = optional_key
    return config


def apply_clip_skip(clip: Any, clip_skip: int) -> Any:
    if int(clip_skip) == -1:
        return clip

    config = resolve_required_input_config(
        display_name="CLIP Set Last Layer",
        fallback_class_names=("CLIPSetLastLayer",),
        required_candidates=CLIP_SET_LAST_LAYER_INPUT_CANDIDATES,
    )
    kwargs = build_required_kwargs(
        config["required"],
        {
            config["clip_key"]: clip,
            config["layer_key"]: int(clip_skip),
        },
    )
    return run_node(config["class"], kwargs)[0]


def encode_text_conditioning(
    *,
    clip: Any,
    prompt: str,
    width: int,
    height: int,
    a1111_prompt_style: bool = False,
) -> Any:
    if a1111_prompt_style:
        config = resolve_a1111_text_conditioning_config()
        if config is None:
            raise RuntimeError(
                "A1111 prompt style requires ComfyUI_smZNodes "
                "(CLIP Text Encode++)."
            )

        explicit_values = {
            config["clip_key"]: clip,
            config["text_key"]: str(prompt),
        }
        optional_values = {
            "text_g_key": str(prompt),
            "text_l_key": str(prompt),
            "parser_key": "A1111",
            "with_sdxl_key": True,
            "width_key": int(width),
            "height_key": int(height),
            "target_width_key": int(width),
            "target_height_key": int(height),
            "crop_w_key": 0,
            "crop_h_key": 0,
        }
        for key_name, value in optional_values.items():
            if config[key_name] is not None:
                explicit_values[config[key_name]] = value

        kwargs = build_required_kwargs(config["required"], explicit_values)
        return run_node(config["class"], kwargs)[0]

    config = resolve_text_conditioning_config()
    kwargs = build_required_kwargs(
        config["required"],
        {
            config["clip_key"]: clip,
            config["text_key"]: str(prompt),
        },
    )
    return run_node(config["class"], kwargs)[0]


def create_empty_latent(width: int, height: int, batch_size: int) -> Any:
    config = resolve_required_input_config(
        display_name="Empty Latent Image",
        fallback_class_names=("EmptyLatentImage",),
        required_candidates=EMPTY_LATENT_INPUT_CANDIDATES,
    )
    kwargs = build_required_kwargs(
        config["required"],
        {
            config["width_key"]: int(width),
            config["height_key"]: int(height),
            config["batch_key"]: int(batch_size),
        },
    )
    return run_node(config["class"], kwargs)[0]


def extract_options(input_spec: Any) -> List[str]:
    if isinstance(input_spec, tuple) and input_spec:
        values = input_spec[0]
        if isinstance(values, (list, tuple)):
            return [str(value) for value in values]
    return []
