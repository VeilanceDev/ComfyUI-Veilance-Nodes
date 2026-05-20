"""
Prompt Selector Node for ComfyUI
Provides dropdown-based prompt selection from YAML, CSV, and JSON files.
"""

from .prompt_selector import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
)

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
