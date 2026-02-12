"""
Model Loader Trio Node for ComfyUI.
Loads Diffusion Model, CLIP, and VAE in one node.
"""

from .model_loader_trio import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
)

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
