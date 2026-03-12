"""
LoRA Stack node for ComfyUI.
Applies up to 5 LoRA models sequentially.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from ..comfy_reflection import (
    build_required_kwargs,
    find_first_input,
    get_required_inputs,
    resolve_node_class,
    run_node,
)


class LoraStack5:
    _DISABLED_OPTION = "(disabled)"
    _SLOT_COUNT = 5

    _PIPE_MODEL_INDEX = 0
    _PIPE_CLIP_INDEX = 1
    _PIPE_VAE_INDEX = 2
    _PIPE_POSITIVE_INDEX = 3
    _PIPE_NEGATIVE_INDEX = 4
    _PIPE_LATENT_INDEX = 5
    _PIPE_SEED_INDEX = 6
    _PIPE_CORE_LENGTH = 7

    _LORA_MODEL_KEYS = ("model",)
    _LORA_CLIP_KEYS = ("clip",)
    _LORA_NAME_KEYS = ("lora_name", "lora")
    _LORA_STRENGTH_MODEL_KEYS = ("strength_model", "model_strength")
    _LORA_STRENGTH_CLIP_KEYS = ("strength_clip", "clip_strength")

    @classmethod
    def _resolve_lora_loader_config(cls) -> Dict[str, Any]:
        lora_loader_class = resolve_node_class("Load LoRA", ("LoraLoader",))
        required_inputs = get_required_inputs(lora_loader_class)

        model_key, _ = find_first_input(required_inputs, cls._LORA_MODEL_KEYS)
        clip_key, _ = find_first_input(required_inputs, cls._LORA_CLIP_KEYS)
        lora_key, lora_input = find_first_input(required_inputs, cls._LORA_NAME_KEYS)
        strength_model_key, strength_model_input = find_first_input(
            required_inputs, cls._LORA_STRENGTH_MODEL_KEYS
        )
        strength_clip_key, strength_clip_input = find_first_input(
            required_inputs, cls._LORA_STRENGTH_CLIP_KEYS
        )

        missing = []
        for key_name, resolved in (
            ("model", model_key),
            ("clip", clip_key),
            ("lora_name", lora_key),
            ("strength_model", strength_model_key),
            ("strength_clip", strength_clip_key),
        ):
            if resolved is None:
                missing.append(key_name)
        if missing:
            raise RuntimeError(
                "Could not resolve Load LoRA required input keys for: "
                + ", ".join(missing)
                + f". Available keys: {list(required_inputs.keys())}."
            )

        return {
            "class": lora_loader_class,
            "required": required_inputs,
            "model_key": model_key,
            "clip_key": clip_key,
            "lora_key": lora_key,
            "lora_input": lora_input,
            "strength_model_key": strength_model_key,
            "strength_model_input": strength_model_input,
            "strength_clip_key": strength_clip_key,
            "strength_clip_input": strength_clip_input,
        }

    @classmethod
    def _disabled_lora_input_spec(cls) -> Any:
        config = cls._resolve_lora_loader_config()
        lora_input = config["lora_input"]

        if isinstance(lora_input, tuple) and lora_input:
            options = lora_input[0]
            if isinstance(options, (list, tuple)):
                normalized = [cls._DISABLED_OPTION]
                for option in options:
                    option_text = str(option)
                    if option_text != cls._DISABLED_OPTION:
                        normalized.append(option_text)

                metadata = {}
                if len(lora_input) > 1 and isinstance(lora_input[1], dict):
                    metadata = dict(lora_input[1])
                metadata["default"] = cls._DISABLED_OPTION
                return (normalized, metadata)

        return ([cls._DISABLED_OPTION], {"default": cls._DISABLED_OPTION})

    @staticmethod
    def _fallback_strength_input_spec(default_value: float) -> Any:
        return (
            "FLOAT",
            {
                "default": default_value,
                "min": -20.0,
                "max": 20.0,
                "step": 0.05,
            },
        )

    @classmethod
    def _single_strength_input_spec(cls, config: Dict[str, Any]) -> Any:
        strength_spec = (
            config["strength_model_input"]
            if config["strength_model_input"] is not None
            else config["strength_clip_input"]
        )
        if strength_spec is None:
            return cls._fallback_strength_input_spec(1.0)

        if isinstance(strength_spec, tuple) and len(strength_spec) > 1:
            first = strength_spec[0]
            metadata = strength_spec[1] if isinstance(strength_spec[1], dict) else {}
            normalized_meta = dict(metadata)
            if "default" not in normalized_meta:
                normalized_meta["default"] = 1.0
            return (first, normalized_meta)

        return strength_spec

    @classmethod
    def INPUT_TYPES(cls):
        config = cls._resolve_lora_loader_config()
        lora_spec = cls._disabled_lora_input_spec()
        strength_spec = cls._single_strength_input_spec(config)

        required: Dict[str, Any] = {
            "active_lora_slots": (
                "INT",
                {
                    "default": 1,
                    "min": 1,
                    "max": cls._SLOT_COUNT,
                    "step": 1,
                },
            ),
        }
        for index in range(1, cls._SLOT_COUNT + 1):
            required[f"lora_name_{index}"] = lora_spec
            required[f"lora_strength_{index}"] = strength_spec

        return {
            "required": required,
            "optional": {
                "pipe": ("PIPE",),
                "model": ("MODEL",),
                "clip": ("CLIP",),
            },
        }

    RETURN_TYPES = ("PIPE", "MODEL", "CLIP")
    RETURN_NAMES = ("pipe", "model", "clip")
    FUNCTION = "apply_stack"
    CATEGORY = "Veilance/Loaders"

    @staticmethod
    def _pipe_item(pipe: Any, index: int) -> Any:
        if isinstance(pipe, tuple):
            return pipe[index] if len(pipe) > index else None
        if isinstance(pipe, list):
            return pipe[index] if len(pipe) > index else None
        return None

    @classmethod
    def _pipe_tail(cls, pipe: Any) -> Tuple[Any, ...]:
        if isinstance(pipe, tuple):
            return pipe[cls._PIPE_CORE_LENGTH :]
        if isinstance(pipe, list):
            return tuple(pipe[cls._PIPE_CORE_LENGTH :])
        return ()

    @classmethod
    def _apply_single_lora(
        cls,
        model,
        clip,
        lora_name: str,
        strength: float,
    ):
        config = cls._resolve_lora_loader_config()
        kwargs = build_required_kwargs(
            config["required"],
            {
                config["model_key"]: model,
                config["clip_key"]: clip,
                config["lora_key"]: lora_name,
                config["strength_model_key"]: float(strength),
                config["strength_clip_key"]: float(strength),
            },
        )
        result = run_node(config["class"], kwargs)
        if len(result) < 2:
            raise RuntimeError(
                "Load LoRA node returned an unexpected output format; "
                "expected at least (MODEL, CLIP)."
            )
        return result[0], result[1]

    def apply_stack(
        self,
        active_lora_slots,
        lora_name_1,
        lora_strength_1,
        lora_name_2,
        lora_strength_2,
        lora_name_3,
        lora_strength_3,
        lora_name_4,
        lora_strength_4,
        lora_name_5,
        lora_strength_5,
        pipe=None,
        model=None,
        clip=None,
    ):
        model_value = (
            model if model is not None else self._pipe_item(pipe, self._PIPE_MODEL_INDEX)
        )
        clip_value = clip if clip is not None else self._pipe_item(pipe, self._PIPE_CLIP_INDEX)

        if model_value is None or clip_value is None:
            raise RuntimeError(
                "LoraStack5 requires MODEL and CLIP. Provide model+clip inputs or a pipe containing both."
            )

        slot_count = max(1, min(self._SLOT_COUNT, int(active_lora_slots)))
        slots = (
            (lora_name_1, lora_strength_1),
            (lora_name_2, lora_strength_2),
            (lora_name_3, lora_strength_3),
            (lora_name_4, lora_strength_4),
            (lora_name_5, lora_strength_5),
        )

        for lora_name, strength in slots[:slot_count]:
            lora_name_text = str(lora_name)
            if not lora_name_text or lora_name_text == self._DISABLED_OPTION:
                continue

            lora_strength = float(strength)
            if lora_strength == 0.0:
                continue

            model_value, clip_value = self._apply_single_lora(
                model=model_value,
                clip=clip_value,
                lora_name=lora_name_text,
                strength=lora_strength,
            )

        pipe_out = (
            model_value,
            clip_value,
            self._pipe_item(pipe, self._PIPE_VAE_INDEX),
            self._pipe_item(pipe, self._PIPE_POSITIVE_INDEX),
            self._pipe_item(pipe, self._PIPE_NEGATIVE_INDEX),
            self._pipe_item(pipe, self._PIPE_LATENT_INDEX),
            self._pipe_item(pipe, self._PIPE_SEED_INDEX),
            *self._pipe_tail(pipe),
        )

        return (
            pipe_out,
            model_value,
            clip_value,
        )


NODE_CLASS_MAPPINGS = {
    "LoraStack5": LoraStack5,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoraStack5": "LoRA Stack",
}
