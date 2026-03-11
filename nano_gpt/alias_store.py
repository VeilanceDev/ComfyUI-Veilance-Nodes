"""
Persistent NanoGPT alias configuration + API key helpers.

Non-secret alias settings are stored in JSON.
API keys are stored in the OS keyring backend via `keyring`.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import keyring  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    keyring = None

try:
    from keyring.errors import KeyringError  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    KeyringError = Exception


_LOCK = threading.RLock()
_ALIAS_FILE = Path(__file__).with_name("aliases.json")
_KEYRING_SERVICE = "ComfyUI.Veilance.NanoGPT"

DEFAULT_ALIAS_CONFIG: Dict[str, Any] = {
    "api_provider": "OpenAI",
    "custom_api_url": "",
    "model": "openai/gpt-5.2",
    "temperature": 0.7,
    "max_tokens": 1024,
    "top_p": 1.0,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "response_format": "text",
    "key_source": "keyring",  # keyring | env | none
    "api_key_env": "",
}


def keyring_available() -> bool:
    return keyring is not None


def _normalize_alias_name(name: Any) -> str:
    if name is None:
        return ""
    return str(name).strip()


def _safe_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except Exception:
        return fallback


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def normalize_alias_config(config: Dict[str, Any]) -> Dict[str, Any]:
    cfg = dict(DEFAULT_ALIAS_CONFIG)
    cfg.update(config or {})

    cfg["api_provider"] = str(cfg.get("api_provider", "OpenAI") or "OpenAI").strip()
    cfg["custom_api_url"] = str(cfg.get("custom_api_url", "") or "").strip()
    cfg["model"] = str(cfg.get("model", "openai/gpt-5.2") or "openai/gpt-5.2").strip()
    cfg["temperature"] = _safe_float(cfg.get("temperature"), 0.7)
    cfg["max_tokens"] = max(1, _safe_int(cfg.get("max_tokens"), 1024))
    cfg["top_p"] = _safe_float(cfg.get("top_p"), 1.0)
    cfg["frequency_penalty"] = _safe_float(cfg.get("frequency_penalty"), 0.0)
    cfg["presence_penalty"] = _safe_float(cfg.get("presence_penalty"), 0.0)

    response_format = str(cfg.get("response_format", "text") or "text").strip()
    cfg["response_format"] = (
        response_format if response_format in {"text", "json_object"} else "text"
    )

    key_source = str(cfg.get("key_source", "keyring") or "keyring").strip().lower()
    if key_source not in {"keyring", "env", "none"}:
        key_source = "keyring"
    cfg["key_source"] = key_source
    cfg["api_key_env"] = str(cfg.get("api_key_env", "") or "").strip()
    return cfg


def _read_alias_map_unlocked() -> Dict[str, Dict[str, Any]]:
    if not _ALIAS_FILE.exists():
        return {}

    try:
        data = json.loads(_ALIAS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

    raw_aliases = data.get("aliases", {})
    if not isinstance(raw_aliases, dict):
        return {}

    aliases: Dict[str, Dict[str, Any]] = {}
    for raw_name, raw_cfg in raw_aliases.items():
        name = _normalize_alias_name(raw_name)
        if not name or not isinstance(raw_cfg, dict):
            continue
        aliases[name] = normalize_alias_config(raw_cfg)
    return aliases


def _write_alias_map_unlocked(alias_map: Dict[str, Dict[str, Any]]) -> None:
    payload = {
        "aliases": alias_map,
    }
    _ALIAS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _ALIAS_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(_ALIAS_FILE)


def list_aliases() -> List[Dict[str, Any]]:
    with _LOCK:
        alias_map = _read_alias_map_unlocked()

    result: List[Dict[str, Any]] = []
    for name in sorted(alias_map.keys(), key=lambda value: value.lower()):
        config = dict(alias_map[name])
        has_api_key = False
        key_error = ""

        if config.get("key_source") == "keyring":
            has_api_key, key_error = has_alias_api_key(name)
        elif config.get("key_source") == "env":
            env_name = config.get("api_key_env", "")
            has_api_key = bool(env_name and os.getenv(env_name))
        elif config.get("key_source") == "none":
            has_api_key = False

        result.append(
            {
                "name": name,
                "has_api_key": has_api_key,
                "key_error": key_error,
                **config,
            }
        )
    return result


def get_alias(name: str) -> Optional[Dict[str, Any]]:
    target = _normalize_alias_name(name)
    if not target:
        return None
    with _LOCK:
        alias_map = _read_alias_map_unlocked()
    config = alias_map.get(target)
    if config is None:
        return None
    return dict(config)


def save_alias(name: str, config: Dict[str, Any]) -> None:
    target = _normalize_alias_name(name)
    if not target:
        raise ValueError("Alias name is required.")

    normalized = normalize_alias_config(config)
    with _LOCK:
        alias_map = _read_alias_map_unlocked()
        alias_map[target] = normalized
        _write_alias_map_unlocked(alias_map)


def delete_alias(name: str) -> bool:
    target = _normalize_alias_name(name)
    if not target:
        return False

    removed = False
    with _LOCK:
        alias_map = _read_alias_map_unlocked()
        if target in alias_map:
            del alias_map[target]
            _write_alias_map_unlocked(alias_map)
            removed = True
    return removed


def set_alias_api_key(name: str, api_key: str) -> Tuple[bool, str]:
    target = _normalize_alias_name(name)
    if not target:
        return False, "Alias name is required."
    if not keyring_available():
        return False, "Python package 'keyring' is not installed."

    try:
        keyring.set_password(_KEYRING_SERVICE, target, api_key or "")
        return True, ""
    except KeyringError as exc:
        return False, f"Failed to store API key in keyring: {exc}"
    except Exception as exc:
        return False, f"Failed to store API key: {exc}"


def get_alias_api_key(name: str) -> Tuple[str, str]:
    target = _normalize_alias_name(name)
    if not target:
        return "", "Alias name is required."
    if not keyring_available():
        return "", "Python package 'keyring' is not installed."

    try:
        value = keyring.get_password(_KEYRING_SERVICE, target)
        return (value or ""), ""
    except KeyringError as exc:
        return "", f"Failed to read API key from keyring: {exc}"
    except Exception as exc:
        return "", f"Failed to read API key: {exc}"


def delete_alias_api_key(name: str) -> Tuple[bool, str]:
    target = _normalize_alias_name(name)
    if not target:
        return False, "Alias name is required."
    if not keyring_available():
        return False, "Python package 'keyring' is not installed."

    try:
        keyring.delete_password(_KEYRING_SERVICE, target)
        return True, ""
    except KeyringError as exc:
        # Treat missing credential as success for idempotent deletes.
        message = str(exc).lower()
        if "not found" in message or "no password" in message:
            return True, ""
        return False, f"Failed to delete API key from keyring: {exc}"
    except Exception as exc:
        return False, f"Failed to delete API key: {exc}"


def has_alias_api_key(name: str) -> Tuple[bool, str]:
    value, err = get_alias_api_key(name)
    if err:
        return False, err
    return bool(value), ""
