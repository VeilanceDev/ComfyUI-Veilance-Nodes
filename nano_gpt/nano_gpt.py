"""
LLM text/vision generation nodes for ComfyUI.
"""

from __future__ import annotations

import base64
from collections import OrderedDict
import hashlib
import io
import json
import os
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from typing import Any, Dict, Optional, Tuple

from . import alias_store

try:
    import torch  # noqa: F401
    from PIL import Image
    import numpy as np
except ImportError:
    torch = None  # type: ignore
    Image = None  # type: ignore
    np = None  # type: ignore

_RESPONSE_CACHE_MAX_SIZE = 128
_RESPONSE_CACHE_TTL_SECONDS = 300.0
_RESPONSE_CACHE: "OrderedDict[str, Tuple[float, str]]" = OrderedDict()
_RESPONSE_CACHE_LOCK = threading.RLock()
_LOCAL_API_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _is_local_api_url(url: str) -> bool:
    candidate = str(url or "").strip()
    if not candidate:
        return False
    try:
        parsed = urlparse(candidate if "://" in candidate else f"http://{candidate}")
        host = (parsed.hostname or "").lower()
    except Exception:
        return False
    return host in _LOCAL_API_HOSTS


def _cache_prune_unlocked(now: Optional[float] = None) -> None:
    current_time = time.time() if now is None else now

    expired_keys = [
        cache_key
        for cache_key, (created_at, _) in _RESPONSE_CACHE.items()
        if current_time - created_at >= _RESPONSE_CACHE_TTL_SECONDS
    ]
    for cache_key in expired_keys:
        _RESPONSE_CACHE.pop(cache_key, None)

    while len(_RESPONSE_CACHE) > _RESPONSE_CACHE_MAX_SIZE:
        _RESPONSE_CACHE.popitem(last=False)


def _response_cache_get(cache_key: str) -> Optional[str]:
    now = time.time()
    with _RESPONSE_CACHE_LOCK:
        cache_entry = _RESPONSE_CACHE.get(cache_key)
        if cache_entry is None:
            _cache_prune_unlocked(now)
            return None

        created_at, cached_text = cache_entry
        if now - created_at >= _RESPONSE_CACHE_TTL_SECONDS:
            _RESPONSE_CACHE.pop(cache_key, None)
            _cache_prune_unlocked(now)
            return None

        _RESPONSE_CACHE.move_to_end(cache_key)
        return cached_text


def _response_cache_set(cache_key: str, text: str) -> None:
    now = time.time()
    with _RESPONSE_CACHE_LOCK:
        _cache_prune_unlocked(now)
        _RESPONSE_CACHE[cache_key] = (now, text)
        _RESPONSE_CACHE.move_to_end(cache_key)
        _cache_prune_unlocked(now)


def _api_key_fingerprint(api_key: str) -> str:
    if not api_key:
        return ""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


def _resolve_base_url(
    api_provider: str,
    custom_api_url: str,
    api_providers: Dict[str, str],
) -> str:
    base_url = str(custom_api_url or "").strip().rstrip("/")
    if base_url:
        return base_url
    return str(api_providers.get(str(api_provider or ""), "") or "").strip().rstrip("/")


def _alias_name_input_spec() -> Tuple[list[str], Dict[str, Any]]:
    aliases = [entry.get("name", "") for entry in alias_store.list_aliases()]
    alias_names = [str(name).strip() for name in aliases if str(name).strip()]
    if not alias_names:
        return ([""], {"default": ""})
    return (alias_names, {"default": alias_names[0]})


def _seed_input_with_control(seed_input_spec: Any) -> Any:
    if isinstance(seed_input_spec, tuple) and len(seed_input_spec) > 1:
        metadata = seed_input_spec[1]
        if isinstance(metadata, dict):
            updated_metadata = dict(metadata)
            updated_metadata["control_after_generate"] = True
            return (seed_input_spec[0], updated_metadata)
    return seed_input_spec


def _build_response_cache_key(
    *,
    data: Dict[str, Any],
    base_url: str,
    api_provider: str,
    config_mode: str,
    alias_name: str,
    api_key: str,
) -> str:
    cache_scope = {
        "base_url": base_url,
        "api_provider": api_provider,
        "config_mode": config_mode,
        "alias_name": (alias_name or "").strip() if config_mode == "alias" else "",
        "api_key_fingerprint": _api_key_fingerprint(api_key),
    }
    cache_key_data = json.dumps(
        {
            "request": data,
            "scope": cache_scope,
        },
        sort_keys=True,
    )
    return hashlib.sha256(cache_key_data.encode("utf-8")).hexdigest()


class _BaseLLMTextGenerator:
    API_PROVIDERS = {
        "NanoGPT": "https://nano-gpt.com/api/v1",
        "OpenAI": "https://api.openai.com/v1",
        "DeepSeek": "https://api.deepseek.com/v1",
        "Groq": "https://api.groq.com/openai/v1",
        "Local LM Studio": "http://localhost:1234/v1",
        "RunPod/vLLM": "http://localhost:8000/v1",
        "Custom": "",
    }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("text", "messages_json", "prompt_echo")
    FUNCTION = "generate_text"
    CATEGORY = "Veilance/Utils/Prompts"

    @classmethod
    def _base_required_inputs(cls) -> Dict[str, Any]:
        return {
            "prompt": ("STRING", {"multiline": True, "default": ""}),
            "system_prompt": (
                "STRING",
                {"multiline": True, "default": "You are a helpful assistant."},
            ),
            "temperature": (
                "FLOAT",
                {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1},
            ),
            "max_tokens": (
                "INT",
                {"default": 1024, "min": 1, "max": 8192, "step": 1},
            ),
            "top_p": (
                "FLOAT",
                {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05},
            ),
            "frequency_penalty": (
                "FLOAT",
                {"default": 0.0, "min": -2.0, "max": 2.0, "step": 0.1},
            ),
            "presence_penalty": (
                "FLOAT",
                {"default": 0.0, "min": -2.0, "max": 2.0, "step": 0.1},
            ),
            "response_format": (["text", "json_object"], {"default": "text"}),
            "seed": _seed_input_with_control(
                ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF})
            ),
        }

    @staticmethod
    def _image_dependency_error() -> str:
        missing = []
        if Image is None:
            missing.append("Pillow")
        if np is None:
            missing.append("numpy")

        return (
            "LLM Text Generator image input requires the following runtime dependencies: "
            + ", ".join(missing)
        )

    def _tensor_to_base64_data_uri(self, input_image: Any) -> Tuple[Optional[str], str]:
        """Convert a ComfyUI image tensor [B, H, W, C] to a base64-encoded JPEG data URI."""
        if Image is None or np is None:
            return None, self._image_dependency_error()

        try:
            image = input_image[0]
            i = 255.0 * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=95)
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{img_str}", ""
        except Exception as e:
            print(f"[LLMTextGenerator] Error converting image: {e}")
            return None, f"Failed to encode image input: {e}"

    def _resolve_alias_settings(self, alias_name: str) -> Tuple[Optional[Dict[str, Any]], str]:
        alias_name = (alias_name or "").strip()
        if not alias_name:
            return None, "Alias mode requires a non-empty alias_name."

        alias_cfg = alias_store.get_alias(alias_name)
        if alias_cfg is None:
            return None, f"Alias '{alias_name}' was not found."

        key_source = alias_cfg.get("key_source", "keyring")
        api_key = ""
        if key_source == "keyring":
            api_key, key_err = alias_store.get_alias_api_key(alias_name)
            if key_err:
                return None, key_err
        elif key_source == "env":
            env_name = (alias_cfg.get("api_key_env") or "").strip()
            if not env_name:
                return None, (
                    f"Alias '{alias_name}' uses env key source but api_key_env is empty."
                )
            api_key = os.getenv(env_name, "")
        elif key_source == "none":
            api_key = ""
        else:
            return None, f"Alias '{alias_name}' has invalid key_source '{key_source}'."

        settings = dict(alias_cfg)
        settings["api_key"] = api_key
        return settings, ""

    def _generate_with_settings(
        self,
        *,
        prompt: str,
        system_prompt: str,
        api_provider: str,
        custom_api_url: str,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        frequency_penalty: float,
        presence_penalty: float,
        response_format: str,
        seed: int,
        mode_name: str,
        alias_name: str = "",
        images: Optional[Any] = None,
    ) -> Tuple[str, str, str]:
        base_url = _resolve_base_url(api_provider, custom_api_url, self.API_PROVIDERS)
        if not base_url:
            return ("Error: A valid API URL must be provided.", "[]", prompt)

        key_optional = api_provider == "Local LM Studio" or _is_local_api_url(base_url)
        if not key_optional and not api_key:
            return (
                "Error: API key is required for this provider. "
                "If using alias mode, ensure alias key source/key is configured.",
                "[]",
                prompt,
            )

        if not prompt:
            return ("", "[]", "")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_content = [{"type": "text", "text": prompt}]

        if images is not None:
            base64_uri, image_error = self._tensor_to_base64_data_uri(images)
            if image_error:
                return (f"Error: {image_error}", "[]", prompt)
            if base64_uri is not None:
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": base64_uri,
                        },
                    }
                )

        messages.append({"role": "user", "content": user_content})

        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "seed": seed,
        }

        if response_format == "json_object":
            data["response_format"] = {"type": "json_object"}

        messages_json_str = json.dumps(messages, indent=2)

        cache_hash = _build_response_cache_key(
            data=data,
            base_url=base_url,
            api_provider=api_provider,
            config_mode=mode_name,
            alias_name=alias_name,
            api_key=api_key,
        )
        cached_text = _response_cache_get(cache_hash)
        if cached_text is not None:
            print(f"[LLMTextGenerator] Returning cached response for seed {seed}")
            return (cached_text, messages_json_str, prompt)

        url = f"{base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        max_retries = 3
        retry_delay = 2.0
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    if "choices" in result and len(result["choices"]) > 0:
                        text = result["choices"][0].get("message", {}).get("content", "")
                        _response_cache_set(cache_hash, text)
                        return (text, messages_json_str, prompt)
                    error_msg = f"Error: Unexpected response format: {result}"
                    return (error_msg, messages_json_str, prompt)
            except urllib.error.HTTPError as e:
                status = e.code
                error_body = e.read().decode("utf-8")
                if status in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    print(
                        f"[LLMTextGenerator] Attempt {attempt + 1}/{max_retries} failed "
                        f"with {status}. Retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return (f"HTTP {status} API Error: {error_body}", messages_json_str, prompt)
            except urllib.error.URLError as e:
                if attempt < max_retries - 1:
                    print(
                        f"[LLMTextGenerator] URLError on attempt {attempt + 1}/{max_retries}: "
                        f"{e.reason}. Retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return (
                    f"URL Error: Could not connect to API ({e.reason})",
                    messages_json_str,
                    prompt,
                )
            except Exception as e:
                return (f"Error calling API: {str(e)}", messages_json_str, prompt)

        return ("Error: Maximum retries reached.", messages_json_str, prompt)


class LLMTextGeneratorManual(_BaseLLMTextGenerator):
    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        required = cls._base_required_inputs()
        manual_inputs = {
            "api_provider": (list(cls.API_PROVIDERS.keys()), {"default": "NanoGPT"}),
            "custom_api_url": ("STRING", {"default": ""}),
            "api_key": ("STRING", {"default": "", "multiline": False}),
            "model": ("STRING", {"default": "openai/gpt-5.2"}),
        }
        return {
            "required": {
                "prompt": required["prompt"],
                "system_prompt": required["system_prompt"],
                **manual_inputs,
                "temperature": required["temperature"],
                "max_tokens": required["max_tokens"],
                "top_p": required["top_p"],
                "frequency_penalty": required["frequency_penalty"],
                "presence_penalty": required["presence_penalty"],
                "response_format": required["response_format"],
                "seed": required["seed"],
            },
            "optional": {
                "images": ("IMAGE",),
            },
        }

    def generate_text(
        self,
        prompt: str,
        system_prompt: str,
        api_provider: str,
        custom_api_url: str,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        frequency_penalty: float,
        presence_penalty: float,
        response_format: str,
        seed: int,
        images: Optional[Any] = None,
    ) -> Tuple[str, str, str]:
        return self._generate_with_settings(
            prompt=prompt,
            system_prompt=system_prompt,
            api_provider=str(api_provider),
            custom_api_url=str(custom_api_url),
            api_key=str(api_key),
            model=str(model),
            temperature=float(temperature),
            max_tokens=int(max_tokens),
            top_p=float(top_p),
            frequency_penalty=float(frequency_penalty),
            presence_penalty=float(presence_penalty),
            response_format=str(response_format),
            seed=int(seed),
            mode_name="manual",
            images=images,
        )


class LLMTextGeneratorAlias(_BaseLLMTextGenerator):
    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        required = cls._base_required_inputs()
        return {
            "required": {
                "prompt": required["prompt"],
                "system_prompt": required["system_prompt"],
                "alias_name": _alias_name_input_spec(),
                "temperature": required["temperature"],
                "max_tokens": required["max_tokens"],
                "top_p": required["top_p"],
                "frequency_penalty": required["frequency_penalty"],
                "presence_penalty": required["presence_penalty"],
                "response_format": required["response_format"],
                "seed": required["seed"],
            },
            "optional": {
                "images": ("IMAGE",),
            },
        }

    def generate_text(
        self,
        prompt: str,
        system_prompt: str,
        alias_name: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        frequency_penalty: float,
        presence_penalty: float,
        response_format: str,
        seed: int,
        images: Optional[Any] = None,
    ) -> Tuple[str, str, str]:
        settings, settings_error = self._resolve_alias_settings(alias_name)
        if settings_error:
            return (f"Error: {settings_error}", "[]", prompt)
        if settings is None:
            return ("Error: Failed to resolve alias settings.", "[]", prompt)

        return self._generate_with_settings(
            prompt=prompt,
            system_prompt=system_prompt,
            api_provider=str(settings.get("api_provider", "NanoGPT")),
            custom_api_url=str(settings.get("custom_api_url", "")),
            api_key=str(settings.get("api_key", "")),
            model=str(settings.get("model", "openai/gpt-5.2")),
            temperature=float(temperature),
            max_tokens=int(max_tokens),
            top_p=float(top_p),
            frequency_penalty=float(frequency_penalty),
            presence_penalty=float(presence_penalty),
            response_format=str(response_format),
            seed=int(seed),
            mode_name="alias",
            alias_name=str(alias_name or "").strip(),
            images=images,
        )


def _alias_payload_from_request(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str]:
    config = alias_store.normalize_alias_config(
        {
            "api_provider": payload.get("api_provider", "NanoGPT"),
            "custom_api_url": payload.get("custom_api_url", ""),
            "model": payload.get("model", "openai/gpt-5.2"),
            "key_source": payload.get("key_source", "keyring"),
            "api_key_env": payload.get("api_key_env", ""),
        }
    )
    alias_name = str(payload.get("name", "") or "").strip()
    api_key = str(payload.get("api_key", "") or "")
    return config, alias_name, api_key


NODE_CLASS_MAPPINGS = {
    "LLMTextGeneratorManual": LLMTextGeneratorManual,
    "LLMTextGeneratorAlias": LLMTextGeneratorAlias,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LLMTextGeneratorManual": "LLM Text Generator (Manual)",
    "LLMTextGeneratorAlias": "LLM Text Generator (Alias)",
}


try:
    from aiohttp import web
    from server import PromptServer

    @PromptServer.instance.routes.get("/veilance/nano_gpt/aliases")
    async def get_nanogpt_aliases(request):
        try:
            aliases = alias_store.list_aliases()
            return web.json_response(
                {
                    "status": "ok",
                    "aliases": aliases,
                    "keyring_available": alias_store.keyring_available(),
                }
            )
        except Exception as exc:
            return web.json_response(
                {"status": "error", "message": str(exc)},
                status=500,
            )

    @PromptServer.instance.routes.post("/veilance/nano_gpt/aliases/upsert")
    async def upsert_nanogpt_alias(request):
        try:
            payload = await request.json()
            config, alias_name, api_key = _alias_payload_from_request(payload)
            clear_api_key = bool(payload.get("clear_api_key", False))

            if not alias_name:
                return web.json_response(
                    {"status": "error", "message": "Alias name is required."},
                    status=400,
                )

            if config["key_source"] == "env" and not config["api_key_env"]:
                return web.json_response(
                    {
                        "status": "error",
                        "message": "api_key_env is required when key_source is 'env'.",
                    },
                    status=400,
                )

            if config["key_source"] == "keyring":
                if clear_api_key:
                    ok, err = alias_store.delete_alias_api_key(alias_name)
                    if not ok:
                        return web.json_response(
                            {"status": "error", "message": err},
                            status=400,
                        )

                if api_key:
                    ok, err = alias_store.set_alias_api_key(alias_name, api_key)
                    if not ok:
                        return web.json_response(
                            {"status": "error", "message": err},
                            status=400,
                        )
                else:
                    has_key, key_err = alias_store.has_alias_api_key(alias_name)
                    if key_err:
                        return web.json_response(
                            {"status": "error", "message": key_err},
                            status=400,
                        )
                    if (
                        not has_key
                        and not _is_local_api_url(
                            _resolve_base_url(
                                str(config.get("api_provider", "NanoGPT")),
                                str(config.get("custom_api_url", "")),
                                _BaseLLMTextGenerator.API_PROVIDERS,
                            )
                        )
                    ):
                        return web.json_response(
                            {
                                "status": "error",
                                "message": (
                                    "No keyring API key set for this alias. "
                                    "Provide api_key to store one."
                                ),
                            },
                            status=400,
                        )

            if config["key_source"] != "keyring":
                # Ensure old keyring credentials do not remain active for aliases moved to env/none.
                alias_store.delete_alias_api_key(alias_name)

            alias_store.save_alias(alias_name, config)
            return web.json_response(
                {
                    "status": "ok",
                    "alias": alias_name,
                    "aliases": alias_store.list_aliases(),
                }
            )
        except Exception as exc:
            return web.json_response(
                {"status": "error", "message": str(exc)},
                status=500,
            )

    @PromptServer.instance.routes.post("/veilance/nano_gpt/aliases/delete")
    async def delete_nanogpt_alias(request):
        try:
            payload = await request.json()
            alias_name = str(payload.get("name", "") or "").strip()
            if not alias_name:
                return web.json_response(
                    {"status": "error", "message": "Alias name is required."},
                    status=400,
                )

            removed = alias_store.delete_alias(alias_name)
            alias_store.delete_alias_api_key(alias_name)
            if not removed:
                return web.json_response(
                    {"status": "error", "message": f"Alias '{alias_name}' not found."},
                    status=404,
                )

            return web.json_response(
                {
                    "status": "ok",
                    "deleted": alias_name,
                    "aliases": alias_store.list_aliases(),
                }
            )
        except Exception as exc:
            return web.json_response(
                {"status": "error", "message": str(exc)},
                status=500,
            )

except Exception as e:
    print(f"[NanoGPT] Could not register alias API routes: {e}")
