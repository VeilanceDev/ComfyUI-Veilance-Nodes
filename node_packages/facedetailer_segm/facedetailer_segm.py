"""
Pipe-aware SEGM Face Detailer node.
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any, Iterable, List, Tuple

from ...utils.comfy_reflection import (
    encode_image_to_latent,
    input_with_default,
    preview_image,
    resolve_ksampler_config,
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


class VeilanceSegmFaceDetailer:
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

    @staticmethod
    def _with_default(input_spec: Any, default_value: Any) -> Any:
        return input_with_default(input_spec, default_value)

    @classmethod
    def INPUT_TYPES(cls):
        ksampler_config = cls._resolve_ksampler_config()
        return {
            "required": {
                "image": ("IMAGE",),
                "segm_detector": ("SEGM_DETECTOR",),
                "target_labels": (
                    "STRING",
                    {
                        "default": "*",
                        "multiline": True,
                        "tooltip": "Comma or newline separated segment labels. Supports * and ?. Empty or * matches all detections.",
                    },
                ),
                "wildcard": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": False,
                    },
                ),
                "threshold": (
                    "FLOAT",
                    {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
                "dilation": ("INT", {"default": 10, "min": -512, "max": 512, "step": 1}),
                "crop_factor": (
                    "FLOAT",
                    {"default": 3.0, "min": 1.0, "max": 10.0, "step": 0.1},
                ),
                "drop_size": ("INT", {"default": 10, "min": 1, "max": 8192, "step": 1}),
                "guide_size": (
                    "FLOAT",
                    {"default": 512, "min": 64, "max": 8192, "step": 8},
                ),
                "guide_size_for": (
                    "BOOLEAN",
                    {"default": True, "label_on": "bbox", "label_off": "crop_region"},
                ),
                "max_size": (
                    "FLOAT",
                    {"default": 1024, "min": 64, "max": 8192, "step": 8},
                ),
                "steps": ksampler_config["steps_input"],
                "cfg": ksampler_config["cfg_input"],
                "sampler_name": ksampler_config["sampler_input"],
                "scheduler": ksampler_config["scheduler_input"],
                "denoise": cls._with_default(ksampler_config["denoise_input"], 0.5),
                "feather": ("INT", {"default": 5, "min": 0, "max": 100, "step": 1}),
                "noise_mask": (
                    "BOOLEAN",
                    {"default": True, "label_on": "enabled", "label_off": "disabled"},
                ),
                "force_inpaint": (
                    "BOOLEAN",
                    {"default": True, "label_on": "enabled", "label_off": "disabled"},
                ),
                "cycle": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1}),
                "image_output": (["Preview", "Hide"], {"default": "Preview"}),
                "seed": seed_input_with_control(ksampler_config["seed_input"]),
            },
            "optional": {
                "pipe": ("PIPE",),
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "detailer_hook": ("DETAILER_HOOK",),
                "scheduler_func_opt": ("SCHEDULER_FUNC",),
                "inpaint_model": (
                    "BOOLEAN",
                    {"default": False, "label_on": "enabled", "label_off": "disabled"},
                ),
                "noise_mask_feather": (
                    "INT",
                    {"default": 20, "min": 0, "max": 100, "step": 1},
                ),
                "tiled_encode": (
                    "BOOLEAN",
                    {"default": False, "label_on": "enabled", "label_off": "disabled"},
                ),
                "tiled_decode": (
                    "BOOLEAN",
                    {"default": False, "label_on": "enabled", "label_off": "disabled"},
                ),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("IMAGE", "PIPE", "MASK", "IMAGE")
    RETURN_NAMES = ("image", "pipe", "mask", "cropped_refined")
    OUTPUT_IS_LIST = (False, False, False, True)
    FUNCTION = "detail"
    CATEGORY = "Veilance/Sampling"
    SEARCH_ALIASES = [
        "face detailer",
        "segm detailer",
        "adetailer",
        "impact detailer",
    ]

    @staticmethod
    def _pipe_item(pipe: Any, index: int) -> Any:
        return pipe_item(pipe, index)

    @staticmethod
    def _pipe_tail(pipe: Any, replaced_items: int) -> Tuple[Any, ...]:
        return pipe_tail(pipe, replaced_items)

    @classmethod
    def _encode_image_to_latent(cls, image: Any, vae: Any) -> Any:
        return encode_image_to_latent(image, vae)

    @classmethod
    def _preview_image(cls, image: Any, prompt: Any = None, extra_pnginfo: Any = None) -> None:
        preview_image(image, prompt=prompt, extra_pnginfo=extra_pnginfo)

    @staticmethod
    def _parse_label_patterns(target_labels: str | None) -> List[str]:
        if target_labels is None:
            return []

        raw_patterns = str(target_labels).replace("\n", ",").split(",")
        patterns = [pattern.strip().lower() for pattern in raw_patterns if pattern.strip()]
        if not patterns or "*" in patterns:
            return []
        return patterns

    @classmethod
    def _label_matches(cls, label: Any, patterns: Iterable[str]) -> bool:
        normalized_patterns = list(patterns)
        if not normalized_patterns:
            return True

        label_text = str(label or "").strip().lower()
        return any(fnmatchcase(label_text, pattern) for pattern in normalized_patterns)

    @classmethod
    def _filter_segs_by_label(cls, segs: Any, target_labels: str | None) -> Any:
        patterns = cls._parse_label_patterns(target_labels)
        if not patterns:
            return segs

        if not isinstance(segs, tuple) or len(segs) < 2:
            raise RuntimeError("SEGM detector returned an invalid SEGS payload.")

        return (segs[0], [seg for seg in segs[1] if cls._label_matches(getattr(seg, "label", ""), patterns)])

    @staticmethod
    def _seg_count(segs: Any) -> int:
        if isinstance(segs, tuple) and len(segs) >= 2 and hasattr(segs[1], "__len__"):
            return len(segs[1])
        return 0

    @staticmethod
    def _image_batch_size(image: Any) -> int:
        if hasattr(image, "shape") and len(image.shape) >= 1:
            return int(image.shape[0])
        try:
            return len(image)
        except Exception:
            return 1

    @staticmethod
    def _image_hw(image: Any) -> Tuple[int, int]:
        if hasattr(image, "shape") and len(image.shape) >= 3:
            return int(image.shape[1]), int(image.shape[2])
        raise RuntimeError("Face Detailer (SEGM Pipe) requires an IMAGE tensor input.")

    @staticmethod
    def _single_image(image: Any, index: int) -> Any:
        if hasattr(image, "__getitem__") and hasattr(image, "shape") and len(image.shape) >= 4:
            return image[index : index + 1]
        return image

    @staticmethod
    def _cat_tensors(items: List[Any], dim: int = 0) -> Any:
        if not items:
            return None
        if len(items) == 1:
            return items[0]
        try:
            import torch

            return torch.cat(items, dim=dim)
        except Exception as exc:
            raise RuntimeError(f"Could not combine detailer output batch: {exc}") from exc

    @staticmethod
    def _empty_mask_like_image(image: Any) -> Any:
        try:
            import torch
        except Exception as exc:
            raise RuntimeError(f"Could not create empty MASK because torch is unavailable: {exc}") from exc

        height, width = VeilanceSegmFaceDetailer._image_hw(image)
        kwargs = {}
        if hasattr(image, "device"):
            kwargs["device"] = image.device
        return torch.zeros((1, height, width), dtype=torch.float32, **kwargs)

    @staticmethod
    def _mask_with_batch_dim(mask: Any) -> Any:
        if hasattr(mask, "dim") and mask.dim() == 2:
            return mask.unsqueeze(0)
        return mask

    @staticmethod
    def _empty_image_placeholder(image: Any) -> Any:
        try:
            from impact.utils import empty_pil_tensor  # type: ignore

            return empty_pil_tensor()
        except Exception:
            try:
                import torch

                kwargs = {}
                if hasattr(image, "device"):
                    kwargs["device"] = image.device
                return torch.zeros((1, 64, 64, 3), dtype=torch.float32, **kwargs)
            except Exception as exc:
                raise RuntimeError(f"Could not create placeholder IMAGE: {exc}") from exc

    @staticmethod
    def _resolve_impact_helpers():
        try:
            from impact import core  # type: ignore
            from impact.impact_pack import DetailerForEach  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "Face Detailer (SEGM Pipe) requires ComfyUI Impact Pack. "
                "Install/enable ComfyUI-Impact-Pack and restart ComfyUI."
            ) from exc
        return core, DetailerForEach

    @staticmethod
    def _combined_mask_from_segs(core: Any, segs: Any, image: Any) -> Any:
        if VeilanceSegmFaceDetailer._seg_count(segs) == 0:
            return VeilanceSegmFaceDetailer._empty_mask_like_image(image)
        return VeilanceSegmFaceDetailer._mask_with_batch_dim(core.segs_to_combined_mask(segs))

    @classmethod
    def _run_detailer(
        cls,
        DetailerForEach: Any,
        *,
        image: Any,
        segs: Any,
        model: Any,
        clip: Any,
        vae: Any,
        guide_size: float,
        guide_size_for: bool,
        max_size: float,
        seed: int,
        steps: int,
        cfg: float,
        sampler_name: str,
        scheduler: str,
        positive: Any,
        negative: Any,
        denoise: float,
        feather: int,
        noise_mask: bool,
        force_inpaint: bool,
        wildcard: str,
        detailer_hook: Any,
        cycle: int,
        inpaint_model: bool,
        noise_mask_feather: int,
        scheduler_func_opt: Any,
        tiled_encode: bool,
        tiled_decode: bool,
    ) -> Tuple[Any, List[Any]]:
        if cls._seg_count(segs) == 0:
            return image, [cls._empty_image_placeholder(image)]

        try:
            enhanced_img, _, cropped_refined, *_ = DetailerForEach.do_detail(
                image,
                segs,
                model,
                clip,
                vae,
                guide_size,
                guide_size_for,
                max_size,
                seed,
                steps,
                cfg,
                sampler_name,
                scheduler,
                positive,
                negative,
                denoise,
                feather,
                noise_mask,
                force_inpaint,
                wildcard,
                detailer_hook,
                cycle=cycle,
                inpaint_model=inpaint_model,
                noise_mask_feather=noise_mask_feather,
                scheduler_func_opt=scheduler_func_opt,
                tiled_encode=tiled_encode,
                tiled_decode=tiled_decode,
            )
        except TypeError:
            enhanced_img, _, cropped_refined, *_ = DetailerForEach.do_detail(
                image,
                segs,
                model,
                clip,
                vae,
                guide_size,
                guide_size_for,
                max_size,
                seed,
                steps,
                cfg,
                sampler_name,
                scheduler,
                positive,
                negative,
                denoise,
                feather,
                noise_mask,
                force_inpaint,
                wildcard,
                detailer_hook,
                cycle=cycle,
                inpaint_model=inpaint_model,
                noise_mask_feather=noise_mask_feather,
                scheduler_func_opt=scheduler_func_opt,
            )

        if not cropped_refined:
            cropped_refined = [cls._empty_image_placeholder(image)]
        return enhanced_img, list(cropped_refined)

    @staticmethod
    def _require_value(value: Any, message: str) -> Any:
        if value is None:
            raise RuntimeError(message)
        return value

    def detail(
        self,
        image,
        segm_detector,
        target_labels,
        wildcard,
        threshold,
        dilation,
        crop_factor,
        drop_size,
        guide_size,
        guide_size_for,
        max_size,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise,
        feather,
        noise_mask,
        force_inpaint,
        cycle,
        image_output,
        seed,
        pipe=None,
        model=None,
        clip=None,
        vae=None,
        positive=None,
        negative=None,
        detailer_hook=None,
        scheduler_func_opt=None,
        inpaint_model=False,
        noise_mask_feather=20,
        tiled_encode=False,
        tiled_decode=False,
        prompt=None,
        extra_pnginfo=None,
    ):
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
        seed_value = int(seed) if seed is not None else self._pipe_item(pipe, self._PIPE_SEED_INDEX)

        self._require_value(
            model_value,
            "Missing required MODEL input. Provide model or a pipe containing model.",
        )
        self._require_value(
            clip_value,
            "Missing required CLIP input. Provide clip or a pipe containing clip.",
        )
        self._require_value(
            vae_value,
            "Missing required VAE input. Provide vae or a pipe containing vae.",
        )
        self._require_value(
            positive_value,
            "Missing required positive CONDITIONING input. Provide positive or pipe[3].",
        )
        self._require_value(
            negative_value,
            "Missing required negative CONDITIONING input. Provide negative or pipe[4].",
        )
        self._require_value(
            seed_value,
            "Missing required seed input. Provide seed or a pipe containing seed.",
        )

        if segm_detector is None or not hasattr(segm_detector, "detect"):
            raise RuntimeError(
                "Face Detailer (SEGM Pipe) requires a SEGM_DETECTOR with a detect method. "
                "Load one with a compatible provider such as Impact Subpack UltralyticsDetectorProvider."
            )

        core, DetailerForEach = self._resolve_impact_helpers()

        result_images: List[Any] = []
        result_masks: List[Any] = []
        cropped_refined: List[Any] = []

        batch_size = self._image_batch_size(image)
        if batch_size > 1:
            print(
                "[ComfyUI-Veilance-Nodes] WARN: Face Detailer (SEGM Pipe) received an image batch. "
                "It will process each frame independently; Impact detailers are not intended for video detailing."
            )

        for index in range(batch_size):
            single_image = self._single_image(image, index)
            try:
                segs = segm_detector.detect(
                    single_image,
                    float(threshold),
                    int(dilation),
                    float(crop_factor),
                    int(drop_size),
                )
            except TypeError as exc:
                raise RuntimeError(
                    "SEGM detector did not accept the expected detect(image, threshold, dilation, crop_factor, drop_size) call."
                ) from exc

            filtered_segs = self._filter_segs_by_label(segs, target_labels)
            mask = self._combined_mask_from_segs(core, filtered_segs, single_image)
            enhanced_image, refined_crops = self._run_detailer(
                DetailerForEach,
                image=single_image,
                segs=filtered_segs,
                model=model_value,
                clip=clip_value,
                vae=vae_value,
                guide_size=float(guide_size),
                guide_size_for=bool(guide_size_for),
                max_size=float(max_size),
                seed=int(seed_value) + index,
                steps=int(steps),
                cfg=float(cfg),
                sampler_name=str(sampler_name),
                scheduler=str(scheduler),
                positive=positive_value,
                negative=negative_value,
                denoise=float(denoise),
                feather=int(feather),
                noise_mask=bool(noise_mask),
                force_inpaint=bool(force_inpaint),
                wildcard=str(wildcard or ""),
                detailer_hook=detailer_hook,
                cycle=int(cycle),
                inpaint_model=bool(inpaint_model),
                noise_mask_feather=int(noise_mask_feather),
                scheduler_func_opt=scheduler_func_opt,
                tiled_encode=bool(tiled_encode),
                tiled_decode=bool(tiled_decode),
            )

            result_images.append(enhanced_image)
            result_masks.append(mask)
            cropped_refined.extend(refined_crops)

        image_value = self._cat_tensors(result_images, dim=0)
        mask_value = self._cat_tensors(result_masks, dim=0)
        if not cropped_refined:
            cropped_refined = [self._empty_image_placeholder(image)]

        latent_value = self._encode_image_to_latent(image_value, vae_value)
        pipe_out = (
            model_value,
            clip_value,
            vae_value,
            positive_value,
            negative_value,
            latent_value,
            int(seed_value),
            *self._pipe_tail(pipe, 7),
        )

        if image_output == "Preview":
            self._preview_image(image_value, prompt=prompt, extra_pnginfo=extra_pnginfo)

        return (image_value, pipe_out, mask_value, cropped_refined)


NODE_CLASS_MAPPINGS = {
    "VeilanceSegmFaceDetailer": VeilanceSegmFaceDetailer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VeilanceSegmFaceDetailer": "Face Detailer (SEGM Pipe)",
}
