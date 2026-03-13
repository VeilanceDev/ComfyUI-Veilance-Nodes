"""
ComfyUI Veilance Nodes
Custom nodes including model loading, resolution, and prompt selector functionality.
"""

from importlib import import_module
import traceback


def _load_node_package(module_name: str):
    try:
        module = import_module(f".{module_name}", __name__)
    except Exception as exc:
        print(
            f"[ComfyUI-Veilance-Nodes] Skipping node package '{module_name}' "
            f"because it failed to import: {exc}"
        )
        print(traceback.format_exc())
        return {}, {}, False

    node_classes = getattr(module, "NODE_CLASS_MAPPINGS", {})
    node_display_names = getattr(module, "NODE_DISPLAY_NAME_MAPPINGS", {})

    if not isinstance(node_classes, dict) or not isinstance(node_display_names, dict):
        print(
            f"[ComfyUI-Veilance-Nodes] Node package '{module_name}' did not expose "
            "dict mappings. Skipping it."
        )
        return {}, {}, False

    return node_classes, node_display_names, True


_NODE_PACKAGE_ORDER = [
    "resolution_selector",
    "prompt_selector",
    "model_loader_trio",
    "model_loader_checkpoint_vae",
    "prompt_cleaner",
    "pipe_ksampler",
    "pipe_builder",
    "pipe_router",
    "sampler_presets",
    "seed_strategy",
    "lora_stack",
    "nano_gpt",
    "image_loader",
    "save_image_civitai",
    "image_sharpen",
    "film_grain",
    "image_artifacts",
    "text_utils",
    "image_adjustments",
    "workflow_utils",
]


def _build_node_mappings():
    node_class_mappings = {}
    node_display_name_mappings = {}
    loaded_packages = []
    skipped_packages = []

    for module_name in _NODE_PACKAGE_ORDER:
        class_mappings, display_name_mappings, loaded = _load_node_package(module_name)
        if loaded:
            loaded_packages.append(module_name)
        else:
            skipped_packages.append(module_name)
        node_class_mappings.update(class_mappings)
        node_display_name_mappings.update(display_name_mappings)

    print(
        "[ComfyUI-Veilance-Nodes] Package load summary: "
        f"loaded={len(loaded_packages)} skipped={len(skipped_packages)} "
        f"nodes={len(node_class_mappings)}"
    )
    if skipped_packages:
        print(
            "[ComfyUI-Veilance-Nodes] Skipped packages: "
            + ", ".join(skipped_packages)
        )

    return node_class_mappings, node_display_name_mappings


NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS = _build_node_mappings()

# JavaScript extensions directory
WEB_DIRECTORY = "./js"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

