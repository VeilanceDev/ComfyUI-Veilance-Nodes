"""
Resolution Selector Node for ComfyUI
Calculates width and height based on a base resolution and aspect ratio,
maintaining the same total pixel count as base_resolution².
"""

import math


class ResolutionSelector:
    """
    A node that outputs width and height integers based on a base resolution
    and selected aspect ratio. The total pixel count is maintained equal to
    base_resolution² (e.g., 1024 base = ~1 megapixel total).
    
    Includes a preview showing the calculated resolution and megapixel count.
    """
    
    # Define aspect ratios as (name, width_ratio, height_ratio)
    ASPECT_RATIOS = [
        ("1:1", 1, 1),
        ("landscape (5:4)", 5, 4),
        ("landscape (4:3)", 4, 3),
        ("landscape (3:2)", 3, 2),
        ("landscape (16:10)", 16, 10),
        ("landscape (16:9)", 16, 9),
        ("landscape (21:9)", 21, 9),
        ("portrait (4:5)", 4, 5),
        ("portrait (3:4)", 3, 4),
        ("portrait (2:3)", 2, 3),
        ("portrait (9:10)", 9, 10),
        ("portrait (9:16)", 9, 16),
        ("portrait (9:21)", 9, 21),
    ]
    
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(cls):
        aspect_ratio_names = [ar[0] for ar in cls.ASPECT_RATIOS]
        
        return {
            "required": {
                "base_resolution": ("INT", {
                    "default": 1024,
                    "min": 64,
                    "max": 8192,
                    "step": 64,
                    "display": "number"
                }),
                "aspect_ratio": (aspect_ratio_names, {
                    "default": "1:1"
                }),
            },
        }
    
    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "calculate_resolution"
    CATEGORY = "utils"
    
    @classmethod
    def calculate_dimensions(cls, base_resolution: int, aspect_ratio_name: str) -> tuple[int, int]:
        """
        Calculate width and height maintaining total pixel count.
        
        Total pixels = base_resolution²
        For aspect ratio w:h:
            width = sqrt(total_pixels * (w/h))
            height = sqrt(total_pixels * (h/w))
        
        Results are rounded to nearest multiple of 8 for optimal AI processing.
        """
        # Find the aspect ratio
        w_ratio, h_ratio = 1, 1
        for name, wr, hr in cls.ASPECT_RATIOS:
            if name == aspect_ratio_name:
                w_ratio, h_ratio = wr, hr
                break
        
        # Total pixels to maintain
        total_pixels = base_resolution * base_resolution
        
        # Calculate dimensions
        # width * height = total_pixels
        # width / height = w_ratio / h_ratio
        # Therefore: width = sqrt(total_pixels * w_ratio / h_ratio)
        #            height = sqrt(total_pixels * h_ratio / w_ratio)
        
        ratio = w_ratio / h_ratio
        width = math.sqrt(total_pixels * ratio)
        height = math.sqrt(total_pixels / ratio)
        
        # Round to nearest multiple of 8
        width = int(round(width / 8) * 8)
        height = int(round(height / 8) * 8)
        
        # Ensure minimum dimensions
        width = max(64, width)
        height = max(64, height)
        
        return width, height
    
    def calculate_resolution(self, base_resolution: int, aspect_ratio: str):
        """
        Main execution function.
        Returns width and height as integers.
        """
        width, height = self.calculate_dimensions(base_resolution, aspect_ratio)
        
        return (width, height)


# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "ResolutionSelector": ResolutionSelector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ResolutionSelector": "Resolution Selector",
}
