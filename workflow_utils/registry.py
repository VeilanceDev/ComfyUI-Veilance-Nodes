from .image_nodes import ImageSizeAndLatent
from .switch_nodes import AnySwitch, AnySwitchInverse


NODE_CLASS_MAPPINGS = {
    "VeilanceAnySwitch": AnySwitch,
    "VeilanceAnySwitchInverse": AnySwitchInverse,
    "VeilanceImageSizeAndLatent": ImageSizeAndLatent,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VeilanceAnySwitch": "Any Switch",
    "VeilanceAnySwitchInverse": "Any Switch (Inverse)",
    "VeilanceImageSizeAndLatent": "Image Size & Empty Latent",
}
