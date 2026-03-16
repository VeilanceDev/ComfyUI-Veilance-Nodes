from __future__ import annotations

import os
from typing import Any, Mapping

from .constants import CATEGORY

UNKNOWN_FILENAME = "<unknown filename>"
BAKED_VAE_OPTION = "(baked)"

SET_VARIABLE_CLASS = "VeilanceSetVariable"
GET_VARIABLE_CLASS = "VeilanceGetVariable"

CHECKPOINT_LOADER_CLASSES = {"CheckpointLoaderSimple", "CheckpointLoader"}
DIFFUSION_LOADER_CLASSES = {"UNETLoader", "DiffusionModelLoader"}
CLIP_LOADER_CLASSES = {"CLIPLoader"}
VAE_LOADER_CLASSES = {"VAELoader"}
MODEL_LOADER_TRIO_CLASSES = {"ModelLoaderTrio", "ModelLoaderTrioWithParams"}
CHECKPOINT_VAE_LOADER_CLASSES = {
    "ModelLoaderCheckpointVAE",
    "ModelLoaderCheckpointVAEWithParams",
}

CHECKPOINT_INPUT_KEYS = ("ckpt_name", "checkpoint", "model_name")
DIFFUSION_INPUT_KEYS = ("unet_name", "model_name", "diffusion_model", "ckpt_name")
CLIP_INPUT_KEYS = ("clip_name", "model_name", "text_encoder")
VAE_INPUT_KEYS = ("vae_name", "model_name")

PIPE_MODEL_INDEX = 0
PIPE_CLIP_INDEX = 1
PIPE_VAE_INDEX = 2

Link = tuple[str, int]


def _coerce_link(value: Any) -> Link | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None

    node_id, output_index = value
    if not isinstance(node_id, (str, int)):
        return None
    if not isinstance(output_index, (int, float)):
        return None

    return str(node_id), int(output_index)


def _resolve_prompt_node(
    prompt: Mapping[str, Any] | None,
    node_id: Any,
) -> Mapping[str, Any] | None:
    if not isinstance(prompt, Mapping):
        return None

    for candidate in (node_id, str(node_id) if node_id is not None else None):
        if candidate is None:
            continue
        node_info = prompt.get(candidate)
        if isinstance(node_info, Mapping):
            return node_info
    return None


def _resolve_input_link(inputs: Mapping[str, Any] | None, key: str) -> Link | None:
    if not isinstance(inputs, Mapping):
        return None
    return _coerce_link(inputs.get(key))


def _resolve_input_value(inputs: Mapping[str, Any] | None, key: str) -> Any:
    if not isinstance(inputs, Mapping):
        return None
    return inputs.get(key)


def _find_first_value(inputs: Mapping[str, Any] | None, keys: tuple[str, ...]) -> Any:
    if not isinstance(inputs, Mapping):
        return None

    for key in keys:
        if key in inputs:
            return inputs.get(key)
    return None


def _basename(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    normalized = text.replace("\\", "/").rstrip("/")
    return os.path.basename(normalized) or normalized


def _as_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default

    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return default


def _normalize_variable_name(name: Any) -> str:
    return str(name or "").strip()


def _resolve_set_variable_source(
    prompt: Mapping[str, Any] | None,
    variable_name: str,
    current_node_id: Any,
) -> Any:
    if not isinstance(prompt, Mapping):
        return None

    matches: list[tuple[str, Mapping[str, Any]]] = []
    for node_id, node_info in prompt.items():
        if str(node_id) == str(current_node_id):
            continue
        if not isinstance(node_info, Mapping):
            continue
        if node_info.get("class_type") != SET_VARIABLE_CLASS:
            continue

        inputs = node_info.get("inputs")
        if not isinstance(inputs, Mapping):
            continue
        if _normalize_variable_name(inputs.get("name")) != variable_name:
            continue

        matches.append((str(node_id), inputs))

    if len(matches) != 1:
        return None

    return matches[0][1].get("value")


def _filename_from_value(value: Any) -> str | None:
    if _coerce_link(value) is not None:
        return None

    filename = _basename(value)
    return filename or None


def _trace_link_filename(
    prompt: Mapping[str, Any] | None,
    link: Link | None,
    visited: set[tuple[str, int]],
) -> str | None:
    if link is None:
        return None
    return _trace_filename(prompt, link[0], link[1], visited)


def _trace_input_filename(
    prompt: Mapping[str, Any] | None,
    inputs: Mapping[str, Any] | None,
    key: str,
    visited: set[tuple[str, int]],
) -> str | None:
    link = _resolve_input_link(inputs, key)
    if link is not None:
        return _trace_link_filename(prompt, link, visited)

    return _filename_from_value(_resolve_input_value(inputs, key))


def _trace_pipe_input_component(
    prompt: Mapping[str, Any] | None,
    inputs: Mapping[str, Any] | None,
    key: str,
    component_index: int,
    visited: set[tuple[str, int]],
) -> str | None:
    link = _resolve_input_link(inputs, key)
    if link is None:
        return None
    return _trace_pipe_component(prompt, link, component_index, visited)


def _resolve_router_pipe_link(inputs: Mapping[str, Any] | None) -> Link | None:
    route = str(_resolve_input_value(inputs, "route") or "A").strip().upper()
    fallback_to_other = _as_bool(_resolve_input_value(inputs, "fallback_to_other"), True)

    primary_key = "pipe_a" if route != "B" else "pipe_b"
    secondary_key = "pipe_b" if primary_key == "pipe_a" else "pipe_a"

    selected = _resolve_input_link(inputs, primary_key)
    if selected is not None:
        return selected
    if fallback_to_other:
        return _resolve_input_link(inputs, secondary_key)
    return None


def _trace_pipe_builder_component(
    prompt: Mapping[str, Any] | None,
    inputs: Mapping[str, Any] | None,
    component_index: int,
    visited: set[tuple[str, int]],
) -> str | None:
    if component_index == PIPE_MODEL_INDEX:
        return _trace_input_filename(prompt, inputs, "model", visited) or _trace_pipe_input_component(
            prompt, inputs, "pipe", PIPE_MODEL_INDEX, visited
        )
    if component_index == PIPE_CLIP_INDEX:
        return _trace_input_filename(prompt, inputs, "clip", visited) or _trace_pipe_input_component(
            prompt, inputs, "pipe", PIPE_CLIP_INDEX, visited
        )
    if component_index == PIPE_VAE_INDEX:
        return _trace_input_filename(prompt, inputs, "vae", visited) or _trace_pipe_input_component(
            prompt, inputs, "pipe", PIPE_VAE_INDEX, visited
        )
    return None


def _trace_ksampler_component(
    prompt: Mapping[str, Any] | None,
    inputs: Mapping[str, Any] | None,
    component_index: int,
    visited: set[tuple[str, int]],
) -> str | None:
    if component_index == PIPE_MODEL_INDEX:
        return _trace_input_filename(prompt, inputs, "model", visited) or _trace_pipe_input_component(
            prompt, inputs, "pipe", PIPE_MODEL_INDEX, visited
        )
    if component_index == PIPE_CLIP_INDEX:
        return _trace_input_filename(prompt, inputs, "clip", visited) or _trace_pipe_input_component(
            prompt, inputs, "pipe", PIPE_CLIP_INDEX, visited
        )
    if component_index == PIPE_VAE_INDEX:
        return _trace_input_filename(prompt, inputs, "vae", visited) or _trace_pipe_input_component(
            prompt, inputs, "pipe", PIPE_VAE_INDEX, visited
        )
    return None


def _trace_lora_stack_component(
    prompt: Mapping[str, Any] | None,
    inputs: Mapping[str, Any] | None,
    component_index: int,
    visited: set[tuple[str, int]],
) -> str | None:
    if component_index == PIPE_MODEL_INDEX:
        return _trace_input_filename(prompt, inputs, "model", visited) or _trace_pipe_input_component(
            prompt, inputs, "pipe", PIPE_MODEL_INDEX, visited
        )
    if component_index == PIPE_CLIP_INDEX:
        return _trace_input_filename(prompt, inputs, "clip", visited) or _trace_pipe_input_component(
            prompt, inputs, "pipe", PIPE_CLIP_INDEX, visited
        )
    if component_index == PIPE_VAE_INDEX:
        return _trace_pipe_input_component(prompt, inputs, "pipe", PIPE_VAE_INDEX, visited)
    return None


def _trace_any_switch_filename(
    prompt: Mapping[str, Any] | None,
    inputs: Mapping[str, Any] | None,
    visited: set[tuple[str, int]],
) -> str | None:
    selected_key = "input_1" if _as_int(_resolve_input_value(inputs, "select"), 1) == 1 else "input_2"
    return _trace_input_filename(prompt, inputs, selected_key, visited)


def _trace_any_switch_pipe_component(
    prompt: Mapping[str, Any] | None,
    inputs: Mapping[str, Any] | None,
    component_index: int,
    visited: set[tuple[str, int]],
) -> str | None:
    selected_key = "input_1" if _as_int(_resolve_input_value(inputs, "select"), 1) == 1 else "input_2"
    return _trace_pipe_input_component(prompt, inputs, selected_key, component_index, visited)


def _trace_any_switch_inverse_filename(
    prompt: Mapping[str, Any] | None,
    inputs: Mapping[str, Any] | None,
    output_index: int,
    visited: set[tuple[str, int]],
) -> str | None:
    select = _as_int(_resolve_input_value(inputs, "select"), 1)
    if (select == 1 and output_index == 0) or (select != 1 and output_index == 1):
        return _trace_input_filename(prompt, inputs, "input_any", visited)
    return None


def _trace_any_switch_inverse_pipe_component(
    prompt: Mapping[str, Any] | None,
    inputs: Mapping[str, Any] | None,
    output_index: int,
    component_index: int,
    visited: set[tuple[str, int]],
) -> str | None:
    select = _as_int(_resolve_input_value(inputs, "select"), 1)
    if (select == 1 and output_index == 0) or (select != 1 and output_index == 1):
        return _trace_pipe_input_component(prompt, inputs, "input_any", component_index, visited)
    return None


def _trace_variable_filename(
    prompt: Mapping[str, Any] | None,
    node_id: str,
    inputs: Mapping[str, Any] | None,
    visited: set[tuple[str, int]],
) -> str | None:
    variable_name = _normalize_variable_name(_resolve_input_value(inputs, "name"))
    if not variable_name:
        return None

    source = _resolve_set_variable_source(prompt, variable_name, node_id)
    link = _coerce_link(source)
    if link is not None:
        return _trace_link_filename(prompt, link, visited)
    return _filename_from_value(source)


def _trace_variable_pipe_component(
    prompt: Mapping[str, Any] | None,
    node_id: str,
    inputs: Mapping[str, Any] | None,
    component_index: int,
    visited: set[tuple[str, int]],
) -> str | None:
    variable_name = _normalize_variable_name(_resolve_input_value(inputs, "name"))
    if not variable_name:
        return None

    source = _resolve_set_variable_source(prompt, variable_name, node_id)
    link = _coerce_link(source)
    if link is None:
        return None
    return _trace_pipe_component(prompt, link, component_index, visited)


def _trace_checkpoint_filename(inputs: Mapping[str, Any] | None) -> str | None:
    return _filename_from_value(_find_first_value(inputs, CHECKPOINT_INPUT_KEYS))


def _trace_diffusion_filename(inputs: Mapping[str, Any] | None) -> str | None:
    return _filename_from_value(_find_first_value(inputs, DIFFUSION_INPUT_KEYS))


def _trace_clip_filename(inputs: Mapping[str, Any] | None) -> str | None:
    return _filename_from_value(_find_first_value(inputs, CLIP_INPUT_KEYS))


def _trace_vae_filename(inputs: Mapping[str, Any] | None) -> str | None:
    return _filename_from_value(_find_first_value(inputs, VAE_INPUT_KEYS))


def _trace_checkpoint_vae_output(
    inputs: Mapping[str, Any] | None,
    output_index: int,
) -> str | None:
    if output_index in (1, 2):
        return _filename_from_value(_resolve_input_value(inputs, "checkpoint_model"))
    if output_index == 3:
        vae_value = _resolve_input_value(inputs, "vae_model")
        if str(vae_value or "").strip() == BAKED_VAE_OPTION:
            return _filename_from_value(_resolve_input_value(inputs, "checkpoint_model"))
        return _filename_from_value(vae_value)
    return None


def _trace_model_loader_trio_output(
    inputs: Mapping[str, Any] | None,
    output_index: int,
) -> str | None:
    if output_index == 1:
        return _filename_from_value(_resolve_input_value(inputs, "diffusion_model"))
    if output_index == 2:
        return _filename_from_value(_resolve_input_value(inputs, "clip_model"))
    if output_index == 3:
        return _filename_from_value(_resolve_input_value(inputs, "vae_model"))
    return None


def _trace_filename(
    prompt: Mapping[str, Any] | None,
    node_id: str,
    output_index: int,
    visited: set[tuple[str, int]],
) -> str | None:
    visit_key = (str(node_id), int(output_index))
    if visit_key in visited:
        return None

    visited.add(visit_key)
    try:
        node_info = _resolve_prompt_node(prompt, node_id)
        if node_info is None:
            return None

        class_type = str(node_info.get("class_type") or "")
        inputs = node_info.get("inputs")
        if not isinstance(inputs, Mapping):
            inputs = {}

        if class_type in CHECKPOINT_LOADER_CLASSES and output_index in (0, 1, 2):
            return _trace_checkpoint_filename(inputs)
        if class_type in DIFFUSION_LOADER_CLASSES and output_index == 0:
            return _trace_diffusion_filename(inputs)
        if class_type in CLIP_LOADER_CLASSES and output_index == 0:
            return _trace_clip_filename(inputs)
        if class_type in VAE_LOADER_CLASSES and output_index == 0:
            return _trace_vae_filename(inputs)
        if class_type in MODEL_LOADER_TRIO_CLASSES:
            return _trace_model_loader_trio_output(inputs, output_index)
        if class_type in CHECKPOINT_VAE_LOADER_CLASSES:
            return _trace_checkpoint_vae_output(inputs, output_index)

        if class_type == "PipeBuilder":
            if output_index == 1:
                return _trace_pipe_builder_component(prompt, inputs, PIPE_MODEL_INDEX, visited)
            if output_index == 2:
                return _trace_pipe_builder_component(prompt, inputs, PIPE_CLIP_INDEX, visited)
            if output_index == 3:
                return _trace_pipe_builder_component(prompt, inputs, PIPE_VAE_INDEX, visited)
            return None

        if class_type == "PipeKSamplerFull":
            if output_index == 2:
                return _trace_ksampler_component(prompt, inputs, PIPE_MODEL_INDEX, visited)
            if output_index == 6:
                return _trace_ksampler_component(prompt, inputs, PIPE_VAE_INDEX, visited)
            if output_index == 7:
                return _trace_ksampler_component(prompt, inputs, PIPE_CLIP_INDEX, visited)
            return None

        if class_type == "PipeHiResFix":
            if output_index == 2:
                return _trace_ksampler_component(prompt, inputs, PIPE_MODEL_INDEX, visited)
            if output_index == 6:
                return _trace_ksampler_component(prompt, inputs, PIPE_VAE_INDEX, visited)
            if output_index == 7:
                return _trace_ksampler_component(prompt, inputs, PIPE_CLIP_INDEX, visited)
            return None

        if class_type == "LoraStack5":
            if output_index == 1:
                return _trace_lora_stack_component(prompt, inputs, PIPE_MODEL_INDEX, visited)
            if output_index == 2:
                return _trace_lora_stack_component(prompt, inputs, PIPE_CLIP_INDEX, visited)
            return None

        if class_type == "VeilanceAnySwitch" and output_index == 0:
            return _trace_any_switch_filename(prompt, inputs, visited)

        if class_type == "VeilanceAnySwitchInverse" and output_index in (0, 1):
            return _trace_any_switch_inverse_filename(prompt, inputs, output_index, visited)

        if class_type == SET_VARIABLE_CLASS and output_index == 0:
            return _trace_input_filename(prompt, inputs, "value", visited)

        if class_type == GET_VARIABLE_CLASS and output_index == 0:
            return _trace_variable_filename(prompt, str(node_id), inputs, visited)

        return None
    finally:
        visited.remove(visit_key)


def _trace_pipe_component(
    prompt: Mapping[str, Any] | None,
    pipe_link: Link | None,
    component_index: int,
    visited: set[tuple[str, int]],
) -> str | None:
    if pipe_link is None or component_index not in (PIPE_MODEL_INDEX, PIPE_CLIP_INDEX, PIPE_VAE_INDEX):
        return None

    node_id, output_index = pipe_link
    visit_key = (str(node_id), int(output_index))
    if visit_key in visited:
        return None

    visited.add(visit_key)
    try:
        node_info = _resolve_prompt_node(prompt, node_id)
        if node_info is None:
            return None

        class_type = str(node_info.get("class_type") or "")
        inputs = node_info.get("inputs")
        if not isinstance(inputs, Mapping):
            inputs = {}

        if class_type in MODEL_LOADER_TRIO_CLASSES and output_index == 0:
            return _trace_model_loader_trio_output(inputs, component_index + 1)
        if class_type in CHECKPOINT_VAE_LOADER_CLASSES and output_index == 0:
            return _trace_checkpoint_vae_output(inputs, component_index + 1)
        if class_type == "PipeBuilder" and output_index == 0:
            return _trace_pipe_builder_component(prompt, inputs, component_index, visited)
        if class_type == "PipeRouter" and output_index == 0:
            return _trace_pipe_component(prompt, _resolve_router_pipe_link(inputs), component_index, visited)
        if class_type == "PipeKSamplerFull" and output_index == 0:
            return _trace_ksampler_component(prompt, inputs, component_index, visited)
        if class_type == "PipeHiResFix" and output_index == 0:
            return _trace_ksampler_component(prompt, inputs, component_index, visited)
        if class_type == "LoraStack5" and output_index == 0:
            return _trace_lora_stack_component(prompt, inputs, component_index, visited)
        if class_type == "VeilanceAnySwitch" and output_index == 0:
            return _trace_any_switch_pipe_component(prompt, inputs, component_index, visited)
        if class_type == "VeilanceAnySwitchInverse" and output_index in (0, 1):
            return _trace_any_switch_inverse_pipe_component(
                prompt, inputs, output_index, component_index, visited
            )
        if class_type == SET_VARIABLE_CLASS and output_index == 0:
            return _trace_pipe_input_component(prompt, inputs, "value", component_index, visited)
        if class_type == GET_VARIABLE_CLASS and output_index == 0:
            return _trace_variable_pipe_component(
                prompt, str(node_id), inputs, component_index, visited
            )

        return None
    finally:
        visited.remove(visit_key)


class SourceFilename:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "source": ("*", {"rawLink": True}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("filename",)
    FUNCTION = "get_filename"
    CATEGORY = CATEGORY

    def get_filename(
        self,
        source: Any,
        prompt: Mapping[str, Any] | None = None,
        unique_id: Any = None,
    ):
        del unique_id

        link = _coerce_link(source)
        if link is None:
            return (UNKNOWN_FILENAME,)

        filename = _trace_filename(prompt, link[0], link[1], set())
        return (filename or UNKNOWN_FILENAME,)
