from .image_nodes import ImageSizeAndLatent
from .registry import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .switch_nodes import AnySwitch, AnySwitchInverse

__all__ = [
    "AnySwitch",
    "AnySwitchInverse",
    "ImageSizeAndLatent",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
]
