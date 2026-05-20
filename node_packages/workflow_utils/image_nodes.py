from .constants import CATEGORY
from .helpers import build_empty_latent


class ImageSizeAndLatent:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 64}),
            }
        }

    RETURN_TYPES = ("INT", "INT", "LATENT")
    RETURN_NAMES = ("width", "height", "latent")
    FUNCTION = "get_size"
    CATEGORY = CATEGORY

    def get_size(self, image, batch_size=1):
        height = image.shape[1]
        width = image.shape[2]
        latent = build_empty_latent(image, batch_size)
        return (width, height, latent)
