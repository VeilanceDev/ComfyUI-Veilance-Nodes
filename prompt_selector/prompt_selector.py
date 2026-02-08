"""
Prompt Selector Nodes for ComfyUI.
Dynamically generates one node per folder; each prompt file becomes a dropdown.
Supports YAML, CSV, and JSON formats. Outputs positive and negative prompts.
"""

from __future__ import annotations

import threading
from typing import Dict, Set, Tuple

from .file_utils import (
    DISABLED_OPTION,
    discover_categories,
    get_all_category_data,
    get_cache_checksum,
    get_file_dropdown_options,
    get_prompt_entry_details,
    get_prompt_from_file,
    refresh_cache,
    start_file_watcher,
)

PROMPT_SELECTOR_CLASS_PREFIX = "PromptSelector_"
PLACEHOLDER_CLASS_NAME = "PromptSelector"

NODE_CLASS_TO_CATEGORY: Dict[str, str] = {}
NODE_CLASS_MAPPINGS: Dict[str, type] = {}
NODE_DISPLAY_NAME_MAPPINGS: Dict[str, str] = {}

_MAPPING_LOCK = threading.RLock()
_REGISTERED_CLASS_NAMES: Set[str] = set()


class PromptSelectorPlaceholder:
    """Placeholder node shown when no prompt data is found."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "message": (
                    "STRING",
                    {
                        "default": (
                            "No prompt files found. Add .yaml/.yml/.csv/.json files "
                            "to data/prompts/"
                        ),
                        "multiline": True,
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("positive", "negative")
    FUNCTION = "show_message"
    CATEGORY = "utils/prompts"

    def show_message(self, message):
        return ("", "")


def create_category_node_class(category_name: str):
    """
    Factory function to create a node class for a specific category.

    Each category folder gets its own node class, and each prompt file
    in that folder becomes a dropdown widget on the node.
    """

    class CategoryPromptNode:
        """
        Dynamically generated node for a prompt category.
        Each prompt file in the folder becomes a dropdown with its prompts.
        Outputs both positive and negative prompts.
        """

        _category = category_name

        def __init__(self):
            pass

        @classmethod
        def INPUT_TYPES(cls):
            """
            Generate inputs based on prompt files in this category.
            Each prompt file becomes a dropdown widget.
            """
            inputs = {
                "required": {
                    "separator": (
                        "STRING",
                        {
                            "default": ", ",
                            "multiline": False,
                        },
                    ),
                },
                "optional": {},
                "hidden": {
                    "_category": ("STRING", {"default": cls._category}),
                },
            }

            data = get_all_category_data()
            files_data = data.get(cls._category)
            if not files_data:
                return inputs

            for file_key in files_data.keys():
                options = get_file_dropdown_options(cls._category, file_key)
                inputs["optional"][file_key] = (
                    options,
                    {
                        "default": DISABLED_OPTION,
                    },
                )

            return inputs

        RETURN_TYPES = ("STRING", "STRING")
        RETURN_NAMES = ("positive", "negative")
        FUNCTION = "select_prompts"
        CATEGORY = "utils/prompts"

        @classmethod
        def IS_CHANGED(cls, **kwargs):
            """Return checksum based on file modification times."""
            return get_cache_checksum()

        def select_prompts(self, separator=", ", **kwargs):
            """
            Collect selected prompts from all dropdowns and join them.
            Returns both positive and negative prompt strings.
            """
            positive_prompts = []
            negative_prompts = []

            for widget_name, selected_display in kwargs.items():
                if widget_name == "separator":
                    continue

                if selected_display in (DISABLED_OPTION, "(none)", ""):
                    continue

                positive, negative = get_prompt_from_file(
                    self._category,
                    widget_name,
                    selected_display,
                )

                if positive:
                    positive_prompts.append(positive)
                if negative:
                    negative_prompts.append(negative)

            return (separator.join(positive_prompts), separator.join(negative_prompts))

    return CategoryPromptNode


def _build_mappings() -> Tuple[Dict[str, type], Dict[str, str], Dict[str, str]]:
    """
    Build node mappings dynamically based on discovered category folders.
    Returns class map, display map, and class->category lookup.
    """
    class_mappings: Dict[str, type] = {}
    display_mappings: Dict[str, str] = {}
    class_to_category: Dict[str, str] = {}

    for category in discover_categories():
        node_class = create_category_node_class(category)
        safe_name = category.replace("/", "_")
        class_name = (
            f"{PROMPT_SELECTOR_CLASS_PREFIX}"
            f"{safe_name.title().replace(' ', '').replace('_', '')}"
        )
        display_name = (
            f"Prompts: {category.replace('/', ' ').replace('_', ' ').title()}"
        )

        class_mappings[class_name] = node_class
        display_mappings[class_name] = display_name
        class_to_category[class_name] = category

    if not class_mappings:
        class_mappings = {PLACEHOLDER_CLASS_NAME: PromptSelectorPlaceholder}
        display_mappings = {PLACEHOLDER_CLASS_NAME: "Prompt Selector (No Data)"}
        class_to_category = {}

    return class_mappings, display_mappings, class_to_category


def _sync_with_comfy_registry(
    old_names: Set[str],
    new_class_mappings: Dict[str, type],
    new_display_mappings: Dict[str, str],
) -> None:
    """
    Best-effort runtime sync into ComfyUI's global node registry.
    This enables add/remove category classes without restarting.
    """
    try:
        import nodes  # type: ignore
    except Exception:
        return

    for class_name in old_names:
        nodes.NODE_CLASS_MAPPINGS.pop(class_name, None)
        nodes.NODE_DISPLAY_NAME_MAPPINGS.pop(class_name, None)

    nodes.NODE_CLASS_MAPPINGS.update(new_class_mappings)
    nodes.NODE_DISPLAY_NAME_MAPPINGS.update(new_display_mappings)


def regenerate_node_mappings() -> dict:
    """Rebuild Prompt Selector mappings and sync with the live node registry."""
    global NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
    global NODE_CLASS_TO_CATEGORY, _REGISTERED_CLASS_NAMES

    new_class_mappings, new_display_mappings, new_class_to_category = _build_mappings()

    with _MAPPING_LOCK:
        previous_names = set(_REGISTERED_CLASS_NAMES)
        new_names = set(new_class_mappings.keys())

        NODE_CLASS_MAPPINGS = new_class_mappings
        NODE_DISPLAY_NAME_MAPPINGS = new_display_mappings
        NODE_CLASS_TO_CATEGORY = new_class_to_category
        _REGISTERED_CLASS_NAMES = new_names

    _sync_with_comfy_registry(previous_names, new_class_mappings, new_display_mappings)

    added = sorted(new_names - previous_names)
    removed = sorted(previous_names - new_names)

    return {
        "classes": sorted(new_names),
        "classes_added": added,
        "classes_removed": removed,
    }


# Build initial mappings at import time.
regenerate_node_mappings()


# Register custom API routes
try:
    from aiohttp import web
    from server import PromptServer

    @PromptServer.instance.routes.post("/prompt_selector/refresh")
    async def refresh_prompt_lists(request):
        """API endpoint to refresh prompt cache and rebuild node mappings."""
        try:
            data = refresh_cache()
            mapping_info = regenerate_node_mappings()

            category_count = len(data)
            file_count = sum(len(files) for files in data.values())
            prompt_count = sum(
                len(prompts)
                for files in data.values()
                for prompts in files.values()
            )

            return web.json_response(
                {
                    "status": "ok",
                    "categories": category_count,
                    "files": file_count,
                    "prompts": prompt_count,
                    "node_classes": mapping_info["classes"],
                    "classes_added": mapping_info["classes_added"],
                    "classes_removed": mapping_info["classes_removed"],
                }
            )
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    @PromptServer.instance.routes.get("/prompt_selector/preview")
    async def get_prompt_preview(request):
        """API endpoint to get prompt preview for tooltip."""
        try:
            category = request.query.get("category", "")
            if not category:
                node_class = request.query.get("node_class", "")
                category = NODE_CLASS_TO_CATEGORY.get(node_class, "")
            filename = request.query.get("filename", "")
            display_name = request.query.get("display_name", "")

            if not all([category, filename, display_name]):
                return web.json_response(
                    {"status": "error", "message": "Missing required parameters"},
                    status=400,
                )

            details = get_prompt_entry_details(category, filename, display_name)
            if details is None:
                return web.json_response(
                    {"status": "error", "message": "Entry not found"},
                    status=404,
                )

            return web.json_response({"status": "ok", **details})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    # Start file watcher when server initializes.
    start_file_watcher()

except Exception as e:
    print(f"[PromptSelector] Could not register API route: {e}")
