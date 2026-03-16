"""
Shared ComfyUI reflection helpers used by compatibility wrapper nodes.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple


def resolve_node_class(display_name: str, fallback_class_names: Iterable[str]):
    import nodes  # type: ignore

    for class_name in fallback_class_names:
        node_class = nodes.NODE_CLASS_MAPPINGS.get(class_name)
        if node_class is not None:
            return node_class

    for class_name, mapped_display_name in nodes.NODE_DISPLAY_NAME_MAPPINGS.items():
        if mapped_display_name == display_name:
            node_class = nodes.NODE_CLASS_MAPPINGS.get(class_name)
            if node_class is not None:
                return node_class

    raise RuntimeError(
        f"Could not find ComfyUI node for '{display_name}'. "
        f"Checked fallback class names: {list(fallback_class_names)}."
    )


def get_required_inputs(node_class) -> Dict[str, Any]:
    input_types = node_class.INPUT_TYPES()
    required_inputs = input_types.get("required", {})
    if not isinstance(required_inputs, dict):
        return {}
    return required_inputs


def extract_default_value(input_spec: Any) -> Any:
    if isinstance(input_spec, tuple) and len(input_spec) > 1:
        config = input_spec[1]
        if isinstance(config, dict):
            return config.get("default")
    return None


def find_first_input(
    required_inputs: Dict[str, Any],
    candidates: Iterable[str],
) -> Tuple[Optional[str], Any]:
    for name in candidates:
        if name in required_inputs:
            return name, required_inputs[name]
    return None, None


def build_required_kwargs(
    required_inputs: Dict[str, Any],
    explicit_values: Dict[str, Any],
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}
    for input_name, input_spec in required_inputs.items():
        if input_name in explicit_values and explicit_values[input_name] is not None:
            kwargs[input_name] = explicit_values[input_name]
            continue

        default_value = extract_default_value(input_spec)
        if default_value is not None:
            kwargs[input_name] = default_value
            continue

        raise RuntimeError(
            f"Required node input '{input_name}' has no explicit value and no default."
        )
    return kwargs


def run_node(node_class, kwargs: Dict[str, Any]) -> Tuple[Any, ...]:
    node = node_class()
    function_name = getattr(node_class, "FUNCTION", None) or getattr(
        node, "FUNCTION", None
    )
    if not function_name:
        raise RuntimeError(f"Node class '{node_class.__name__}' has no FUNCTION.")

    node_fn = getattr(node, function_name)
    result = node_fn(**kwargs)

    node_result = getattr(result, "result", None)
    if hasattr(result, "args") and node_result is not None:
        if isinstance(node_result, tuple):
            return node_result
        if isinstance(node_result, list):
            return tuple(node_result)
        return (node_result,)
    if isinstance(result, tuple):
        return result
    if isinstance(result, list):
        return tuple(result)
    return (result,)


def extract_options(input_spec: Any) -> List[str]:
    if isinstance(input_spec, tuple) and input_spec:
        values = input_spec[0]
        if isinstance(values, (list, tuple)):
            return [str(value) for value in values]
    return []
