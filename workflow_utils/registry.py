from .global_nodes import GlobalSamplerScheduler, GlobalSeed
from .image_nodes import ImageSizeAndLatent
from .switch_nodes import AnySwitch, AnySwitchInverse
from .variable_nodes import GetVariable, SetVariable


NODE_CLASS_MAPPINGS = {
    "VeilanceAnySwitch": AnySwitch,
    "VeilanceAnySwitchInverse": AnySwitchInverse,
    "VeilanceGlobalSamplerScheduler": GlobalSamplerScheduler,
    "VeilanceGlobalSeed": GlobalSeed,
    "VeilanceImageSizeAndLatent": ImageSizeAndLatent,
    "VeilanceSetVariable": SetVariable,
    "VeilanceGetVariable": GetVariable,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VeilanceAnySwitch": "Any Switch",
    "VeilanceAnySwitchInverse": "Any Switch (Inverse)",
    "VeilanceGlobalSamplerScheduler": "Global Sampler + Scheduler",
    "VeilanceGlobalSeed": "Global Seed",
    "VeilanceImageSizeAndLatent": "Image Size & Empty Latent",
    "VeilanceSetVariable": "Set Variable",
    "VeilanceGetVariable": "Get Variable",
}
