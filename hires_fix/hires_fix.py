"""
Pipe-aware HiRes Fix node for ComfyUI.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

try:
    import folder_paths  # type: ignore
except Exception:
    folder_paths = None

from ..comfy_reflection import (
    build_required_kwargs,
    extract_options,
    find_first_input,
    get_required_inputs,
    resolve_node_class,
    run_node,
)


def _seed_input_with_control(seed_input_spec: Any) -> Any:
    if isinstance(seed_input_spec, tuple) and len(seed_input_spec) > 1:
        metadata = seed_input_spec[1]
        if isinstance(metadata, dict):
            updated_metadata = dict(metadata)
            updated_metadata["control_after_generate"] = True
            return (seed_input_spec[0], updated_metadata)
    return seed_input_spec


class PipeHiResFix:
    _PIPE_MODEL_INDEX = 0
    _PIPE_CLIP_INDEX = 1
    _PIPE_VAE_INDEX = 2
    _PIPE_POSITIVE_INDEX = 3
    _PIPE_NEGATIVE_INDEX = 4
    _PIPE_LATENT_INDEX = 5
    _PIPE_SEED_INDEX = 6

    _NONE_UPSCALE_MODEL = "None"
    _UPSCALE_MODEL_CATEGORIES = ("upscale_models", "esrgan")

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

    _UPSCALE_MODEL_NAME_KEYS = ("model_name", "upscale_model_name", "model")
    _IMAGE_UPSCALE_MODEL_KEYS = ("upscale_model", "model")
    _IMAGE_UPSCALE_IMAGE_KEYS = ("image", "images", "pixels")

    _LATENT_UPSCALE_SAMPLE_KEYS = ("samples", "latent", "latent_image")
    _LATENT_UPSCALE_METHOD_KEYS = ("upscale_method", "method")
    _LATENT_UPSCALE_FACTOR_KEYS = ("upscale_by", "scale_by", "scale")

    _LATENT_UPSCALE_METHOD_FALLBACKS = [
        "bislerp",
        "bicubic",
        "bilinear",
        "nearest-exact",
        "area",
    ]

    @staticmethod
    def _with_default(input_spec: Any, default_value: Any) -> Any:
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

    @classmethod
    def _resolve_ksampler_config(cls) -> Dict[str, Any]:
        ksampler_class = resolve_node_class("KSampler", ("KSampler",))
        required_inputs = get_required_inputs(ksampler_class)

        model_key, model_input = find_first_input(
            required_inputs, cls._KSAMPLER_MODEL_KEYS
        )
        positive_key, positive_input = find_first_input(
            required_inputs, cls._KSAMPLER_POSITIVE_KEYS
        )
        negative_key, negative_input = find_first_input(
            required_inputs, cls._KSAMPLER_NEGATIVE_KEYS
        )
        latent_key, latent_input = find_first_input(
            required_inputs, cls._KSAMPLER_LATENT_KEYS
        )
        seed_key, seed_input = find_first_input(required_inputs, cls._KSAMPLER_SEED_KEYS)
        steps_key, steps_input = find_first_input(
            required_inputs, cls._KSAMPLER_STEPS_KEYS
        )
        cfg_key, cfg_input = find_first_input(required_inputs, cls._KSAMPLER_CFG_KEYS)
        sampler_key, sampler_input = find_first_input(
            required_inputs, cls._KSAMPLER_SAMPLER_KEYS
        )
        scheduler_key, scheduler_input = find_first_input(
            required_inputs, cls._KSAMPLER_SCHEDULER_KEYS
        )
        denoise_key, denoise_input = find_first_input(
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
    def _resolve_upscale_model_loader_config(cls) -> Dict[str, Any]:
        loader_class = resolve_node_class(
            "Load Upscale Model",
            ("UpscaleModelLoader",),
        )
        required_inputs = get_required_inputs(loader_class)
        model_key, model_input = find_first_input(
            required_inputs, cls._UPSCALE_MODEL_NAME_KEYS
        )
        if model_key is None:
            raise RuntimeError(
                "Could not resolve the upscale model input key from "
                f"{list(required_inputs.keys())}."
            )
        return {
            "class": loader_class,
            "required": required_inputs,
            "model_key": model_key,
            "model_input": model_input,
        }

    @classmethod
    def _upscale_model_input_with_none(cls):
        options: List[str] = []
        metadata: Dict[str, Any] = {"default": cls._NONE_UPSCALE_MODEL}

        try:
            config = cls._resolve_upscale_model_loader_config()
        except RuntimeError:
            config = None

        if config is not None:
            model_input = config["model_input"]
            options.extend(extract_options(model_input))
            if isinstance(model_input, tuple) and len(model_input) > 1:
                if isinstance(model_input[1], dict):
                    metadata.update(dict(model_input[1]))

        if folder_paths is not None and hasattr(folder_paths, "get_filename_list"):
            get_filename_list = getattr(folder_paths, "get_filename_list")
            for category in cls._UPSCALE_MODEL_CATEGORIES:
                try:
                    options.extend(get_filename_list(category) or [])
                except Exception:
                    continue

        normalized = [cls._NONE_UPSCALE_MODEL]
        seen = {cls._NONE_UPSCALE_MODEL}
        for option in options:
            option_text = str(option).strip()
            if not option_text or option_text in seen:
                continue
            seen.add(option_text)
            normalized.append(option_text)

        metadata["default"] = cls._NONE_UPSCALE_MODEL
        return (normalized, metadata)

    @classmethod
    def _resolve_image_upscale_with_model_config(cls) -> Dict[str, Any]:
        upscale_class = resolve_node_class(
            "Upscale Image (using Model)",
            ("ImageUpscaleWithModel",),
        )
        required_inputs = get_required_inputs(upscale_class)
        model_key, _ = find_first_input(required_inputs, cls._IMAGE_UPSCALE_MODEL_KEYS)
        image_key, _ = find_first_input(required_inputs, cls._IMAGE_UPSCALE_IMAGE_KEYS)
        if model_key is None or image_key is None:
            raise RuntimeError(
                "Could not resolve required image upscale inputs. "
                f"Available keys: {list(required_inputs.keys())}."
            )
        return {
            "class": upscale_class,
            "required": required_inputs,
            "model_key": model_key,
            "image_key": image_key,
        }

    @classmethod
    def _resolve_latent_upscale_config(cls) -> Dict[str, Any]:
        latent_class = resolve_node_class(
            "Latent Upscale By",
            ("LatentUpscaleBy", "LatentUpscale"),
        )
        required_inputs = get_required_inputs(latent_class)
        samples_key, _ = find_first_input(
            required_inputs, cls._LATENT_UPSCALE_SAMPLE_KEYS
        )
        method_key, method_input = find_first_input(
            required_inputs, cls._LATENT_UPSCALE_METHOD_KEYS
        )
        scale_key, _ = find_first_input(
            required_inputs, cls._LATENT_UPSCALE_FACTOR_KEYS
        )
        if samples_key is None or method_key is None or scale_key is None:
            raise RuntimeError(
                "Could not resolve required latent upscale inputs. "
                f"Available keys: {list(required_inputs.keys())}."
            )
        return {
            "class": latent_class,
            "required": required_inputs,
            "samples_key": samples_key,
            "method_key": method_key,
            "method_input": method_input,
            "scale_key": scale_key,
        }

    @classmethod
    def _latent_upscale_method_input(cls):
        try:
            config = cls._resolve_latent_upscale_config()
            options = extract_options(config["method_input"])
        except RuntimeError:
            options = []

        normalized: List[str] = []
        for option in options or cls._LATENT_UPSCALE_METHOD_FALLBACKS:
            option_text = str(option)
            if option_text not in normalized:
                normalized.append(option_text)

        default = normalized[0] if normalized else "bicubic"
        for candidate in ("bislerp", "bicubic"):
            if candidate in normalized:
                default = candidate
                break
        return (normalized, {"default": default})

    @classmethod
    def INPUT_TYPES(cls):
        ksampler_config = cls._resolve_ksampler_config()
        return {
            "required": {
                "upscale_by": (
                    "FLOAT",
                    {"default": 1.5, "min": 1.0, "max": 8.0, "step": 0.05},
                ),
                "upscale_model": cls._upscale_model_input_with_none(),
                "latent_upscale_method": cls._latent_upscale_method_input(),
                "steps": ksampler_config["steps_input"],
                "cfg": ksampler_config["cfg_input"],
                "sampler_name": ksampler_config["sampler_input"],
                "scheduler": ksampler_config["scheduler_input"],
                "denoise": cls._with_default(ksampler_config["denoise_input"], 0.3),
                "image_output": (["Preview", "Hide"], {"default": "Preview"}),
                "seed": _seed_input_with_control(ksampler_config["seed_input"]),
            },
            "optional": {
                "pipe": ("PIPE",),
                "model": ("MODEL",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "latent": ("LATENT",),
                "image": ("IMAGE",),
                "vae": ("VAE",),
                "clip": ("CLIP",),
                "xyPlot": ("XYPLOT",),
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
        vae_encode_class = resolve_node_class("VAE Encode", ("VAEEncode",))
        required_inputs = get_required_inputs(vae_encode_class)

        image_key, _ = find_first_input(required_inputs, cls._VAE_ENCODE_IMAGE_KEYS)
        vae_key, _ = find_first_input(required_inputs, cls._VAE_ENCODE_VAE_KEYS)
        if image_key is None or vae_key is None:
            raise RuntimeError(
                "Could not resolve required VAE Encode inputs. "
                f"Available keys: {list(required_inputs.keys())}."
            )

        kwargs = build_required_kwargs(
            required_inputs,
            {
                image_key: image,
                vae_key: vae,
            },
        )
        result = run_node(vae_encode_class, kwargs)
        return result[0]

    @classmethod
    def _decode_latent_to_image(cls, latent, vae):
        vae_decode_class = resolve_node_class("VAE Decode", ("VAEDecode",))
        required_inputs = get_required_inputs(vae_decode_class)

        samples_key, _ = find_first_input(required_inputs, cls._VAE_DECODE_SAMPLES_KEYS)
        vae_key, _ = find_first_input(required_inputs, cls._VAE_DECODE_VAE_KEYS)
        if samples_key is None or vae_key is None:
            raise RuntimeError(
                "Could not resolve required VAE Decode inputs. "
                f"Available keys: {list(required_inputs.keys())}."
            )

        kwargs = build_required_kwargs(
            required_inputs,
            {
                samples_key: latent,
                vae_key: vae,
            },
        )
        result = run_node(vae_decode_class, kwargs)
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
        result = run_node(config["class"], kwargs)
        return result[0]

    @classmethod
    def _preview_image(cls, image, prompt=None, extra_pnginfo=None):
        try:
            preview_class = resolve_node_class("Preview Image", ("PreviewImage",))
        except RuntimeError:
            return

        required_inputs = get_required_inputs(preview_class)
        images_key, _ = find_first_input(required_inputs, cls._PREVIEW_IMAGES_KEYS)
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

    @classmethod
    def _load_upscale_model(cls, upscale_model_name: str):
        config = cls._resolve_upscale_model_loader_config()
        kwargs = build_required_kwargs(
            config["required"],
            {
                config["model_key"]: upscale_model_name,
            },
        )
        outputs = run_node(config["class"], kwargs)
        if not outputs:
            raise RuntimeError(
                f"Load Upscale Model returned no outputs for '{upscale_model_name}'."
            )
        return outputs[0]

    @classmethod
    def _run_image_upscale_with_model(cls, upscale_model, image):
        config = cls._resolve_image_upscale_with_model_config()
        kwargs = build_required_kwargs(
            config["required"],
            {
                config["model_key"]: upscale_model,
                config["image_key"]: image,
            },
        )
        outputs = run_node(config["class"], kwargs)
        if not outputs:
            raise RuntimeError("Upscale Image (using Model) returned no outputs.")
        return outputs[0]

    @staticmethod
    def _latent_downscale_ratio(latent, vae) -> int:
        if isinstance(latent, dict):
            ratio = latent.get("downscale_ratio_spacial")
            if isinstance(ratio, (int, float)) and ratio > 0:
                return max(1, int(round(float(ratio))))

        if vae is not None and hasattr(vae, "spacial_compression_encode"):
            try:
                ratio = vae.spacial_compression_encode()
                if isinstance(ratio, (int, float)) and ratio > 0:
                    return max(1, int(round(float(ratio))))
            except Exception:
                pass

        return 8

    @classmethod
    def _target_image_size(cls, latent, image, vae, upscale_by: float) -> Tuple[int, int] | None:
        if isinstance(latent, dict):
            samples = latent.get("samples")
            if samples is not None and hasattr(samples, "shape") and len(samples.shape) >= 4:
                ratio = cls._latent_downscale_ratio(latent, vae)
                width = max(1, int(round(samples.shape[-1] * float(upscale_by))) * ratio)
                height = max(1, int(round(samples.shape[-2] * float(upscale_by))) * ratio)
                return (width, height)

        if image is not None and hasattr(image, "shape") and len(image.shape) >= 3:
            width = max(1, int(round(image.shape[2] * float(upscale_by))))
            height = max(1, int(round(image.shape[1] * float(upscale_by))))
            return (width, height)

        return None

    @staticmethod
    def _image_size(image) -> Tuple[int, int] | None:
        if image is None or not hasattr(image, "shape") or len(image.shape) < 3:
            return None
        return (int(image.shape[2]), int(image.shape[1]))

    @staticmethod
    def _resize_image(image, width: int, height: int, upscale_method: str = "lanczos"):
        try:
            import comfy.utils  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                f"Could not import comfy.utils for image resize fallback: {exc}"
            ) from exc

        samples = image.movedim(-1, 1)
        resized = comfy.utils.common_upscale(
            samples,
            int(width),
            int(height),
            str(upscale_method),
            "disabled",
        )
        return resized.movedim(1, -1)

    @classmethod
    def _run_latent_upscale_builtin(cls, latent, upscale_method: str, upscale_by: float):
        config = cls._resolve_latent_upscale_config()
        kwargs = build_required_kwargs(
            config["required"],
            {
                config["samples_key"]: latent,
                config["method_key"]: upscale_method,
                config["scale_key"]: float(upscale_by),
            },
        )
        outputs = run_node(config["class"], kwargs)
        if not outputs:
            raise RuntimeError("Latent upscale returned no outputs.")
        return outputs[0]

    @classmethod
    def _run_latent_upscale_fallback(
        cls,
        latent,
        upscale_method: str,
        upscale_by: float,
    ):
        try:
            import comfy.utils  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "Could not resolve a built-in latent upscale node and the comfy.utils "
                f"fallback is unavailable: {exc}"
            ) from exc

        samples = None
        if isinstance(latent, dict):
            samples = latent.get("samples")
        if samples is None:
            raise RuntimeError("Latent upscale requires a LATENT with a 'samples' tensor.")

        target_width = max(1, int(round(samples.shape[-1] * float(upscale_by))))
        target_height = max(1, int(round(samples.shape[-2] * float(upscale_by))))

        output = dict(latent)
        output["samples"] = comfy.utils.common_upscale(
            samples,
            target_width,
            target_height,
            str(upscale_method),
            "disabled",
        )
        return output

    @classmethod
    def _run_latent_upscale(cls, latent, upscale_method: str, upscale_by: float):
        try:
            cls._resolve_latent_upscale_config()
        except RuntimeError as exc:
            return cls._run_latent_upscale_fallback(latent, upscale_method, upscale_by)
        return cls._run_latent_upscale_builtin(latent, upscale_method, upscale_by)

    def sample(
        self,
        upscale_by,
        upscale_model,
        latent_upscale_method,
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
        image=None,
        vae=None,
        clip=None,
        xyPlot=None,
        prompt=None,
        extra_pnginfo=None,
    ):
        del xyPlot  # Passthrough compatibility input; not consumed by this node.

        model_value = (
            model if model is not None else self._pipe_item(pipe, self._PIPE_MODEL_INDEX)
        )
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
        latent_value = (
            latent if latent is not None else self._pipe_item(pipe, self._PIPE_LATENT_INDEX)
        )
        seed_value = (
            int(seed) if seed is not None else self._pipe_item(pipe, self._PIPE_SEED_INDEX)
        )

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

        upscale_model_name = str(upscale_model or self._NONE_UPSCALE_MODEL).strip()
        use_model_upscale = (
            bool(upscale_model_name)
            and upscale_model_name != self._NONE_UPSCALE_MODEL
        )

        if use_model_upscale:
            if vae_value is None:
                raise RuntimeError(
                    "Image-model HiRes Fix requires a VAE for decode/encode. "
                    "Provide vae or pipe[2]."
                )

            base_image = image
            if base_image is None:
                base_image = self._decode_latent_to_image(latent_value, vae_value)

            try:
                loaded_upscale_model = self._load_upscale_model(upscale_model_name)
            except RuntimeError as exc:
                raise RuntimeError(
                    f"Could not load upscale model '{upscale_model_name}': {exc}"
                ) from exc

            try:
                upscaled_image = self._run_image_upscale_with_model(
                    loaded_upscale_model,
                    base_image,
                )
            except RuntimeError as exc:
                raise RuntimeError(
                    "Could not run ComfyUI's 'Upscale Image (using Model)' node for "
                    f"'{upscale_model_name}': {exc}"
                ) from exc

            target_size = self._target_image_size(
                latent_value,
                base_image,
                vae_value,
                float(upscale_by),
            )
            current_size = self._image_size(upscaled_image)
            if (
                target_size is not None
                and current_size is not None
                and current_size != target_size
            ):
                upscaled_image = self._resize_image(
                    upscaled_image,
                    target_size[0],
                    target_size[1],
                )
            upscaled_latent = self._encode_image_to_latent(upscaled_image, vae_value)
        else:
            upscaled_latent = self._run_latent_upscale(
                latent_value,
                str(latent_upscale_method),
                float(upscale_by),
            )

        sampled_latent = self._run_ksampler(
            model=model_value,
            positive=positive_value,
            negative=negative_value,
            latent=upscaled_latent,
            seed=int(seed_value),
            steps=int(steps),
            cfg=float(cfg),
            sampler_name=sampler_name,
            scheduler=scheduler,
            denoise=float(denoise),
        )

        if vae_value is None:
            raise RuntimeError(
                "Missing VAE input. Provide vae or pipe[2] to decode the HiRes Fix latent."
            )
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
    "PipeHiResFix": PipeHiResFix,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PipeHiResFix": "HiRes Fix",
}
