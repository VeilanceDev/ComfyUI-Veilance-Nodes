"""
Image saver node with CivitAI-compatible metadata output.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - optional at import time
    np = None

try:
    from PIL import Image  # type: ignore
    from PIL.PngImagePlugin import PngInfo  # type: ignore
except Exception:  # pragma: no cover - optional at import time
    Image = None
    PngInfo = None

try:
    import folder_paths  # type: ignore
except Exception:  # pragma: no cover - depends on ComfyUI runtime
    folder_paths = None


class SaveImageCivitaiMetadata:
    _DEFAULT_FILENAME_STEM = "CivitAI"
    _USER_COMMENT_TAG = 0x9286
    _IMAGE_DESCRIPTION_TAG = 0x010E
    _MAKE_TAG = 0x010F
    _SAMPLER_NAME_MAP = {
        "euler_ancestral": "Euler a",
        "euler": "Euler",
        "lms": "LMS",
        "heun": "Heun",
        "dpm_2": "DPM2",
        "dpm_2_ancestral": "DPM2 a",
        "dpmpp_2s_ancestral": "DPM++ 2S a",
        "dpmpp_2m": "DPM++ 2M",
        "dpmpp_sde": "DPM++ SDE",
        "dpmpp_sde_gpu": "DPM++ SDE",
        "dpmpp_2m_sde": "DPM++ 2M SDE",
        "dpm_fast": "DPM fast",
        "dpm_adaptive": "DPM adaptive",
        "ddim": "DDIM",
        "plms": "PLMS",
        "uni_pc_bh2": "UniPC",
        "uni_pc": "UniPC",
        "lcm": "LCM",
    }

    def __init__(self):
        if folder_paths is not None:
            self.output_dir = folder_paths.get_output_directory()
        else:
            self.output_dir = os.path.join(os.getcwd(), "output")
        self.type = "output"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "output_path": ("STRING", {"default": "CivitAI/", "multiline": False}),
                "file_format": (["png", "jpg", "webp"], {"default": "png"}),
                "include_workflow": ("BOOLEAN", {"default": True}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 8.0, "min": 0.0, "max": 100.0}),
                "sampler_name": ("STRING", {"default": "", "multiline": False}),
                "scheduler": ("STRING", {"default": "", "multiline": False}),
                "model_name": ("STRING", {"default": "", "multiline": False}),
                "vae_name": ("STRING", {"default": "", "multiline": False}),
                "positive_prompt": ("STRING", {"default": "", "multiline": True}),
                "negative_prompt": ("STRING", {"default": "", "multiline": True}),
                "png_compress_level": ("INT", {"default": 4, "min": 0, "max": 9}),
                "jpg_quality": ("INT", {"default": 95, "min": 1, "max": 100}),
                "jpg_optimize": ("BOOLEAN", {"default": True}),
                "webp_quality": ("INT", {"default": 95, "min": 1, "max": 100}),
                "webp_lossless": ("BOOLEAN", {"default": False}),
                "webp_method": ("INT", {"default": 4, "min": 0, "max": 6}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "Veilance/Image"

    @classmethod
    def _normalize_format(cls, file_format: str) -> str:
        normalized = (file_format or "").strip().lower()
        if normalized == "jpeg":
            normalized = "jpg"
        if normalized not in {"png", "jpg", "webp"}:
            raise ValueError(f"Unsupported file format '{file_format}'.")
        return normalized

    @classmethod
    def _parse_output_path(cls, output_path: str, file_format: str) -> str:
        cls._normalize_format(file_format)
        raw_path = (output_path or "").strip()
        if not raw_path:
            raw_path = cls._DEFAULT_FILENAME_STEM

        if os.path.isabs(raw_path) or os.path.splitdrive(raw_path)[0]:
            raise ValueError("output_path must be relative to the ComfyUI output directory.")

        folder_only = raw_path.endswith(("/", "\\"))
        trimmed = raw_path.rstrip("/\\")

        if not trimmed:
            return cls._DEFAULT_FILENAME_STEM

        if folder_only:
            return os.path.join(trimmed, cls._DEFAULT_FILENAME_STEM)

        folder_name = os.path.dirname(trimmed)
        file_name = os.path.basename(trimmed)
        stem, extension = os.path.splitext(file_name)
        if extension.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            file_name = stem or cls._DEFAULT_FILENAME_STEM
        elif not file_name:
            file_name = cls._DEFAULT_FILENAME_STEM

        filename_prefix = os.path.join(folder_name, file_name) if folder_name else file_name
        if not filename_prefix:
            filename_prefix = cls._DEFAULT_FILENAME_STEM

        return filename_prefix

    @classmethod
    def _map_sampler_name_for_civitai(cls, sampler_name: str, scheduler: str) -> str:
        sampler_key = (sampler_name or "").strip()
        scheduler_key = (scheduler or "").strip()

        civitai_name = cls._SAMPLER_NAME_MAP.get(sampler_key, sampler_key)
        if civitai_name and scheduler_key == "karras":
            return f"{civitai_name} Karras"
        if scheduler_key and scheduler_key != "normal" and sampler_key:
            return f"{sampler_key}_{scheduler_key}"
        return civitai_name

    @classmethod
    def _build_civitai_parameters(
        cls,
        *,
        positive_prompt: str,
        negative_prompt: str,
        seed: int,
        steps: int,
        cfg: float,
        sampler_name: str,
        scheduler: str,
        model_name: str,
        vae_name: str,
        width: int,
        height: int,
    ) -> str:
        lines = [(positive_prompt or "").strip()]

        negative_value = (negative_prompt or "").strip()
        if negative_value:
            lines.append(f"Negative prompt: {negative_value}")

        parameter_parts = [
            f"Steps: {int(steps)}",
            f"Sampler: {cls._map_sampler_name_for_civitai(sampler_name, scheduler)}",
            f"CFG scale: {float(cfg):g}",
            f"Seed: {int(seed)}",
            f"Size: {int(width)}x{int(height)}",
            f"Scheduler: {scheduler or ''}",
            f"Model: {model_name or ''}",
            f"VAE: {vae_name or ''}",
            "Version: ComfyUI",
        ]
        lines.append(", ".join(parameter_parts))
        return "\n".join(lines)

    @staticmethod
    def _tensor_to_pil(image_tensor) -> Image.Image:
        image_array = 255.0 * image_tensor.cpu().numpy()
        clipped = np.clip(image_array, 0, 255).astype(np.uint8)
        return Image.fromarray(clipped)

    @staticmethod
    def _json_dumps(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    @classmethod
    def _encode_user_comment(cls, text: str) -> bytes:
        try:
            return b"ASCII\x00\x00\x00" + text.encode("ascii")
        except UnicodeEncodeError:
            return b"UNICODE\x00" + text.encode("utf-16-be")

    @classmethod
    def _build_pnginfo(
        cls,
        parameters_text: str,
        include_workflow: bool,
        prompt: Optional[Dict[str, Any]],
        extra_pnginfo: Optional[Dict[str, Any]],
    ) -> PngInfo:
        metadata = PngInfo()
        metadata.add_text("parameters", parameters_text)

        if not include_workflow:
            return metadata

        if prompt is not None:
            metadata.add_text("prompt", cls._json_dumps(prompt))
        if extra_pnginfo is not None:
            for key, value in extra_pnginfo.items():
                metadata.add_text(str(key), cls._json_dumps(value))
        return metadata

    @classmethod
    def _build_exif(
        cls,
        parameters_text: str,
        include_workflow: bool,
        prompt: Optional[Dict[str, Any]],
        extra_pnginfo: Optional[Dict[str, Any]],
    ) -> bytes:
        exif_cls = getattr(Image, "Exif", None)
        if exif_cls is None:
            raise RuntimeError(
                "The host ComfyUI Pillow build does not support EXIF image saving for JPG/WEBP."
            )

        exif = exif_cls()
        exif[cls._USER_COMMENT_TAG] = cls._encode_user_comment(parameters_text)

        if include_workflow:
            prompt_payload = {} if prompt is None else prompt
            workflow_payload = {}
            if isinstance(extra_pnginfo, dict):
                workflow_payload = extra_pnginfo.get("workflow", {})
            exif[cls._MAKE_TAG] = f"Prompt: {cls._json_dumps(prompt_payload)}"
            exif[cls._IMAGE_DESCRIPTION_TAG] = (
                f"Workflow: {cls._json_dumps(workflow_payload)}"
            )

        return exif.tobytes()

    def _save_single_image(
        self,
        *,
        image: Image.Image,
        file_path: str,
        file_format: str,
        parameters_text: str,
        include_workflow: bool,
        prompt: Optional[Dict[str, Any]],
        extra_pnginfo: Optional[Dict[str, Any]],
        png_compress_level: int,
        jpg_quality: int,
        jpg_optimize: bool,
        webp_quality: int,
        webp_lossless: bool,
        webp_method: int,
    ) -> None:
        if file_format == "png":
            pnginfo = self._build_pnginfo(
                parameters_text=parameters_text,
                include_workflow=include_workflow,
                prompt=prompt,
                extra_pnginfo=extra_pnginfo,
            )
            image.save(
                file_path,
                pnginfo=pnginfo,
                compress_level=int(png_compress_level),
            )
            return

        exif_bytes = self._build_exif(
            parameters_text=parameters_text,
            include_workflow=include_workflow,
            prompt=prompt,
            extra_pnginfo=extra_pnginfo,
        )

        try:
            if file_format == "jpg":
                jpeg_image = image.convert("RGB")
                jpeg_image.save(
                    file_path,
                    format="JPEG",
                    quality=int(jpg_quality),
                    optimize=bool(jpg_optimize),
                    exif=exif_bytes,
                )
                return

            if file_format == "webp":
                image.save(
                    file_path,
                    format="WEBP",
                    quality=int(webp_quality),
                    lossless=bool(webp_lossless),
                    method=int(webp_method),
                    exif=exif_bytes,
                )
                return
        except (TypeError, ValueError, KeyError, OSError) as exc:
            raise RuntimeError(
                f"The host ComfyUI Pillow build does not support EXIF image saving for {file_format.upper()}."
            ) from exc

        raise ValueError(f"Unsupported file format '{file_format}'.")

    def _build_ui_result(self, filename: str, subfolder: str) -> Dict[str, str]:
        return {
            "filename": filename,
            "subfolder": subfolder,
            "type": self.type,
        }

    @staticmethod
    def _ensure_runtime_dependencies() -> None:
        missing = []
        if np is None:
            missing.append("numpy")
        if Image is None or PngInfo is None:
            missing.append("Pillow")

        if missing:
            raise RuntimeError(
                "SaveImageCivitaiMetadata requires the following runtime dependencies: "
                + ", ".join(missing)
            )

    def save_images(
        self,
        images,
        output_path,
        file_format,
        include_workflow,
        seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        model_name,
        vae_name,
        positive_prompt,
        negative_prompt,
        png_compress_level,
        jpg_quality,
        jpg_optimize,
        webp_quality,
        webp_lossless,
        webp_method,
        prompt=None,
        extra_pnginfo=None,
    ):
        self._ensure_runtime_dependencies()
        normalized_format = self._normalize_format(file_format)
        filename_prefix = self._parse_output_path(output_path, normalized_format)

        first_image = images[0]
        height = int(first_image.shape[0])
        width = int(first_image.shape[1])
        if folder_paths is not None:
            (
                full_output_folder,
                filename,
                counter,
                subfolder,
                _,
            ) = folder_paths.get_save_image_path(
                filename_prefix,
                self.output_dir,
                width,
                height,
            )
        else:
            subfolder = os.path.dirname(filename_prefix).replace("\\", "/")
            filename = os.path.basename(filename_prefix) or self._DEFAULT_FILENAME_STEM
            full_output_folder = os.path.join(self.output_dir, os.path.dirname(filename_prefix))
            os.makedirs(full_output_folder, exist_ok=True)
            counter = 1
            while os.path.exists(
                os.path.join(
                    full_output_folder,
                    f"{filename}_{counter:05}_.{normalized_format}",
                )
            ):
                counter += 1

        results = []
        for image_tensor in images:
            pil_image = self._tensor_to_pil(image_tensor)
            parameters_text = self._build_civitai_parameters(
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                seed=int(seed),
                steps=int(steps),
                cfg=float(cfg),
                sampler_name=sampler_name,
                scheduler=scheduler,
                model_name=model_name,
                vae_name=vae_name,
                width=int(pil_image.width),
                height=int(pil_image.height),
            )

            file_name = f"{filename}_{counter:05}_.{normalized_format}"
            file_path = os.path.join(full_output_folder, file_name)
            self._save_single_image(
                image=pil_image,
                file_path=file_path,
                file_format=normalized_format,
                parameters_text=parameters_text,
                include_workflow=bool(include_workflow),
                prompt=prompt,
                extra_pnginfo=extra_pnginfo,
                png_compress_level=int(png_compress_level),
                jpg_quality=int(jpg_quality),
                jpg_optimize=bool(jpg_optimize),
                webp_quality=int(webp_quality),
                webp_lossless=bool(webp_lossless),
                webp_method=int(webp_method),
            )
            results.append(self._build_ui_result(file_name, subfolder))
            counter += 1

        return {"ui": {"images": results}}


NODE_CLASS_MAPPINGS = {
    "SaveImageCivitaiMetadata": SaveImageCivitaiMetadata,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SaveImageCivitaiMetadata": "Save Image (CivitAI Metadata)",
}
