from __future__ import annotations

from typing import Any, Mapping

from .constants import CATEGORY

SET_VARIABLE_CLASS = "VeilanceSetVariable"


def _normalize_variable_name(name: Any) -> str:
    return str(name or "").strip()


def _coerce_link(value: Any) -> list[Any] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    node_id, output_index = value
    if not isinstance(node_id, (str, int)):
        return None
    if not isinstance(output_index, (int, float)):
        return None
    return [str(node_id), int(output_index)]


def _build_passthrough_result(value: Any) -> dict[str, Any]:
    from comfy_execution.graph_utils import GraphBuilder

    graph = GraphBuilder()
    passthrough = graph.node("VeilanceAnySwitch", select=1, input_1=value)
    return {
        "result": (passthrough.out(0),),
        "expand": graph.finalize(),
    }


def _resolve_prompt_node(prompt: Mapping[str, Any] | None, node_id: Any) -> Mapping[str, Any] | None:
    if not isinstance(prompt, Mapping):
        return None

    candidates = [node_id]
    if node_id is not None:
        candidates.append(str(node_id))

    for candidate in candidates:
        if candidate in prompt:
            node_info = prompt[candidate]
            if isinstance(node_info, Mapping):
                return node_info
    return None


def _resolve_variable_source(
    prompt: Mapping[str, Any] | None,
    variable_name: str,
    current_node_id: Any,
) -> Any:
    if not isinstance(prompt, Mapping):
        raise RuntimeError("Get Variable requires ComfyUI prompt metadata during execution.")

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

    if not matches:
        raise RuntimeError(f"No Set Variable node found for '{variable_name}'.")

    if len(matches) > 1:
        duplicate_ids = ", ".join(node_id for node_id, _ in matches)
        raise RuntimeError(
            f"Multiple Set Variable nodes found for '{variable_name}': {duplicate_ids}."
        )

    node_id, inputs = matches[0]
    if "value" not in inputs:
        raise RuntimeError(f"Set Variable '{variable_name}' on node {node_id} has no value.")

    value = inputs["value"]
    link = _coerce_link(value)
    if link is not None:
        return link
    return value


class SetVariable:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "name": ("STRING", {"default": "", "placeholder": "my_variable"}),
                "value": ("*", {"rawLink": True}),
            }
        }

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("value",)
    FUNCTION = "set_value"
    CATEGORY = CATEGORY

    @classmethod
    def VALIDATE_INPUTS(cls, input_types):
        return True

    def set_value(self, name: str, value: Any):
        variable_name = _normalize_variable_name(name)
        if not variable_name:
            raise RuntimeError("Set Variable requires a non-empty variable name.")

        link = _coerce_link(value)
        if link is not None:
            return _build_passthrough_result(link)
        return (value,)


class GetVariable:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "name": ("STRING", {"default": "", "placeholder": "my_variable"}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("value",)
    FUNCTION = "get_value"
    CATEGORY = CATEGORY

    def get_value(self, name: str, prompt: Mapping[str, Any] | None = None, unique_id: Any = None):
        variable_name = _normalize_variable_name(name)
        if not variable_name:
            raise RuntimeError("Get Variable requires a non-empty variable name.")

        current_node = _resolve_prompt_node(prompt, unique_id)
        if current_node is not None:
            current_inputs = current_node.get("inputs")
            if isinstance(current_inputs, Mapping):
                current_name = _normalize_variable_name(current_inputs.get("name"))
                if current_name and current_name != variable_name:
                    variable_name = current_name

        source = _resolve_variable_source(prompt, variable_name, unique_id)
        link = _coerce_link(source)
        if link is not None:
            return _build_passthrough_result(link)
        return (source,)
