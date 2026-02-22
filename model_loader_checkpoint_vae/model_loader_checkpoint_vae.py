"""
Checkpoint + VAE loader node for ComfyUI.
Loads MODEL/CLIP from checkpoint and allows selecting baked VAE or an external VAE file.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Tuple


def _resolve_loader_class(display_name: str, fallback_class_names: Iterable[str]):
    import nodes  # type: ignore

    for class_name in fallback_class_names:
        loader_class = nodes.NODE_CLASS_MAPPINGS.get(class_name)
        if loader_class is not None:
            return loader_class

    for class_name, mapped_display_name in nodes.NODE_DISPLAY_NAME_MAPPINGS.items():
        if mapped_display_name == display_name:
            loader_class = nodes.NODE_CLASS_MAPPINGS.get(class_name)
            if loader_class is not None:
                return loader_class

    raise RuntimeError(
        f"Could not find ComfyUI loader node for '{display_name}'. "
        f"Checked fallback class names: {list(fallback_class_names)}."
    )


def _get_required_inputs(loader_class) -> Dict[str, Any]:
    input_types = loader_class.INPUT_TYPES()
    required_inputs = input_types.get("required", {})
    if not isinstance(required_inputs, dict):
        return {}
    return required_inputs


def _extract_default_value(input_spec: Any) -> Any:
    if isinstance(input_spec, tuple) and len(input_spec) > 1:
        config = input_spec[1]
        if isinstance(config, dict):
            return config.get("default")
    return None


def _find_first_input(
    required_inputs: Dict[str, Any],
    candidates: Iterable[str],
) -> Tuple[Optional[str], Any]:
    for name in candidates:
        if name in required_inputs:
            return name, required_inputs[name]
    return None, None


def _build_loader_kwargs(
    required_inputs: Dict[str, Any],
    explicit_values: Dict[str, Any],
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}
    for input_name, input_spec in required_inputs.items():
        if input_name in explicit_values and explicit_values[input_name] is not None:
            kwargs[input_name] = explicit_values[input_name]
            continue

        default_value = _extract_default_value(input_spec)
        if default_value is not None:
            kwargs[input_name] = default_value
            continue

        raise RuntimeError(
            f"Required loader input '{input_name}' has no explicit value and no default."
        )
    return kwargs


def _run_loader(loader_class, kwargs: Dict[str, Any]) -> Tuple[Any, ...]:
    loader = loader_class()
    function_name = getattr(loader_class, "FUNCTION", None) or getattr(
        loader, "FUNCTION", None
    )
    if not function_name:
        raise RuntimeError(f"Loader class '{loader_class.__name__}' has no FUNCTION.")

    loader_fn = getattr(loader, function_name)
    result = loader_fn(**kwargs)

    if isinstance(result, tuple):
        return result
    if isinstance(result, list):
        return tuple(result)
    return (result,)


class ModelLoaderCheckpointVAE:
    _BAKED_OPTION = "(baked)"

    _CHECKPOINT_MODEL_KEYS = ("ckpt_name", "checkpoint", "model_name")
    _VAE_MODEL_KEYS = ("vae_name", "model_name")

    @classmethod
    def _resolve_checkpoint_config(cls) -> Dict[str, Any]:
        checkpoint_class = _resolve_loader_class(
            "Load Checkpoint",
            ("CheckpointLoaderSimple", "CheckpointLoader"),
        )
        required_inputs = _get_required_inputs(checkpoint_class)
        model_key, model_input = _find_first_input(
            required_inputs, cls._CHECKPOINT_MODEL_KEYS
        )
        if model_key is None:
            raise RuntimeError(
                "Could not resolve the checkpoint model input key from "
                f"{list(required_inputs.keys())}."
            )

        return {
            "class": checkpoint_class,
            "required": required_inputs,
            "model_key": model_key,
            "model_input": model_input,
        }

    @classmethod
    def _resolve_vae_config(cls) -> Dict[str, Any]:
        vae_class = _resolve_loader_class(
            "Load VAE",
            ("VAELoader",),
        )
        required_inputs = _get_required_inputs(vae_class)
        model_key, model_input = _find_first_input(required_inputs, cls._VAE_MODEL_KEYS)
        if model_key is None:
            raise RuntimeError(
                "Could not resolve the VAE model input key from "
                f"{list(required_inputs.keys())}."
            )

        return {
            "class": vae_class,
            "required": required_inputs,
            "model_key": model_key,
            "model_input": model_input,
        }

    @classmethod
    def _vae_input_with_baked_option(cls):
        config = cls._resolve_vae_config()
        model_input = config["model_input"]

        if isinstance(model_input, tuple) and model_input:
            options = model_input[0]
            if isinstance(options, (list, tuple)):
                normalized = [cls._BAKED_OPTION]
                for option in options:
                    option_text = str(option)
                    if option_text != cls._BAKED_OPTION:
                        normalized.append(option_text)

                metadata = {}
                if len(model_input) > 1 and isinstance(model_input[1], dict):
                    metadata = dict(model_input[1])
                metadata["default"] = cls._BAKED_OPTION
                return (normalized, metadata)

        return ([cls._BAKED_OPTION], {"default": cls._BAKED_OPTION})

    @classmethod
    def INPUT_TYPES(cls):
        checkpoint_config = cls._resolve_checkpoint_config()
        return {
            "required": {
                "checkpoint_model": checkpoint_config["model_input"],
                "vae_model": cls._vae_input_with_baked_option(),
            },
            "optional": {
                "pipe": ("PIPE",),
            },
        }

    RETURN_TYPES = ("PIPE", "MODEL", "CLIP", "VAE")
    RETURN_NAMES = ("pipe", "model", "clip", "vae")
    FUNCTION = "load_models"
    CATEGORY = "Veilance/Loaders"

    @staticmethod
    def _pipe_tail(pipe: Any, replaced_items: int) -> Tuple[Any, ...]:
        if isinstance(pipe, tuple):
            return pipe[replaced_items:]
        if isinstance(pipe, list):
            return tuple(pipe[replaced_items:])
        return ()

    @classmethod
    def _load_checkpoint(cls, checkpoint_model):
        checkpoint_config = cls._resolve_checkpoint_config()
        checkpoint_kwargs = _build_loader_kwargs(
            checkpoint_config["required"],
            {
                checkpoint_config["model_key"]: checkpoint_model,
            },
        )
        checkpoint_outputs = _run_loader(
            checkpoint_config["class"], checkpoint_kwargs
        )
        if len(checkpoint_outputs) < 3:
            raise RuntimeError(
                "Load Checkpoint returned an unexpected output format; "
                "expected at least (MODEL, CLIP, VAE)."
            )
        return checkpoint_outputs[0], checkpoint_outputs[1], checkpoint_outputs[2]

    @classmethod
    def _load_vae(cls, vae_model):
        vae_config = cls._resolve_vae_config()
        vae_kwargs = _build_loader_kwargs(
            vae_config["required"],
            {
                vae_config["model_key"]: vae_model,
            },
        )
        vae_outputs = _run_loader(vae_config["class"], vae_kwargs)
        if not vae_outputs:
            raise RuntimeError("Load VAE returned no outputs.")
        return vae_outputs[0]

    def load_models(self, checkpoint_model, vae_model, pipe=None):
        model, clip, baked_vae = self._load_checkpoint(checkpoint_model)

        vae_model_text = (
            self._BAKED_OPTION if vae_model is None else str(vae_model).strip()
        )
        use_baked_vae = (
            not vae_model_text or vae_model_text == self._BAKED_OPTION
        )

        vae = baked_vae if use_baked_vae else self._load_vae(vae_model_text)
        if use_baked_vae and vae is None:
            raise RuntimeError(
                "Selected baked VAE, but checkpoint did not provide one. "
                "Pick an external VAE in 'vae_model'."
            )

        pipe_out = (model, clip, vae, *self._pipe_tail(pipe, 3))
        return (pipe_out, model, clip, vae)


NODE_CLASS_MAPPINGS = {
    "ModelLoaderCheckpointVAE": ModelLoaderCheckpointVAE,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelLoaderCheckpointVAE": "Load Checkpoint + VAE",
}
