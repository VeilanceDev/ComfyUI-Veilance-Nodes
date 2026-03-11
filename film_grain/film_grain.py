"""
Film grain node for ComfyUI.
"""

from __future__ import annotations

import math

import torch
import torch.nn.functional as F


_EPSILON = 1e-6
_MAX_TORCH_SEED = 0x7FFFFFFFFFFFFFFF
_STOCK_PROFILES = {
    "35mm color": {
        "luma_intensity": 0.050,
        "color_intensity": 0.018,
        "base_grain_size": 1.0,
        "roughness": 0.42,
        "shadow_bias": 0.20,
        "highlight_rolloff": 0.38,
        "detail_threshold": 0.080,
    },
    "35mm b&w": {
        "luma_intensity": 0.058,
        "color_intensity": 0.0,
        "base_grain_size": 1.0,
        "roughness": 0.40,
        "shadow_bias": 0.24,
        "highlight_rolloff": 0.36,
        "detail_threshold": 0.082,
    },
    "16mm color": {
        "luma_intensity": 0.072,
        "color_intensity": 0.022,
        "base_grain_size": 1.35,
        "roughness": 0.55,
        "shadow_bias": 0.26,
        "highlight_rolloff": 0.32,
        "detail_threshold": 0.092,
    },
    "pushed 800": {
        "luma_intensity": 0.090,
        "color_intensity": 0.016,
        "base_grain_size": 1.55,
        "roughness": 0.72,
        "shadow_bias": 0.34,
        "highlight_rolloff": 0.24,
        "detail_threshold": 0.110,
    },
}


def _to_bchw(image: torch.Tensor) -> tuple[torch.Tensor, torch.dtype]:
    original_dtype = image.dtype
    return image.movedim(-1, 1).contiguous().to(dtype=torch.float32), original_dtype


def _to_bhwc(image: torch.Tensor, dtype: torch.dtype) -> torch.Tensor:
    return image.movedim(1, -1).contiguous().to(dtype=dtype)


def _clamp_image(image: torch.Tensor) -> torch.Tensor:
    return torch.clamp(image, 0.0, 1.0)


def _normalize_per_sample(noise: torch.Tensor) -> torch.Tensor:
    flattened = noise.flatten(start_dim=1)
    mean = flattened.mean(dim=1).view(-1, 1, 1, 1)
    std = flattened.std(dim=1, unbiased=False).view(-1, 1, 1, 1)
    return (noise - mean) / (std + _EPSILON)


def _gaussian_kernel_1d(sigma: float, image: torch.Tensor) -> torch.Tensor:
    sigma = max(float(sigma), 0.35)
    half_width = max(1, int(math.ceil(sigma * 3.0)))
    coordinates = torch.arange(
        -half_width,
        half_width + 1,
        device=image.device,
        dtype=image.dtype,
    )
    kernel = torch.exp(-(coordinates * coordinates) / (2.0 * sigma * sigma))
    return kernel / kernel.sum()


def _gaussian_blur(image: torch.Tensor, sigma: float) -> torch.Tensor:
    if sigma <= 0.0:
        return image

    kernel_1d = _gaussian_kernel_1d(sigma, image)
    channels = image.shape[1]
    horizontal = kernel_1d.view(1, 1, 1, -1).expand(channels, 1, -1, -1)
    vertical = kernel_1d.view(1, 1, -1, 1).expand(channels, 1, -1, -1)
    pad = kernel_1d.numel() // 2

    blurred = F.pad(image, (pad, pad, 0, 0), mode="replicate")
    blurred = F.conv2d(blurred, horizontal, groups=channels)
    blurred = F.pad(blurred, (0, 0, pad, pad), mode="replicate")
    return F.conv2d(blurred, vertical, groups=channels)


def _luminance(image: torch.Tensor) -> torch.Tensor:
    if image.shape[1] >= 3:
        weights = image.new_tensor([0.299, 0.587, 0.114]).view(1, 3, 1, 1)
        return (image[:, :3] * weights).sum(dim=1, keepdim=True)
    return image[:, :1]


def _seed_value(seed: int, offset: int) -> int:
    mixed = int(seed) + (offset * 0x9E3779B97F4A7C15)
    return mixed & _MAX_TORCH_SEED


def _random_noise(shape: tuple[int, ...], reference: torch.Tensor, seed: int) -> torch.Tensor:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(_seed_value(seed, 0))
    noise = torch.randn(shape, generator=generator, dtype=torch.float32)
    return noise.to(device=reference.device, dtype=reference.dtype)


def _random_noise_with_offset(
    shape: tuple[int, ...],
    reference: torch.Tensor,
    seed: int,
    offset: int,
) -> torch.Tensor:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(_seed_value(seed, offset))
    noise = torch.randn(shape, generator=generator, dtype=torch.float32)
    return noise.to(device=reference.device, dtype=reference.dtype)


def _resized_noise(
    batch: int,
    channels: int,
    height: int,
    width: int,
    scale: float,
    reference: torch.Tensor,
    seed: int,
    offset: int,
) -> torch.Tensor:
    scaled_height = max(2, int(round(height / max(scale, 1.0))))
    scaled_width = max(2, int(round(width / max(scale, 1.0))))
    noise = _random_noise_with_offset(
        (batch, channels, scaled_height, scaled_width),
        reference,
        seed,
        offset,
    )
    if scaled_height == height and scaled_width == width:
        return noise
    return F.interpolate(noise, size=(height, width), mode="bicubic", align_corners=False)


def _tonal_mask(luminance: torch.Tensor, shadow_bias: float, highlight_rolloff: float) -> torch.Tensor:
    midtone_peak = torch.exp(-((luminance - 0.48) ** 2) / 0.050)
    shadow_response = torch.pow(1.0 - luminance, 0.8)
    highlight_response = torch.pow(luminance, 1.8)
    mask = (
        0.24
        + (0.56 * midtone_peak)
        + (float(shadow_bias) * 0.28 * shadow_response)
        - (float(highlight_rolloff) * 0.18 * highlight_response)
    )
    return _clamp_image(mask)


def _detail_mask(luminance: torch.Tensor, grain_size: float, threshold: float) -> torch.Tensor:
    local_base = _gaussian_blur(luminance, sigma=max(0.8, float(grain_size) * 1.1))
    local_detail = (luminance - local_base).abs()
    detail_gate = 1.0 - _clamp_image(local_detail / max(float(threshold), _EPSILON))
    return 0.45 + (0.55 * detail_gate)


def _build_luma_grain(
    batch: int,
    height: int,
    width: int,
    grain_size: float,
    roughness: float,
    reference: torch.Tensor,
    seed: int,
) -> torch.Tensor:
    fine = _random_noise((batch, 1, height, width), reference, seed)
    medium = _resized_noise(
        batch,
        1,
        height,
        width,
        scale=max(1.0, float(grain_size) * 1.8),
        reference=reference,
        seed=seed,
        offset=1,
    )
    coarse = _resized_noise(
        batch,
        1,
        height,
        width,
        scale=max(1.0, float(grain_size) * 3.2),
        reference=reference,
        seed=seed,
        offset=2,
    )

    coarse_mix = 0.18 + (0.42 * float(roughness))
    fine_mix = 1.0 - min(coarse_mix * 0.7, 0.55)
    grain = (fine_mix * fine) + (0.35 * medium) + (coarse_mix * coarse)
    grain = torch.sign(grain) * torch.pow(torch.abs(grain) + _EPSILON, 0.92)
    grain = _gaussian_blur(grain, sigma=max(0.0, (float(grain_size) - 1.0) * 0.45))
    return _normalize_per_sample(grain)


def _build_chroma_grain(
    batch: int,
    height: int,
    width: int,
    grain_size: float,
    reference: torch.Tensor,
    seed: int,
) -> torch.Tensor:
    chroma = _resized_noise(
        batch,
        3,
        height,
        width,
        scale=max(1.0, float(grain_size) * 1.6),
        reference=reference,
        seed=seed,
        offset=3,
    )
    chroma = _gaussian_blur(chroma, sigma=max(0.4, float(grain_size) * 0.35))
    chroma = chroma - chroma.mean(dim=1, keepdim=True)
    return _normalize_per_sample(chroma)


class ImageFilmGrain:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "stock": (list(_STOCK_PROFILES.keys()), {"default": "35mm color"}),
                "amount": ("FLOAT", {"default": 0.30, "min": 0.0, "max": 2.0, "step": 0.01}),
                "grain_size": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.5, "max": 3.0, "step": 0.05},
                ),
                "color_amount": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05},
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "step": 1,
                        "control_after_generate": True,
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "apply_film_grain"
    CATEGORY = "Veilance/Image"

    def apply_film_grain(
        self,
        image,
        stock: str,
        amount: float,
        grain_size: float,
        color_amount: float,
        seed: int,
    ):
        if float(amount) <= 0.0:
            return (image,)

        profile = _STOCK_PROFILES.get(str(stock), _STOCK_PROFILES["35mm color"])
        image_bchw, original_dtype = _to_bchw(image)
        batch, channels, height, width = image_bchw.shape
        visible_channels = 1 if channels == 1 else min(channels, 3)

        effective_grain_size = float(grain_size) * float(profile["base_grain_size"])
        luminance = _luminance(image_bchw[:, :visible_channels])
        tonal_mask = _tonal_mask(
            luminance,
            shadow_bias=float(profile["shadow_bias"]),
            highlight_rolloff=float(profile["highlight_rolloff"]),
        )
        detail_mask = _detail_mask(
            luminance,
            grain_size=effective_grain_size,
            threshold=float(profile["detail_threshold"]),
        )
        adaptive_mask = tonal_mask * detail_mask

        luma_grain = _build_luma_grain(
            batch=batch,
            height=height,
            width=width,
            grain_size=effective_grain_size,
            roughness=float(profile["roughness"]),
            reference=image_bchw,
            seed=int(seed),
        )
        luma_strength = float(amount) * float(profile["luma_intensity"]) * adaptive_mask

        output = image_bchw.clone()
        if visible_channels == 1:
            output[:, :1] = _clamp_image(output[:, :1] + (luma_grain * luma_strength))
        else:
            output[:, :visible_channels] = _clamp_image(
                output[:, :visible_channels]
                + (luma_grain.expand(-1, visible_channels, -1, -1) * luma_strength)
            )

        effective_color = float(color_amount) * float(profile["color_intensity"])
        if visible_channels >= 3 and effective_color > 0.0:
            chroma_grain = _build_chroma_grain(
                batch=batch,
                height=height,
                width=width,
                grain_size=effective_grain_size,
                reference=image_bchw,
                seed=int(seed),
            )
            chroma_strength = effective_color * (0.25 + (0.75 * adaptive_mask))
            output[:, :3] = _clamp_image(output[:, :3] + (chroma_grain * chroma_strength))

        return (_to_bhwc(output, original_dtype),)


NODE_CLASS_MAPPINGS = {
    "ImageFilmGrain": ImageFilmGrain,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageFilmGrain": "Film Grain",
}
