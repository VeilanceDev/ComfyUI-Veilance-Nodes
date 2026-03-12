"""
Checkpoint + VAE model loader nodes for ComfyUI.
Loads MODEL+CLIP from checkpoint and VAE from either checkpoint or external VAE loader.
"""

from .model_loader_checkpoint_vae import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
)

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
