from __future__ import annotations

import torch
import torch.nn.functional as F

def _to_bchw(image: torch.Tensor) -> tuple[torch.Tensor, torch.dtype]:
    original_dtype = image.dtype
    return image.movedim(-1, 1).contiguous().to(dtype=torch.float32), original_dtype

def _to_bhwc(image: torch.Tensor, dtype: torch.dtype) -> torch.Tensor:
    return image.movedim(1, -1).contiguous().to(dtype=dtype)

def _luminance(image: torch.Tensor) -> torch.Tensor:
    if image.shape[1] >= 3:
        weights = image.new_tensor([0.299, 0.587, 0.114]).view(1, 3, 1, 1)
        return (image[:, :3] * weights).sum(dim=1, keepdim=True)
    return image[:, :1]

class ImageVignette:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "intensity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.05}),
                "radius": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 5.0, "step": 0.05}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "apply"
    CATEGORY = "Veilance/Image"

    def apply(self, image, intensity: float, radius: float):
        image_bchw, original_dtype = _to_bchw(image)
        batch, channels, height, width = image_bchw.shape
        
        y = torch.linspace(-1, 1, height, device=image.device).view(-1, 1)
        x = torch.linspace(-1, 1, width, device=image.device).view(1, -1)
        
        # calculate distance from center
        dist = torch.sqrt(x**2 + y**2)
        
        # radius is distance at which darkening starts, intensity scales it
        # smoothstep mapping might be better
        mask = 1.0 - torch.clamp((dist / max(radius, 0.001)) ** max(intensity, 0.001), 0.0, 1.0)
        
        # mask needs to be 1, 1, H, W
        mask = mask.view(1, 1, height, width)
        
        output = image_bchw * mask
        return (_to_bhwc(output, original_dtype),)


class ImageBasicColorAdjust:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "brightness": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 5.0, "step": 0.01}),
                "contrast": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 5.0, "step": 0.01}),
                "saturation": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 5.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "apply"
    CATEGORY = "Veilance/Image"

    def apply(self, image, brightness: float, contrast: float, saturation: float):
        image_bchw, original_dtype = _to_bchw(image)
        
        img = image_bchw * brightness
        
        if contrast != 1.0:
            mean = img.mean(dim=[2, 3], keepdim=True)
            img = (img - mean) * contrast + mean
            
        if saturation != 1.0:
            luma = _luminance(img)
            img = (img - luma) * saturation + luma
            
        img = torch.clamp(img, 0.0, 1.0)
        return (_to_bhwc(img, original_dtype),)


class ImageCropToRatio:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "target_ratio": (["1:1", "4:3", "3:4", "16:9", "9:16", "21:9", "1.85:1", "2.35:1"],),
                "mode": (["crop", "pad"],),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "apply"
    CATEGORY = "Veilance/Image"

    def apply(self, image, target_ratio: str, mode: str):
        image_bchw, original_dtype = _to_bchw(image)
        batch, channels, height, width = image_bchw.shape
        
        if ":" in target_ratio:
            parts = target_ratio.split(":")
            ratio = float(parts[0]) / float(parts[1])
        else:
            ratio = float(target_ratio)
            
        current_ratio = width / max(height, 1)
        
        if abs(current_ratio - ratio) < 0.01:
            return (image,)
            
        if mode == "crop":
            if current_ratio > ratio:
                # image is wider than target, crop sides
                new_width = int(height * ratio)
                start_x = (width - new_width) // 2
                output = image_bchw[:, :, :, start_x:start_x+new_width]
            else:
                # image is taller than target, crop top/bottom
                new_height = int(width / ratio)
                start_y = (height - new_height) // 2
                output = image_bchw[:, :, start_y:start_y+new_height, :]
                
        else: # pad
            if current_ratio > ratio:
                # image is wider than target, pad top/bottom
                new_height = int(width / ratio)
                pad_total = new_height - height
                pad_top = pad_total // 2
                pad_bottom = pad_total - pad_top
                output = F.pad(image_bchw, (0, 0, pad_top, pad_bottom), "constant", 0)
            else:
                # image is taller than target, pad sides
                new_width = int(height * ratio)
                pad_total = new_width - width
                pad_left = pad_total // 2
                pad_right = pad_total - pad_left
                output = F.pad(image_bchw, (pad_left, pad_right, 0, 0), "constant", 0)
                
        return (_to_bhwc(output, original_dtype),)


NODE_CLASS_MAPPINGS = {
    "VeilanceImageVignette": ImageVignette,
    "VeilanceImageBasicColorAdjust": ImageBasicColorAdjust,
    "VeilanceImageCropToRatio": ImageCropToRatio,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VeilanceImageVignette": "Vignette",
    "VeilanceImageBasicColorAdjust": "Basic Color Adjust",
    "VeilanceImageCropToRatio": "Crop to Ratio",
}
