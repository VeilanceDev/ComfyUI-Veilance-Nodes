from __future__ import annotations

from typing import Any, List, Tuple

from ..comfy_reflection import extract_options, resolve_node_class
from .constants import CATEGORY


def _seed_input_with_control(seed_input_spec: Any) -> Any:
    if isinstance(seed_input_spec, tuple) and len(seed_input_spec) > 1:
        metadata = seed_input_spec[1]
        if isinstance(metadata, dict):
            updated_metadata = dict(metadata)
            updated_metadata["control_after_generate"] = True
            return (seed_input_spec[0], updated_metadata)
    return seed_input_spec


def _available_ksampler_options() -> Tuple[List[str], List[str]]:
    fallback_samplers = ["euler", "euler_a", "dpmpp_2m", "lcm"]
    fallback_schedulers = ["normal", "karras", "simple", "sgm_uniform"]

    try:
        ksampler_class = resolve_node_class("KSampler", ("KSampler",))
    except RuntimeError:
        return fallback_samplers, fallback_schedulers

    try:
        required_inputs = ksampler_class.INPUT_TYPES().get("required", {})
        if not isinstance(required_inputs, dict):
            return fallback_samplers, fallback_schedulers
    except Exception:
        return fallback_samplers, fallback_schedulers

    sampler_options = extract_options(required_inputs.get("sampler_name"))
    scheduler_options = extract_options(required_inputs.get("scheduler"))
    return (
        sampler_options or fallback_samplers,
        scheduler_options or fallback_schedulers,
    )


class GlobalSamplerScheduler:
    @classmethod
    def INPUT_TYPES(cls):
        sampler_options, scheduler_options = _available_ksampler_options()
        return {
            "required": {
                "sampler_name": (sampler_options, {"default": sampler_options[0]}),
                "scheduler": (scheduler_options, {"default": scheduler_options[0]}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("sampler_name", "scheduler")
    FUNCTION = "output_values"
    CATEGORY = CATEGORY

    def output_values(self, sampler_name: str, scheduler: str):
        return (str(sampler_name), str(scheduler))


class GlobalSeed:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": _seed_input_with_control(
                    (
                        "INT",
                        {
                            "default": 0,
                            "min": 0,
                            "max": 0xFFFFFFFFFFFFFFFF,
                        },
                    )
                ),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("seed",)
    FUNCTION = "output_seed"
    CATEGORY = CATEGORY

    def output_seed(self, seed: int):
        return (int(seed),)
