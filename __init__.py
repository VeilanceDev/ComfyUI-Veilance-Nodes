"""
ComfyUI Veilance Nodes
Custom nodes including Resolution Selector and String Concatenation functionality.
"""

from .resolution_selector import (
    NODE_CLASS_MAPPINGS as RESOLUTION_SELECTOR_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as RESOLUTION_SELECTOR_DISPLAY_MAPPINGS,
)

# Combine all node mappings
NODE_CLASS_MAPPINGS = {
    **RESOLUTION_SELECTOR_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    **RESOLUTION_SELECTOR_DISPLAY_MAPPINGS,
}

# JavaScript extensions directory
WEB_DIRECTORY = "./js"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

