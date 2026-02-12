"""
Pipe-aware KSampler node for ComfyUI.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Tuple


def _resolve_node_class(display_name: str, fallback_class_names: Iterable[str]):
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


def _get_required_inputs(node_class) -> Dict[str, Any]:
    input_types = node_class.INPUT_TYPES()
    required_inputs = input_types.get("required", {})
    if not isinstance(required_inputs, dict):
        return {}
    return required_inputs


def _extract_default_value(input_spec: Any) -> Any:
    if isinstance(input_spec, tuple) and len(input_spec) > 1:
        config = input_spec[1]
        if isinstance(config, dict):
            return config.get("default")
    return None


def _find_first_input(
    required_inputs: Dict[str, Any],
    candidates: Iterable[str],
) -> Tuple[Optional[str], Any]:
    for name in candidates:
        if name in required_inputs:
            return name, required_inputs[name]
    return None, None


def _build_node_kwargs(
    required_inputs: Dict[str, Any],
    explicit_values: Dict[str, Any],
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}
    for input_name, input_spec in required_inputs.items():
        if input_name in explicit_values and explicit_values[input_name] is not None:
            kwargs[input_name] = explicit_values[input_name]
            continue

        default_value = _extract_default_value(input_spec)
        if default_value is not None:
            kwargs[input_name] = default_value
            continue

        raise RuntimeError(
            f"Required node input '{input_name}' has no explicit value and no default."
        )
    return kwargs


def _run_node(node_class, kwargs: Dict[str, Any]) -> Tuple[Any, ...]:
    node = node_class()
    function_name = getattr(node_class, "FUNCTION", None) or getattr(
        node, "FUNCTION", None
    )
    if not function_name:
        raise RuntimeError(f"Node class '{node_class.__name__}' has no FUNCTION.")

    node_fn = getattr(node, function_name)
    result = node_fn(**kwargs)

    if isinstance(result, tuple):
        return result
    if isinstance(result, list):
        return tuple(result)
    return (result,)


def _seed_input_with_control(seed_input_spec: Any) -> Any:
    if isinstance(seed_input_spec, tuple) and len(seed_input_spec) > 1:
        metadata = seed_input_spec[1]
        if isinstance(metadata, dict):
            updated_metadata = dict(metadata)
            updated_metadata["control_after_generate"] = True
            return (seed_input_spec[0], updated_metadata)
    return seed_input_spec


class PipeKSamplerFull:
    _PIPE_MODEL_INDEX = 0
    _PIPE_CLIP_INDEX = 1
    _PIPE_VAE_INDEX = 2
    _PIPE_POSITIVE_INDEX = 3
    _PIPE_NEGATIVE_INDEX = 4
    _PIPE_LATENT_INDEX = 5
    _PIPE_SEED_INDEX = 6

    _KSAMPLER_MODEL_KEYS = ("model",)
    _KSAMPLER_POSITIVE_KEYS = ("positive",)
    _KSAMPLER_NEGATIVE_KEYS = ("negative",)
    _KSAMPLER_LATENT_KEYS = ("latent_image", "latent", "samples")
    _KSAMPLER_SEED_KEYS = ("seed", "noise_seed")
    _KSAMPLER_STEPS_KEYS = ("steps",)
    _KSAMPLER_CFG_KEYS = ("cfg",)
    _KSAMPLER_SAMPLER_KEYS = ("sampler_name",)
    _KSAMPLER_SCHEDULER_KEYS = ("scheduler",)
    _KSAMPLER_DENOISE_KEYS = ("denoise",)

    _VAE_ENCODE_IMAGE_KEYS = ("pixels", "image")
    _VAE_ENCODE_VAE_KEYS = ("vae",)
    _VAE_DECODE_SAMPLES_KEYS = ("samples", "latent", "latent_image")
    _VAE_DECODE_VAE_KEYS = ("vae",)

    _PREVIEW_IMAGES_KEYS = ("images", "image")

    @classmethod
    def _resolve_ksampler_config(cls) -> Dict[str, Any]:
        ksampler_class = _resolve_node_class("KSampler", ("KSampler",))
        required_inputs = _get_required_inputs(ksampler_class)

        model_key, model_input = _find_first_input(
            required_inputs, cls._KSAMPLER_MODEL_KEYS
        )
        positive_key, positive_input = _find_first_input(
            required_inputs, cls._KSAMPLER_POSITIVE_KEYS
        )
        negative_key, negative_input = _find_first_input(
            required_inputs, cls._KSAMPLER_NEGATIVE_KEYS
        )
        latent_key, latent_input = _find_first_input(
            required_inputs, cls._KSAMPLER_LATENT_KEYS
        )
        seed_key, seed_input = _find_first_input(required_inputs, cls._KSAMPLER_SEED_KEYS)
        steps_key, steps_input = _find_first_input(
            required_inputs, cls._KSAMPLER_STEPS_KEYS
        )
        cfg_key, cfg_input = _find_first_input(required_inputs, cls._KSAMPLER_CFG_KEYS)
        sampler_key, sampler_input = _find_first_input(
            required_inputs, cls._KSAMPLER_SAMPLER_KEYS
        )
        scheduler_key, scheduler_input = _find_first_input(
            required_inputs, cls._KSAMPLER_SCHEDULER_KEYS
        )
        denoise_key, denoise_input = _find_first_input(
            required_inputs, cls._KSAMPLER_DENOISE_KEYS
        )

        missing = []
        for key_name, resolved in (
            ("model", model_key),
            ("positive", positive_key),
            ("negative", negative_key),
            ("latent", latent_key),
            ("seed", seed_key),
            ("steps", steps_key),
            ("cfg", cfg_key),
            ("sampler_name", sampler_key),
            ("scheduler", scheduler_key),
            ("denoise", denoise_key),
        ):
            if resolved is None:
                missing.append(key_name)
        if missing:
            raise RuntimeError(
                "Could not resolve KSampler required input keys for: "
                + ", ".join(missing)
                + f". Available keys: {list(required_inputs.keys())}."
            )

        return {
            "class": ksampler_class,
            "required": required_inputs,
            "model_key": model_key,
            "positive_key": positive_key,
            "negative_key": negative_key,
            "latent_key": latent_key,
            "seed_key": seed_key,
            "steps_key": steps_key,
            "cfg_key": cfg_key,
            "sampler_key": sampler_key,
            "scheduler_key": scheduler_key,
            "denoise_key": denoise_key,
            "seed_input": seed_input,
            "steps_input": steps_input,
            "cfg_input": cfg_input,
            "sampler_input": sampler_input,
            "scheduler_input": scheduler_input,
            "denoise_input": denoise_input,
            "model_input": model_input,
            "positive_input": positive_input,
            "negative_input": negative_input,
            "latent_input": latent_input,
        }

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
                "seed": _seed_input_with_control(ksampler_config["seed_input"]),
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
    CATEGORY = "sampling"

    @staticmethod
    def _pipe_item(pipe: Any, index: int) -> Any:
        if isinstance(pipe, tuple):
            return pipe[index] if len(pipe) > index else None
        if isinstance(pipe, list):
            return pipe[index] if len(pipe) > index else None
        return None

    @staticmethod
    def _pipe_tail(pipe: Any, replaced_items: int) -> Tuple[Any, ...]:
        if isinstance(pipe, tuple):
            return pipe[replaced_items:]
        if isinstance(pipe, list):
            return tuple(pipe[replaced_items:])
        return ()

    @classmethod
    def _encode_image_to_latent(cls, image, vae):
        vae_encode_class = _resolve_node_class("VAE Encode", ("VAEEncode",))
        required_inputs = _get_required_inputs(vae_encode_class)

        image_key, _ = _find_first_input(required_inputs, cls._VAE_ENCODE_IMAGE_KEYS)
        vae_key, _ = _find_first_input(required_inputs, cls._VAE_ENCODE_VAE_KEYS)
        if image_key is None or vae_key is None:
            raise RuntimeError(
                "Could not resolve required VAE Encode inputs. "
                f"Available keys: {list(required_inputs.keys())}."
            )

        kwargs = _build_node_kwargs(
            required_inputs,
            {
                image_key: image,
                vae_key: vae,
            },
        )
        result = _run_node(vae_encode_class, kwargs)
        return result[0]

    @classmethod
    def _decode_latent_to_image(cls, latent, vae):
        vae_decode_class = _resolve_node_class("VAE Decode", ("VAEDecode",))
        required_inputs = _get_required_inputs(vae_decode_class)

        samples_key, _ = _find_first_input(required_inputs, cls._VAE_DECODE_SAMPLES_KEYS)
        vae_key, _ = _find_first_input(required_inputs, cls._VAE_DECODE_VAE_KEYS)
        if samples_key is None or vae_key is None:
            raise RuntimeError(
                "Could not resolve required VAE Decode inputs. "
                f"Available keys: {list(required_inputs.keys())}."
            )

        kwargs = _build_node_kwargs(
            required_inputs,
            {
                samples_key: latent,
                vae_key: vae,
            },
        )
        result = _run_node(vae_decode_class, kwargs)
        return result[0]

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
        config = cls._resolve_ksampler_config()
        kwargs = _build_node_kwargs(
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
        result = _run_node(config["class"], kwargs)
        return result[0]

    @classmethod
    def _preview_image(cls, image, prompt=None, extra_pnginfo=None):
        try:
            preview_class = _resolve_node_class("Preview Image", ("PreviewImage",))
        except RuntimeError:
            return

        required_inputs = _get_required_inputs(preview_class)
        images_key, _ = _find_first_input(required_inputs, cls._PREVIEW_IMAGES_KEYS)
        if images_key is None:
            return

        try:
            kwargs = _build_node_kwargs(required_inputs, {images_key: image})
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
