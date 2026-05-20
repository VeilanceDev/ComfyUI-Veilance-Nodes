"""
Shared helpers for Veilance PIPE payloads.
"""

from __future__ import annotations

from typing import Any, Tuple


PIPE_MODEL_INDEX = 0
PIPE_CLIP_INDEX = 1
PIPE_VAE_INDEX = 2
PIPE_POSITIVE_INDEX = 3
PIPE_NEGATIVE_INDEX = 4
PIPE_LATENT_INDEX = 5
PIPE_SEED_INDEX = 6
PIPE_CORE_LENGTH = 7


def pipe_item(pipe: Any, index: int) -> Any:
    if isinstance(pipe, tuple):
        return pipe[index] if len(pipe) > index else None
    if isinstance(pipe, list):
        return pipe[index] if len(pipe) > index else None
    return None


def pipe_tail(pipe: Any, start_index: int = PIPE_CORE_LENGTH) -> Tuple[Any, ...]:
    if isinstance(pipe, tuple):
        return pipe[start_index:]
    if isinstance(pipe, list):
        return tuple(pipe[start_index:])
    return ()

