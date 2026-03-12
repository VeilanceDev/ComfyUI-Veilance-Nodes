import torch

class AnySwitch:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "select": ("INT", {"default": 1, "min": 1, "max": 2, "step": 1}),
            },
            "optional": {
                "input_1": ("*",),
                "input_2": ("*",),
            }
        }
        
    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("output",)
    FUNCTION = "switch"
    CATEGORY = "Veilance/Utils"

    def switch(self, select=1, input_1=None, input_2=None):
        if select == 1:
            return (input_1,)
        return (input_2,)


class AnySwitchInverse:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "select": ("INT", {"default": 1, "min": 1, "max": 2, "step": 1}),
            },
            "optional": {
                "input_any": ("*",),
            }
        }
        
    RETURN_TYPES = ("*", "*")
    RETURN_NAMES = ("output_1", "output_2")
    FUNCTION = "switch"
    CATEGORY = "Veilance/Utils"

    def switch(self, select=1, input_any=None):
        if select == 1:
            return (input_any, None)
        return (None, input_any)


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
    CATEGORY = "Veilance/Utils"

    def get_size(self, image, batch_size=1):
        # image shape is [B, H, W, C]
        height = image.shape[1]
        width = image.shape[2]
        
        # Empty latent image
        latent_tensor = torch.zeros([batch_size, 4, height // 8, width // 8], device="cpu")
        latent = {"samples": latent_tensor}
        
        return (width, height, latent)


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
