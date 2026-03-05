"""
NanoGPT text generation node for ComfyUI.
"""

import json
import urllib.request
from typing import Any, Dict, Tuple


class NanoGPTTextGenerator:
    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "system_prompt": (
                    "STRING",
                    {"multiline": True, "default": "You are a helpful assistant."},
                ),
                "api_key": ("STRING", {"default": ""}),
                "api_url": ("STRING", {"default": "https://nano-gpt.com/api/v1"}),
                "model": ("STRING", {"default": "openai/gpt-5.2"}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1}),
                "max_tokens": ("INT", {"default": 1024, "min": 1, "max": 8192, "step": 1}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "generate_text"
    CATEGORY = "Veilance/Utils/Prompts"

    def generate_text(
        self,
        prompt: str,
        system_prompt: str,
        api_key: str,
        api_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> Tuple[str]:
        if not api_key:
            return ("Error: API key is required",)

        if not prompt:
            return ("",)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        url = f"{api_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode("utf-8"))
                
                if "choices" in result and len(result["choices"]) > 0:
                    text = result["choices"][0].get("message", {}).get("content", "")
                    return (text,)
                else:
                    return (f"Error: Unexpected response format: {result}",)
        except Exception as e:
            return (f"Error calling API: {str(e)}",)


NODE_CLASS_MAPPINGS = {
    "NanoGPTTextGenerator": NanoGPTTextGenerator,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NanoGPTTextGenerator": "NanoGPT Text Generator",
}
