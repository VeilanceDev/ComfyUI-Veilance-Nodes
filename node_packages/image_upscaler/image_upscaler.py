"""
ESRGAN/upscale-model image upscaler node for ComfyUI.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

try:
    import folder_paths  # type: ignore
except Exception:
    folder_paths = None

from ...utils.comfy_reflection import (
    build_required_kwargs,
    extract_options,
    find_first_input,
    get_required_inputs,
    preview_image,
    resolve_node_class,
    run_node,
)


class VeilanceImageUpscaler:
    _UPSCALE_MODEL_CATEGORIES = ("upscale_models", "esrgan")
    _UPSCALE_MODEL_NAME_KEYS = ("model_name", "upscale_model_name", "model")
    _IMAGE_UPSCALE_MODEL_KEYS = ("upscale_model", "model")
    _IMAGE_UPSCALE_IMAGE_KEYS = ("image", "images", "pixels")

    @classmethod
    def _resolve_upscale_model_loader_config(cls) -> Dict[str, Any]:
        loader_class = resolve_node_class(
            "Load Upscale Model",
            ("UpscaleModelLoader",),
        )
        required_inputs = get_required_inputs(loader_class)
        model_key, model_input = find_first_input(
            required_inputs,
            cls._UPSCALE_MODEL_NAME_KEYS,
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
    def _upscale_model_input(cls):
        options: List[str] = []
        metadata: Dict[str, Any] = {}

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

        normalized: List[str] = []
        seen = set()
        for option in options:
            option_text = str(option).strip()
            if not option_text or option_text in seen:
                continue
            seen.add(option_text)
            normalized.append(option_text)

        if not normalized:
            normalized = [""]

        default = metadata.get("default")
        if default not in normalized:
            metadata["default"] = normalized[0]

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
    def _image_size(image) -> Tuple[int, int] | None:
        if image is None or not hasattr(image, "shape") or len(image.shape) < 3:
            return None
        return (int(image.shape[2]), int(image.shape[1]))

    @classmethod
    def _target_image_size(cls, image, upscale_by: float) -> Tuple[int, int]:
        image_size = cls._image_size(image)
        if image_size is None:
            raise RuntimeError("Image upscaling requires an IMAGE tensor input.")
        width, height = image_size
        return (
            max(1, int(round(width * float(upscale_by)))),
            max(1, int(round(height * float(upscale_by)))),
        )

    @staticmethod
    def _resize_image(image, width: int, height: int):
        try:
            import comfy.utils  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                f"Could not import comfy.utils for exact scale resize: {exc}"
            ) from exc

        samples = image.movedim(-1, 1)
        resized = comfy.utils.common_upscale(
            samples,
            int(width),
            int(height),
            "lanczos",
            "disabled",
        )
        return resized.movedim(1, -1)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "upscale_model": cls._upscale_model_input(),
                "upscale_by": (
                    "FLOAT",
                    {"default": 1.5, "min": 1.0, "max": 8.0, "step": 0.05},
                ),
                "image_output": (["Preview", "Hide"], {"default": "Preview"}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "upscale"
    CATEGORY = "Veilance/Image"
    SEARCH_ALIASES = [
        "esrgan",
        "upscale",
        "image upscale",
        "upscale image",
        "veilance upscaler",
    ]

    def upscale(
        self,
        image,
        upscale_model,
        upscale_by,
        image_output,
        prompt=None,
        extra_pnginfo=None,
    ):
        upscale_model_name = str(upscale_model or "").strip()
        if not upscale_model_name:
            raise RuntimeError("Select an upscale model before running Image Upscaler.")

        try:
            scale = float(upscale_by)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("upscale_by must be a number.") from exc
        if scale <= 0:
            raise RuntimeError("upscale_by must be greater than 0.")

        target_width, target_height = self._target_image_size(image, scale)

        try:
            loaded_upscale_model = self._load_upscale_model(upscale_model_name)
        except RuntimeError as exc:
            raise RuntimeError(
                f"Could not load upscale model '{upscale_model_name}': {exc}"
            ) from exc

        try:
            upscaled_image = self._run_image_upscale_with_model(
                loaded_upscale_model,
                image,
            )
        except RuntimeError as exc:
            raise RuntimeError(
                "Could not run ComfyUI's 'Upscale Image (using Model)' node for "
                f"'{upscale_model_name}': {exc}"
            ) from exc

        current_size = self._image_size(upscaled_image)
        target_size = (target_width, target_height)
        if current_size is not None and current_size != target_size:
            upscaled_image = self._resize_image(
                upscaled_image,
                target_width,
                target_height,
            )

        if image_output == "Preview":
            preview_image(upscaled_image, prompt=prompt, extra_pnginfo=extra_pnginfo)

        return (upscaled_image,)


NODE_CLASS_MAPPINGS = {
    "VeilanceImageUpscaler": VeilanceImageUpscaler,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VeilanceImageUpscaler": "Image Upscaler",
}
