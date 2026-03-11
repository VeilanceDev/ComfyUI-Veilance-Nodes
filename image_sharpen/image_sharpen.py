"""
Image sharpening nodes for ComfyUI.
"""

from __future__ import annotations

import math

import torch
import torch.nn.functional as F

try:
    import numpy as np
    from PIL import Image, ImageFilter
except ImportError:
    np = None
    Image = None
    ImageFilter = None


_EPSILON = 1e-6


def _to_bchw(image: torch.Tensor) -> tuple[torch.Tensor, torch.dtype]:
    original_dtype = image.dtype
    return image.movedim(-1, 1).contiguous().to(dtype=torch.float32), original_dtype


def _to_bhwc(image: torch.Tensor, dtype: torch.dtype) -> torch.Tensor:
    return image.movedim(1, -1).contiguous().to(dtype=dtype)


def _clamp_image(image: torch.Tensor) -> torch.Tensor:
    return torch.clamp(image, 0.0, 1.0)


def _grouped_conv2d(image: torch.Tensor, kernel: torch.Tensor) -> torch.Tensor:
    kernel_height, kernel_width = kernel.shape
    channels = image.shape[1]
    weight = kernel.view(1, 1, kernel_height, kernel_width).expand(channels, 1, -1, -1)
    padded = F.pad(
        image,
        (kernel_width // 2, kernel_width // 2, kernel_height // 2, kernel_height // 2),
        mode="replicate",
    )
    return F.conv2d(padded, weight, groups=channels)


def _sharpen_kernel(image: torch.Tensor) -> torch.Tensor:
    return image.new_tensor(
        [
            [0.0, -1.0, 0.0],
            [-1.0, 5.0, -1.0],
            [0.0, -1.0, 0.0],
        ]
    )


def _luminance(image: torch.Tensor) -> torch.Tensor:
    if image.shape[1] >= 3:
        weights = image.new_tensor([0.299, 0.587, 0.114]).view(1, 3, 1, 1)
        return (image[:, :3] * weights).sum(dim=1, keepdim=True)
    return image.mean(dim=1, keepdim=True)


def _sobel_edge_magnitude(image: torch.Tensor) -> torch.Tensor:
    luminance = _luminance(image)
    sobel_x = image.new_tensor(
        [
            [-1.0, 0.0, 1.0],
            [-2.0, 0.0, 2.0],
            [-1.0, 0.0, 1.0],
        ]
    )
    sobel_y = image.new_tensor(
        [
            [-1.0, -2.0, -1.0],
            [0.0, 0.0, 0.0],
            [1.0, 2.0, 1.0],
        ]
    )
    grad_x = _grouped_conv2d(luminance, sobel_x)
    grad_y = _grouped_conv2d(luminance, sobel_y)
    magnitude = torch.sqrt((grad_x * grad_x) + (grad_y * grad_y) + _EPSILON)

    flattened = magnitude.flatten(start_dim=1)
    minimum = flattened.amin(dim=1).view(-1, 1, 1, 1)
    maximum = flattened.amax(dim=1).view(-1, 1, 1, 1)
    return _clamp_image((magnitude - minimum) / (maximum - minimum + _EPSILON))


def _gaussian_kernel_1d(radius: float, image: torch.Tensor) -> torch.Tensor:
    sigma = max(float(radius), _EPSILON)
    half_width = max(1, int(math.ceil(float(radius) * 3.0)))
    coordinates = torch.arange(-half_width, half_width + 1, device=image.device, dtype=image.dtype)
    kernel = torch.exp(-(coordinates * coordinates) / (2.0 * sigma * sigma))
    return kernel / kernel.sum()


def _gaussian_blur_torch(image: torch.Tensor, radius: float) -> torch.Tensor:
    if radius <= 0.0:
        return image

    kernel_1d = _gaussian_kernel_1d(radius, image)
    channels = image.shape[1]
    horizontal = kernel_1d.view(1, 1, 1, -1).expand(channels, 1, -1, -1)
    vertical = kernel_1d.view(1, 1, -1, 1).expand(channels, 1, -1, -1)
    pad = kernel_1d.numel() // 2

    blurred = F.pad(image, (pad, pad, 0, 0), mode="replicate")
    blurred = F.conv2d(blurred, horizontal, groups=channels)
    blurred = F.pad(blurred, (0, 0, pad, pad), mode="replicate")
    return F.conv2d(blurred, vertical, groups=channels)


def _gaussian_blur_pil(image: torch.Tensor, radius: float) -> torch.Tensor:
    if radius <= 0.0:
        return image
    if np is None or Image is None or ImageFilter is None:
        raise RuntimeError("Pillow and numpy are required for the CPU blur fallback path.")

    batch, channels, height, width = image.shape
    image_cpu = _clamp_image(image).detach().cpu()
    blurred_batch = np.empty((batch, channels, height, width), dtype=np.float32)

    for batch_index in range(batch):
        sample = image_cpu[batch_index].permute(1, 2, 0).numpy()
        blurred_channels = []

        for channel_index in range(channels):
            channel = np.clip(sample[:, :, channel_index] * 255.0, 0.0, 255.0).astype(np.uint8)
            blurred = Image.fromarray(channel, mode="L").filter(
                ImageFilter.GaussianBlur(radius=float(radius))
            )
            blurred_channels.append(np.asarray(blurred, dtype=np.float32) / 255.0)

        blurred_batch[batch_index] = np.stack(blurred_channels, axis=0)

    return torch.from_numpy(blurred_batch).to(device=image.device, dtype=image.dtype)


def _gaussian_blur(image: torch.Tensor, radius: float) -> torch.Tensor:
    try:
        return _gaussian_blur_torch(image, radius)
    except (RuntimeError, TypeError) as exc:
        try:
            return _gaussian_blur_pil(image, radius)
        except Exception as fallback_exc:  # pragma: no cover - defensive runtime fallback
            raise RuntimeError(
                "Gaussian blur failed for unsharp mask in both torch and Pillow fallback paths."
            ) from fallback_exc


def _sharpen_candidate(image: torch.Tensor) -> torch.Tensor:
    return _grouped_conv2d(image, _sharpen_kernel(image))


class ImageSharpen:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.05}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "sharpen_image"
    CATEGORY = "Veilance/Image/Sharpen"

    def sharpen_image(self, image, strength: float):
        if float(strength) <= 0.0:
            return (image,)

        image_bchw, original_dtype = _to_bchw(image)
        sharpened = _sharpen_candidate(image_bchw)
        output = _clamp_image(image_bchw + float(strength) * (sharpened - image_bchw))
        return (_to_bhwc(output, original_dtype),)


class ImageUnsharpMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "radius": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 20.0, "step": 0.1}),
                "amount": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 4.0, "step": 0.05}),
                "threshold": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "unsharp_mask"
    CATEGORY = "Veilance/Image/Sharpen"

    def unsharp_mask(self, image, radius: float, amount: float, threshold: float):
        if float(radius) <= 0.0 or float(amount) <= 0.0:
            return (image,)

        image_bchw, original_dtype = _to_bchw(image)
        blurred = _gaussian_blur(image_bchw, float(radius))
        detail = image_bchw - blurred
        detail_luminance = _luminance(detail).abs()

        if float(threshold) <= 0.0:
            threshold_mask = torch.ones_like(detail_luminance)
        else:
            threshold_mask = _clamp_image(
                (detail_luminance - float(threshold)) / (1.0 - float(threshold) + _EPSILON)
            )

        output = _clamp_image(image_bchw + (float(amount) * detail * threshold_mask))
        return (_to_bhwc(output, original_dtype),)


class ImageEdgeSharpen:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.05}),
                "edge_threshold": (
                    "FLOAT",
                    {"default": 0.12, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
                "edge_softness": (
                    "FLOAT",
                    {"default": 0.08, "min": 0.001, "max": 1.0, "step": 0.01},
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "edge_sharpen"
    CATEGORY = "Veilance/Image/Sharpen"

    def edge_sharpen(
        self,
        image,
        strength: float,
        edge_threshold: float,
        edge_softness: float,
    ):
        if float(strength) <= 0.0:
            return (image,)

        image_bchw, original_dtype = _to_bchw(image)
        sharpened = _sharpen_candidate(image_bchw)
        edge_magnitude = _sobel_edge_magnitude(image_bchw)
        edge_mask = _clamp_image(
            (edge_magnitude - float(edge_threshold)) / max(float(edge_softness), _EPSILON)
        )
        output = _clamp_image(
            image_bchw + (float(strength) * edge_mask * (sharpened - image_bchw))
        )
        return (_to_bhwc(output, original_dtype),)


NODE_CLASS_MAPPINGS = {
    "ImageSharpen": ImageSharpen,
    "ImageUnsharpMask": ImageUnsharpMask,
    "ImageEdgeSharpen": ImageEdgeSharpen,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageSharpen": "Sharpen",
    "ImageUnsharpMask": "Unsharp Mask",
    "ImageEdgeSharpen": "Edge Sharpen",
}
