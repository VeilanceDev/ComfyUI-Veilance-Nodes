# ComfyUI Custom Node Development Reference

**Target Audience:** LLMs / Code Generators
**Purpose:** Context injection for generating valid ComfyUI Custom Nodes.

## 1. Core Documentation Source

> ## Documentation Index
> Fetch the complete documentation index at: https://docs.comfy.org/llms.txt
> Use this file to discover all available pages before exploring further.

---

## 2. Node Class Structure Template
A ComfyUI node is a Python class. It **must** contain specific attributes to be recognized by the server.

```python
import torch

class ExampleNode:
    """
    Standard template for a ComfyUI node.
    """
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(s):
        """
        Defines input widgets and connections.
        Returns a dictionary with specific keys: 'required', 'optional', 'hidden'.
        """
        return {
            "required": {
                # Connection Input: ("TYPE_NAME",)
                "image_input": ("IMAGE",),
                
                # Widget Input: ("WIDGET_TYPE", {options})
                "int_val": ("INT", {
                    "default": 0, 
                    "min": 0, 
                    "max": 100, 
                    "step": 1, 
                    "display": "number" # or "slider"
                }),
                "float_val": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.01}),
                "string_val": ("STRING", {"multiline": False}),
                "select_val": (["Option A", "Option B"],), # Dropdown
            },
            "optional": {
                # Optional inputs do not block execution if missing
                "optional_model": ("MODEL",),
            },
            "hidden": {
                # Special internal types
                "unique_id": "UNIQUE_ID",
                "prompt": "PROMPT", 
                "extra_pnginfo": "EXTRA_PNGINFO",
            }
        }

    # Output types matching the return tuple of the execution function
    RETURN_TYPES = ("IMAGE", "INT")
    
    # Names for outputs visible in the UI (Optional, defaults to type names)
    RETURN_NAMES = ("processed_image", "count")

    # Name of the instance method to run
    FUNCTION = "execute_processing"

    # Category in the right-click menu
    CATEGORY = "Custom/Example"

    # Optional: Control caching/updating
    # Return float("NaN") to force update every run
    # def IS_CHANGED(s, image_input, int_val, **kwargs):
    #    return float("NaN")

    def execute_processing(self, image_input, int_val, float_val, string_val, select_val, optional_model=None):
        """
        The actual processing logic.
        Arguments must match keys in INPUT_TYPES['required'] + ['optional'].
        """
        
        # LOGIC GOES HERE
        # Example: Pass through
        
        return (image_input, int_val)

```

---

## 3. Data Types and Tensors

ComfyUI passes data primarily as `torch.Tensor` or standard Python types.

### Standard ComfyUI Types (Strings)

* `"IMAGE"`: Shape `[Batch, Height, Width, Channels]`. Format: `float32`, Range: `0.0` to `1.0`. **Note:** Differs from PyTorch standard `[B, C, H, W]`.
* `"MASK"`: Shape `[Batch, Height, Width]`. Range: `0.0` to `1.0`.
* `"LATENT"`: Dict `{"samples": torch.Tensor}`. Shape `[B, 4, H/8, W/8]` (for SD1.5/XL).
* `"MODEL"`: UNet wrapper.
* `"CLIP"`: CLIP Text Encoder wrapper.
* `"VAE"`: Autoencoder wrapper.
* `"CONDITIONING"`: List of tuples `[(conditioning_vector, {"pooled_output": ...})]`.

### Tensor Manipulation Rules

When manipulating images in ComfyUI:

1. **Input:** `[B, H, W, C]`
2. **Processing (PyTorch):** Usually requires permute to `[B, C, H, W]`.
```python
# Convert to standard PyTorch format
img = image_input.permute(0, 3, 1, 2)

```


3. **Output:** Must permute back to `[B, H, W, C]`.

---

## 4. Module Registration (`__init__.py`)

For the node to be loaded, the directory must contain an `__init__.py` mapping the class names.

```python
from .my_node_file import ExampleNode

# Mapping: "ClassNameString": ClassObject
NODE_CLASS_MAPPINGS = {
    "ExampleNode": ExampleNode
}

# Mapping: "ClassNameString": "Readable UI Name"
NODE_DISPLAY_NAME_MAPPINGS = {
    "ExampleNode": "My Awesome Node"
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

```

---

## 5. LLM Implementation Guidelines

When generating ComfyUI nodes, adhere to these rules:

1. **Widget Types:** Use strict widget types in `INPUT_TYPES`: `INT`, `FLOAT`, `STRING`, `BOOLEAN`. Do not invent new widget types.
2. **Tuple Syntax:** Ensure widget definitions are tuples. Correct: `("INT", {...})`. Incorrect: `{"default": 0}`.
3. **Return Tuple:** The `execute` function **must** return a tuple, even for a single item. Correct: `return (output_tensor,)`. Incorrect: `return output_tensor`.
4. **Imports:** Keep imports minimal. If using heavy libraries (opencv, scipy), import them inside the class or method to prevent startup crashes if dependencies are missing, or wrap in `try/except` blocks.
5. **Shapes:** Always verify tensor shapes. ComfyUI images are BHWC.

```

```
