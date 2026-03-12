"""
NanoGPT text/vision generation node for ComfyUI.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
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
    pass

# Simple in-memory cache
_RESPONSE_CACHE: Dict[str, str] = {}
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


class NanoGPTTextGenerator:
    API_PROVIDERS = {
        "NanoGPT": "https://nano-gpt.com/api/v1",
        "OpenAI": "https://api.openai.com/v1",
        "DeepSeek": "https://api.deepseek.com/v1",
        "Groq": "https://api.groq.com/openai/v1",
        "Local LM Studio": "http://localhost:1234/v1",
        "RunPod/vLLM": "http://localhost:8000/v1",
        "Custom": "",
    }

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "system_prompt": (
                    "STRING",
                    {"multiline": True, "default": "You are a helpful assistant."},
                ),
                "config_mode": (["manual", "alias"], {"default": "manual"}),
                "alias_name": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "e.g. openai-main",
                    },
                ),
                "api_provider": (list(cls.API_PROVIDERS.keys()), {"default": "NanoGPT"}),
                "custom_api_url": ("STRING", {"default": ""}),
                "api_key": ("STRING", {"default": "", "multiline": False}),
                "model": ("STRING", {"default": "openai/gpt-5.2"}),
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
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                "control_after_generate": (
                    ["fixed", "increment", "decrement", "randomize"],
                ),
            },
            "optional": {
                "images": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("text", "messages_json", "prompt_echo")
    FUNCTION = "generate_text"
    CATEGORY = "Veilance/Utils/Prompts"

    def _tensor_to_base64_data_uri(self, input_image: Any) -> str:
        """Converts a ComfyUI image tensor [B, H, W, C] to a base64 encoded jpeg data URI."""
        try:
            image = input_image[0]
            i = 255.0 * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=95)
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{img_str}"
        except Exception as e:
            print(f"[NanoGPT] Error converting image: {e}")
            return ""

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

    def _resolve_effective_settings(
        self,
        config_mode: str,
        alias_name: str,
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
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        manual = {
            "api_provider": api_provider,
            "custom_api_url": custom_api_url,
            "api_key": api_key,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "response_format": response_format,
        }

        if config_mode != "alias":
            return manual, ""

        alias_settings, alias_error = self._resolve_alias_settings(alias_name)
        if alias_error:
            return None, alias_error
        if alias_settings is None:
            return None, "Alias resolution failed."

        # Alias mode only overrides connection/auth details; generation controls stay on-node.
        return {
            "api_provider": manual["api_provider"],
            "custom_api_url": alias_settings.get(
                "custom_api_url", manual["custom_api_url"]
            ),
            "api_key": alias_settings.get("api_key", ""),
            "model": alias_settings.get("model", manual["model"]),
            "temperature": manual["temperature"],
            "max_tokens": manual["max_tokens"],
            "top_p": manual["top_p"],
            "frequency_penalty": manual["frequency_penalty"],
            "presence_penalty": manual["presence_penalty"],
            "response_format": manual["response_format"],
        }, ""

    def generate_text(
        self,
        prompt: str,
        system_prompt: str,
        config_mode: str,
        alias_name: str,
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
        control_after_generate: str,
        images: Optional[Any] = None,
    ) -> Tuple[str, str, str]:
        settings, settings_error = self._resolve_effective_settings(
            config_mode=config_mode,
            alias_name=alias_name,
            api_provider=api_provider,
            custom_api_url=custom_api_url,
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            response_format=response_format,
        )
        if settings_error:
            return (f"Error: {settings_error}", "[]", prompt)
        if settings is None:
            return ("Error: Failed to resolve settings.", "[]", prompt)

        api_provider = str(settings["api_provider"])
        custom_api_url = str(settings["custom_api_url"])
        api_key = str(settings["api_key"])
        model = str(settings["model"])
        temperature = float(settings["temperature"])
        max_tokens = int(settings["max_tokens"])
        top_p = float(settings["top_p"])
        frequency_penalty = float(settings["frequency_penalty"])
        presence_penalty = float(settings["presence_penalty"])
        response_format = str(settings["response_format"])

        base_url = (custom_api_url or "").strip().rstrip("/")
        if not base_url:
            base_url = self.API_PROVIDERS.get(api_provider, "").rstrip("/")

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
            base64_uri = self._tensor_to_base64_data_uri(images)
            if base64_uri:
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

        cache_key_data = json.dumps(data, sort_keys=True) + base_url
        cache_hash = hashlib.sha256(cache_key_data.encode("utf-8")).hexdigest()
        if cache_hash in _RESPONSE_CACHE:
            print(f"[NanoGPT] Returning cached response for seed {seed}")
            return (_RESPONSE_CACHE[cache_hash], messages_json_str, prompt)

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
                        _RESPONSE_CACHE[cache_hash] = text
                        return (text, messages_json_str, prompt)
                    error_msg = f"Error: Unexpected response format: {result}"
                    return (error_msg, messages_json_str, prompt)
            except urllib.error.HTTPError as e:
                status = e.code
                error_body = e.read().decode("utf-8")
                if status in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    print(
                        f"[NanoGPT] Attempt {attempt + 1}/{max_retries} failed "
                        f"with {status}. Retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return (f"HTTP {status} API Error: {error_body}", messages_json_str, prompt)
            except urllib.error.URLError as e:
                if attempt < max_retries - 1:
                    print(
                        f"[NanoGPT] URLError on attempt {attempt + 1}/{max_retries}: "
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


def _alias_payload_from_request(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str]:
    config = alias_store.normalize_alias_config(
        {
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
    "NanoGPTTextGenerator": NanoGPTTextGenerator,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NanoGPTTextGenerator": "NanoGPT Text Generator",
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
                        and not _is_local_api_url(config.get("custom_api_url", ""))
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
