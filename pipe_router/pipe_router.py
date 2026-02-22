"""
Pipe Router node for ComfyUI.
Routes between two PIPE inputs.
"""

from __future__ import annotations

from typing import Any, Tuple


class PipeRouter:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "route": (["A", "B"], {"default": "A"}),
                "fallback_to_other": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "pipe_a": ("PIPE",),
                "pipe_b": ("PIPE",),
            },
        }

    RETURN_TYPES = ("PIPE", "STRING")
    RETURN_NAMES = ("pipe", "selected_route")
    FUNCTION = "route_pipe"
    CATEGORY = "Veilance/Pipe"

    @staticmethod
    def _as_pipe_tuple(pipe: Any) -> Tuple[Any, ...] | None:
        if pipe is None:
            return None
        if isinstance(pipe, tuple):
            return pipe
        if isinstance(pipe, list):
            return tuple(pipe)
        return (pipe,)

    def route_pipe(self, route, fallback_to_other, pipe_a=None, pipe_b=None):
        route_upper = str(route).upper()
        selected = pipe_a if route_upper == "A" else pipe_b
        selected_route = "A" if route_upper == "A" else "B"

        if selected is None and bool(fallback_to_other):
            selected = pipe_b if selected_route == "A" else pipe_a
            selected_route = "B" if selected_route == "A" else "A"

        pipe_out = self._as_pipe_tuple(selected)
        if pipe_out is None:
            raise RuntimeError(
                f"PipeRouter could not resolve route '{selected_route}'. "
                "Connect at least one of pipe_a or pipe_b."
            )

        return (pipe_out, selected_route)


NODE_CLASS_MAPPINGS = {
    "PipeRouter": PipeRouter,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PipeRouter": "Pipe Router",
}
