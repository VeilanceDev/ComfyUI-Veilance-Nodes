"""
Sampler Presets node for ComfyUI.
Outputs KSampler parameter sets from curated presets.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple


def _resolve_node_class(display_name: str, fallback_class_names: Iterable[str]):
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

    return None


def _extract_options(input_spec: Any) -> List[str]:
    if isinstance(input_spec, tuple) and input_spec:
        values = input_spec[0]
        if isinstance(values, (list, tuple)):
            return [str(value) for value in values]
    return []


class SamplerPresets:
    _PRESETS: Dict[str, Dict[str, Any]] = {
        "Balanced": {
            "steps": 28,
            "cfg": 6.5,
            "denoise": 1.0,
            "sampler_candidates": ("dpmpp_2m", "dpmpp_2m_sde", "euler"),
            "scheduler_candidates": ("karras", "normal"),
        },
        "Fast Draft": {
            "steps": 16,
            "cfg": 5.5,
            "denoise": 1.0,
            "sampler_candidates": ("euler_a", "euler_ancestral", "euler"),
            "scheduler_candidates": ("normal", "simple"),
        },
        "High Detail": {
            "steps": 40,
            "cfg": 7.0,
            "denoise": 1.0,
            "sampler_candidates": ("dpmpp_2m_sde", "dpmpp_sde", "dpmpp_3m_sde"),
            "scheduler_candidates": ("karras", "normal"),
        },
        "Turbo/LCM": {
            "steps": 8,
            "cfg": 2.0,
            "denoise": 1.0,
            "sampler_candidates": ("lcm", "euler_a", "euler"),
            "scheduler_candidates": ("sgm_uniform", "normal", "simple"),
        },
        "Img2Img Refine": {
            "steps": 24,
            "cfg": 6.0,
            "denoise": 0.55,
            "sampler_candidates": ("dpmpp_2m", "dpmpp_2m_sde", "euler"),
            "scheduler_candidates": ("karras", "normal"),
        },
    }

    _SAMPLER_ALIASES: Dict[str, Tuple[str, ...]] = {
        "euler_a": ("euler_ancestral",),
        "euler_ancestral": ("euler_a",),
    }

    _SCHEDULER_ALIASES: Dict[str, Tuple[str, ...]] = {}

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "preset": (list(cls._PRESETS.keys()), {"default": "Balanced"}),
                "steps_offset": ("INT", {"default": 0, "min": -200, "max": 200, "step": 1}),
                "cfg_offset": (
                    "FLOAT",
                    {"default": 0.0, "min": -20.0, "max": 20.0, "step": 0.1},
                ),
                "denoise_override": (
                    "FLOAT",
                    {"default": -1.0, "min": -1.0, "max": 1.0, "step": 0.01},
                ),
            },
        }

    RETURN_TYPES = ("INT", "FLOAT", "STRING", "STRING", "FLOAT", "STRING")
    RETURN_NAMES = ("steps", "cfg", "sampler_name", "scheduler", "denoise", "preset_name")
    FUNCTION = "apply_preset"
    CATEGORY = "Veilance/Sampling"

    @staticmethod
    def _available_ksampler_options() -> Tuple[List[str], List[str]]:
        fallback_samplers = ["euler", "euler_a", "dpmpp_2m", "lcm"]
        fallback_schedulers = ["normal", "karras", "simple", "sgm_uniform"]

        ksampler_class = _resolve_node_class("KSampler", ("KSampler",))
        if ksampler_class is None:
            return fallback_samplers, fallback_schedulers

        try:
            required_inputs = ksampler_class.INPUT_TYPES().get("required", {})
            if not isinstance(required_inputs, dict):
                return fallback_samplers, fallback_schedulers
        except Exception:
            return fallback_samplers, fallback_schedulers

        sampler_options = _extract_options(required_inputs.get("sampler_name"))
        scheduler_options = _extract_options(required_inputs.get("scheduler"))
        return (
            sampler_options or fallback_samplers,
            scheduler_options or fallback_schedulers,
        )

    @staticmethod
    def _choose_option(
        available: Sequence[str],
        candidates: Sequence[str],
        aliases: Dict[str, Tuple[str, ...]],
    ) -> str:
        if not available:
            return str(candidates[0])

        available_map = {value.lower(): value for value in available}
        for candidate in candidates:
            resolved = available_map.get(candidate.lower())
            if resolved is not None:
                return resolved

            for alias in aliases.get(candidate, ()):
                resolved = available_map.get(alias.lower())
                if resolved is not None:
                    return resolved

        return str(available[0])

    def apply_preset(self, preset, steps_offset, cfg_offset, denoise_override):
        preset_name = str(preset)
        config = self._PRESETS.get(preset_name)
        if config is None:
            raise RuntimeError(f"Unknown preset '{preset_name}'.")

        available_samplers, available_schedulers = self._available_ksampler_options()

        sampler_name = self._choose_option(
            available_samplers,
            config["sampler_candidates"],
            self._SAMPLER_ALIASES,
        )
        scheduler = self._choose_option(
            available_schedulers,
            config["scheduler_candidates"],
            self._SCHEDULER_ALIASES,
        )

        steps = max(1, int(round(float(config["steps"]) + float(steps_offset))))
        cfg = max(0.0, float(config["cfg"]) + float(cfg_offset))

        denoise = float(config["denoise"])
        if float(denoise_override) >= 0.0:
            denoise = float(denoise_override)
        denoise = min(1.0, max(0.0, denoise))

        return (steps, cfg, sampler_name, scheduler, denoise, preset_name)


NODE_CLASS_MAPPINGS = {
    "SamplerPresets": SamplerPresets,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SamplerPresets": "Sampler Presets",
}
