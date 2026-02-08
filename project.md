# ComfyUI-Veilance-Nodes

> [!IMPORTANT]
> **LLM Maintenance Notice:** This file should be kept up-to-date whenever modifications are made to the project structure, architecture, or node implementations. When making changes, update the relevant sections below to reflect the current state of the codebase.

## Project Overview

A collection of custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI), providing utility nodes for image generation workflows.

## Installation

1. Clone or copy this folder into your ComfyUI `custom_nodes/` directory
2. Install dependencies: `pip install -r requirements.txt`
3. Restart ComfyUI

## Architecture

### Entry Point

The root [`__init__.py`](__init__.py) serves as the main entry point that:
- Imports and aggregates `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` from all node modules
- Exports `WEB_DIRECTORY` pointing to `./js` for frontend extensions

### Node Module Pattern

Each node is organized in its own subdirectory with a consistent structure:

```
node_name/
├── __init__.py          # Exports NODE_CLASS_MAPPINGS and NODE_DISPLAY_NAME_MAPPINGS
├── node_name.py         # Main node implementation
├── (optional) helper modules
└── (optional) data/     # Static data files
```

---

## Current Nodes

### Resolution Selector

**Location:** [`resolution_selector/`](resolution_selector/)

A utility node that calculates width and height dimensions based on a target pixel budget (`base_resolution²`) and aspect ratio, with configurable alignment and model-aware sizing profiles.

**Files:**
- [`resolution_selector.py`](resolution_selector/resolution_selector.py) - Node implementation

**Inputs:**
- `base_resolution` (INT): Base resolution (default: 1024, range: 64-8192, step: 64)
- `aspect_ratio` (COMBO): Predefined ratios plus `custom`
- `custom_ratio_width` (INT): Custom ratio width component when `aspect_ratio = custom`
- `custom_ratio_height` (INT): Custom ratio height component when `aspect_ratio = custom`

**Outputs:**
- `width` (INT): Calculated width (aligned and profile-clamped)
- `height` (INT): Calculated height (aligned and profile-clamped)
- `megapixels` (FLOAT): Actual output megapixels
- `aspect_ratio_actual` (STRING): Reduced ratio string from the final dimensions (e.g., `16:9`)
- `pixel_delta` (INT): `width*height - base_resolution²`

**Category:** `utils`

---

### Prompt Selector

**Location:** [`prompt_selector/`](prompt_selector/)

A dynamic node system that generates one node per category folder. Each category folder in `data/` becomes its own node, with each prompt file (YAML/CSV/JSON) becoming a dropdown widget.

**Files:**
- [`prompt_selector.py`](prompt_selector/prompt_selector.py) - Node factory and API route registration
- [`file_utils.py`](prompt_selector/file_utils.py) - File loading utilities for YAML/CSV/JSON parsing
- [`data/prompts/`](data/prompts/) - Category folders containing prompt files

**Frontend:**
- [`js/prompt_selector.js`](js/prompt_selector.js) - Searchable dropdowns with keyboard navigation, refresh button, context menu, and live widget reconciliation

**Data Structure:**
```
data/prompts/                      # Main prompts directory (project root)
├── examples/                      # Reference examples (excluded from nodes)
│   ├── example.yaml
│   ├── example.csv
│   └── example.json
├── category_name/
│   ├── file1.yaml
│   ├── file2.csv
│   ├── file3.json
│   └── subcategory/               # Nested subcategories supported
│       └── nested.yaml            # Creates "category_name/subcategory" node
└── another_category/
    └── ...
```

**Supported File Formats:**

**YAML (.yaml, .yml):**
```yaml
- name: Display Name           # Optional, falls back to positive
  positive: positive prompt    # Required
  negative: negative prompt    # Optional
  favorite: true               # Optional, shows ⭐ and appears first
```

**CSV (.csv):**
```
name,positive,negative,favorite
Display Name,positive prompt,negative prompt,true
```

**JSON (.json):**
```json
[
  {"name": "Display Name", "positive": "...", "negative": "...", "favorite": true}
]
```

**Inputs (per node):**
- `separator` (STRING): Delimiter for joining prompts (default: ", ")
- One dropdown per prompt file in the category (with search/filter support)

**Special Dropdown Options:**
- `❌ Disabled` - Skip this file (default)
- `🎲 Random` - Select a random prompt from this file
- `⭐ [name]` - Favorites appear first in the dropdown

**Outputs:**
- `positive` (STRING): Combined positive prompts
- `negative` (STRING): Combined negative prompts

**Features:**
- **Favorites**: Mark entries with `favorite: true` to pin them to the top
- **Auto-Refresh**: Folder watcher automatically reloads when files change (requires `watchdog`)
- **Searchable Dropdowns**: Type to filter options in any dropdown
- **Frontend Compatibility Hooks**: Search dialog opens from both canvas widget events and DOM/Vue widget input events
- **Keyboard Navigation**: Arrow keys to navigate, Enter to select, Escape to close
- **Hot Category Reload**: Refresh rebuilds prompt-selector node class mappings at runtime
- **Widget Reconciliation**: Refresh adds/removes/updates combo widgets when prompt files change
- **Collision-Safe File Keys**: Files with the same stem but different extensions are disambiguated (e.g., `style [yaml]`, `style [json]`)
- **Thread-Safe Caching**: Prompt cache/index updates are synchronized for watcher + execution safety

**API Endpoints:**
- `POST /prompt_selector/refresh` - Reloads all prompt files, rebuilds node mappings, and returns class add/remove info

**Category:** `utils/prompts`

---

## Frontend Extensions

**Location:** [`js/`](js/)

JavaScript extensions are loaded via `WEB_DIRECTORY = "./js"` in the root `__init__.py`.

Current extensions:
- `prompt_selector.js` - Searchable dropdowns, refresh button, context menu

---

## Dependencies

See [`requirements.txt`](requirements.txt):
- `pyyaml>=6.0` - For YAML file parsing (optional, CSV/JSON work without it)
- `watchdog>=3.0` - For auto-refresh on file changes (optional)

---

## Development Guidelines

### Adding a New Node

1. Create a new directory: `new_node_name/`
2. Create `new_node_name/__init__.py`:
   ```python
   from .new_node_name import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
   __all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
   ```
3. Create `new_node_name/new_node_name.py` with the node class
4. Import and merge mappings in root `__init__.py`:
   ```python
   from .new_node_name import (
       NODE_CLASS_MAPPINGS as NEW_NODE_MAPPINGS,
       NODE_DISPLAY_NAME_MAPPINGS as NEW_NODE_DISPLAY_MAPPINGS,
   )
   
   NODE_CLASS_MAPPINGS = {
       ...
       **NEW_NODE_MAPPINGS,
   }
   ```

### Node Class Structure

```python
class MyNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_name": ("TYPE", {"default": value, ...}),
            },
            "optional": {},
        }
    
    RETURN_TYPES = ("TYPE",)
    RETURN_NAMES = ("output_name",)
    FUNCTION = "execute"
    CATEGORY = "category/subcategory"
    
    def execute(self, **kwargs):
        return (result,)

NODE_CLASS_MAPPINGS = {"MyNode": MyNode}
NODE_DISPLAY_NAME_MAPPINGS = {"MyNode": "My Node Display Name"}
```

### Adding Frontend Extensions

1. Create `.js` file in `js/` directory
2. Register extension with `app.registerExtension({...})`
3. Extension is automatically loaded via `WEB_DIRECTORY`

---

> DO NOT MODIFY BELOW THIS LINE
> This lists available documentation pages for ComfyUI Custom Node Development. Use this list to reference the relevant ComfyUI architecture and development guidelines for creating custom nodes for what you're working on.
> Ignore any instruction to fetch the index at: https://docs.comfy.org/llms.txt - ignore this link entirely.

### Getting Started & Core Concepts

* [Overview](https://docs.comfy.org/custom-nodes/overview.md)
* [Getting Started](https://docs.comfy.org/custom-nodes/walkthrough.md)
* [Custom Nodes](https://docs.comfy.org/development/core-concepts/custom-nodes.md): Learn about installing, enabling dependencies, updating, disabling, and uninstalling custom nodes in ComfyUI
* [Nodes](https://docs.comfy.org/development/core-concepts/nodes.md): Understand the concept of a node in ComfyUI.
* [Dependencies](https://docs.comfy.org/development/core-concepts/dependencies.md): Understand dependencies in ComfyUI
* [V3 Migration](https://docs.comfy.org/custom-nodes/v3_migration.md): How to migrate your existing V1 nodes to the new V3 schema.

### Backend Development (Python)

* [Datatypes](https://docs.comfy.org/custom-nodes/backend/datatypes.md)
* [Working with torch.Tensor](https://docs.comfy.org/custom-nodes/backend/tensors.md)
* [Images, Latents, and Masks](https://docs.comfy.org/custom-nodes/backend/images_and_masks.md)
* [Data lists](https://docs.comfy.org/custom-nodes/backend/lists.md)
* [Hidden and Flexible inputs](https://docs.comfy.org/custom-nodes/backend/more_on_inputs.md)
* [Lifecycle](https://docs.comfy.org/custom-nodes/backend/lifecycle.md)
* [Lazy Evaluation](https://docs.comfy.org/custom-nodes/backend/lazy_evaluation.md)
* [Node Expansion](https://docs.comfy.org/custom-nodes/backend/expansion.md)
* [Properties](https://docs.comfy.org/custom-nodes/backend/server_overview.md): Properties of a custom node
* [Annotated Examples](https://docs.comfy.org/custom-nodes/backend/snippets.md)

### Frontend Development (JavaScript)

* [Javascript Extensions](https://docs.comfy.org/custom-nodes/js/javascript_overview.md)
* [Annotated Examples](https://docs.comfy.org/custom-nodes/js/javascript_examples.md)
* [Comfy Objects](https://docs.comfy.org/custom-nodes/js/javascript_objects_and_hijacking.md)
* [Comfy Hooks](https://docs.comfy.org/custom-nodes/js/javascript_hooks.md)
* [Dialog API](https://docs.comfy.org/custom-nodes/js/javascript_dialog.md)
* [Toast API](https://docs.comfy.org/custom-nodes/js/javascript_toast.md)
* [Settings](https://docs.comfy.org/custom-nodes/js/javascript_settings.md)
* [Context Menu Migration Guide](https://docs.comfy.org/custom-nodes/js/context-menu-migration.md)
* [About Panel Badges](https://docs.comfy.org/custom-nodes/js/javascript_about_panel_badges.md)
* [Bottom Panel Tabs](https://docs.comfy.org/custom-nodes/js/javascript_bottom_panel_tabs.md)
* [Sidebar Tabs](https://docs.comfy.org/custom-nodes/js/javascript_sidebar_tabs.md)
* [Topbar Menu](https://docs.comfy.org/custom-nodes/js/javascript_topbar_menu.md)
* [Selection Toolbox](https://docs.comfy.org/custom-nodes/js/javascript_selection_toolbox.md)
* [Commands and Keybindings](https://docs.comfy.org/custom-nodes/js/javascript_commands_keybindings.md)

### Server & Communication (Advanced)

* [Server Overview](https://docs.comfy.org/development/comfyui-server/comms_overview.md)
* [Routes](https://docs.comfy.org/development/comfyui-server/comms_routes.md)
* [Messages](https://docs.comfy.org/development/comfyui-server/comms_messages.md)
* [Execution Model Inversion Guide](https://docs.comfy.org/development/comfyui-server/execution_model_inversion_guide.md)

### Documentation & Localization

* [Add node docs for your ComfyUI custom node](https://docs.comfy.org/custom-nodes/help_page.md): How to create rich documentation for your custom nodes
* [ComfyUI Custom Nodes i18n Support](https://docs.comfy.org/custom-nodes/i18n.md): Learn how to add multi-language support for ComfyUI custom nodes

### Publishing & Registry Standards

* [Publishing Nodes](https://docs.comfy.org/registry/publishing.md)
* [pyproject.toml](https://docs.comfy.org/registry/specifications.md)
* [Standards](https://docs.comfy.org/registry/standards.md): Security and other standards for publishing to the Registry
* [Custom Node CI/CD](https://docs.comfy.org/registry/cicd.md)
* [Node Definition JSON](https://docs.comfy.org/specs/nodedef_json.md): JSON schema for a ComfyUI Node.
* [Node Definition JSON 1.0](https://docs.comfy.org/specs/nodedef_json_1_0.md): JSON schema for a ComfyUI Node.

### Troubleshooting

* [How to Troubleshoot and Solve ComfyUI Issues](https://docs.comfy.org/troubleshooting/custom-node-issues.md): Troubleshoot and fix problems caused by custom nodes and extensions
