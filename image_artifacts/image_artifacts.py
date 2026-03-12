"""
JPEG artifact simulation nodes for ComfyUI.
"""

from __future__ import annotations

import io

import torch

try:
    import numpy as np
    from PIL import Image
except ImportError:
    np = None
    Image = None


def _clamp_image(image: torch.Tensor) -> torch.Tensor:
    return torch.clamp(image, 0.0, 1.0)


def _require_jpeg_dependencies() -> None:
    if np is None or Image is None:
        raise RuntimeError("Jpegify requires Pillow and numpy for JPEG encode/decode.")


def _normalize_quality_range(quality_min: int, quality_max: int) -> tuple[int, int]:
    minimum = max(1, min(95, int(quality_min)))
    maximum = max(1, min(95, int(quality_max)))
    if minimum > maximum:
        minimum, maximum = maximum, minimum
    return minimum, maximum


def _map_amount_to_quality(amount: float, quality_min: int, quality_max: int) -> int:
    minimum, maximum = _normalize_quality_range(quality_min, quality_max)
    t = float(amount) ** 0.85
    quality = round(maximum + ((minimum - maximum) * t))
    return max(1, min(95, int(quality)))


def _subsampling_argument(chroma_subsampling: str) -> int:
    mapping = {
        "auto": -1,
        "4:2:0": 2,
        "4:4:4": 0,
    }
    return mapping.get(str(chroma_subsampling), -1)


def _rgb_tensor_to_uint8(sample: torch.Tensor) -> "np.ndarray":
    rgb = _clamp_image(sample[:, :, :3]).detach().to(device="cpu", dtype=torch.float32).numpy()
    return np.clip(np.rint(rgb * 255.0), 0.0, 255.0).astype(np.uint8)


def _gray_tensor_to_uint8(sample: torch.Tensor) -> "np.ndarray":
    gray = _clamp_image(sample[:, :, :1]).detach().to(device="cpu", dtype=torch.float32).numpy()
    gray_rgb = np.repeat(gray, 3, axis=2)
    return np.clip(np.rint(gray_rgb * 255.0), 0.0, 255.0).astype(np.uint8)


def _jpeg_roundtrip_sample(
    sample: torch.Tensor,
    quality: int,
    subsampling: int,
    passes: int,
) -> torch.Tensor:
    _require_jpeg_dependencies()

    height, width, channels = sample.shape
    if channels >= 3:
        encoded = _rgb_tensor_to_uint8(sample)
        suffix = sample[:, :, 3:]
        restore_grayscale = False
    else:
        encoded = _gray_tensor_to_uint8(sample)
        suffix = sample[:, :, 1:]
        restore_grayscale = True

    image = Image.fromarray(encoded, mode="RGB")

    for _ in range(max(1, int(passes))):
        buffer = io.BytesIO()
        image.save(
            buffer,
            format="JPEG",
            quality=int(quality),
            subsampling=int(subsampling),
        )
        buffer.seek(0)
        with Image.open(buffer) as decoded:
            image = decoded.convert("RGB")

    decoded_np = np.asarray(image, dtype=np.float32) / 255.0
    decoded = torch.from_numpy(decoded_np).to(device=sample.device, dtype=sample.dtype)

    if restore_grayscale:
        decoded = decoded[:, :, :1]

    if suffix.shape[-1] > 0:
        decoded = torch.cat((decoded, suffix), dim=-1)

    return _clamp_image(decoded.view(height, width, channels))


class ImageJpegify:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "amount": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 1.0, "step": 0.01}),
                "quality_min": ("INT", {"default": 18, "min": 1, "max": 95, "step": 1}),
                "quality_max": ("INT", {"default": 92, "min": 1, "max": 95, "step": 1}),
                "passes": ("INT", {"default": 1, "min": 1, "max": 6, "step": 1}),
                "chroma_subsampling": (["auto", "4:2:0", "4:4:4"], {"default": "auto"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "jpegify_image"
    CATEGORY = "Veilance/Image"

    def jpegify_image(
        self,
        image,
        amount: float,
        quality_min: int,
        quality_max: int,
        passes: int,
        chroma_subsampling: str,
    ):
        if float(amount) <= 0.0:
            return (image,)

        image_bhwc = _clamp_image(image.to(dtype=torch.float32))
        quality = _map_amount_to_quality(float(amount), int(quality_min), int(quality_max))
        subsampling = _subsampling_argument(chroma_subsampling)
        outputs = [
            _jpeg_roundtrip_sample(sample, quality=quality, subsampling=subsampling, passes=passes)
            for sample in image_bhwc
        ]
        result = torch.stack(outputs, dim=0).to(dtype=image.dtype)
        return (result,)


NODE_CLASS_MAPPINGS = {
    "ImageJpegify": ImageJpegify,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageJpegify": "Jpegify",
}
