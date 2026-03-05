"""
NanoGPT text/vision generation node for ComfyUI.
"""

import json
import urllib.request
import urllib.error
import time
import base64
import io
import hashlib
from typing import Any, Dict, Tuple, List, Optional

try:
    import torch
    from PIL import Image
    import numpy as np
except ImportError:
    pass

# Simple in-memory cache
_RESPONSE_CACHE: Dict[str, str] = {}


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
                "api_provider": (list(cls.API_PROVIDERS.keys()), {"default": "NanoGPT"}),
                "custom_api_url": ("STRING", {"default": ""}),
                "api_key": ("STRING", {"default": ""}),
                "model": ("STRING", {"default": "openai/gpt-5.2"}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1}),
                "max_tokens": ("INT", {"default": 1024, "min": 1, "max": 8192, "step": 1}),
                "top_p": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "frequency_penalty": ("FLOAT", {"default": 0.0, "min": -2.0, "max": 2.0, "step": 0.1}),
                "presence_penalty": ("FLOAT", {"default": 0.0, "min": -2.0, "max": 2.0, "step": 0.1}),
                "response_format": (["text", "json_object"], {"default": "text"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "control_after_generate": (["fixed", "increment", "decrement", "randomize"],),
            },
            "optional": {
                "images": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("text", "messages_json", "prompt_echo")
    FUNCTION = "generate_text"
    CATEGORY = "Veilance/Utils/Prompts"

    def _tensor_to_base64_data_uri(self, input_image: Any) -> str:
        """Converts a ComfyUI image tensor [B, H, W, C] to a base64 encoded jpeg data URI."""
        try:
            # Take the first image in the batch
            image = input_image[0]
            # Convert to numpy array [H, W, C]
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            
            # Save to BytesIO
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=95)
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{img_str}"
        except Exception as e:
            print(f"[NanoGPT] Error converting image: {e}")
            return ""

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
        control_after_generate: str,
        images: Optional[Any] = None,
    ) -> Tuple[str, str, str]:
        
        # Determine API URL
        if api_provider == "Custom":
            base_url = custom_api_url.rstrip('/')
        else:
            base_url = self.API_PROVIDERS.get(api_provider, "").rstrip('/')

        if not base_url:
            return ("Error: A valid API URL must be provided.", "[]", prompt)

        if api_provider != "Local LM Studio" and not api_key:
            return ("Error: API key is required for this provider.", "[]", prompt)

        if not prompt:
            return ("", "[]", "")

        # Construct messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Render User Prompt with Image if provided
        user_content = []
        user_content.append({"type": "text", "text": prompt})

        if images is not None:
            # We assume ComfyUI passes a batch of images [B, H, W, C]
            # Convert first one to base64
            base64_uri = self._tensor_to_base64_data_uri(images)
            if base64_uri:
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": base64_uri
                    }
                })

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

        # Serialize debug data early
        messages_json_str = json.dumps(messages, indent=2)

        # Check Cache
        # We hash the data payload (which includes everything relevant to output except api details) + url
        cache_key_data = json.dumps(data, sort_keys=True) + base_url
        cache_hash = hashlib.sha256(cache_key_data.encode('utf-8')).hexdigest()

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
                # Add a timeout to prevent hanging forever
                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    
                    if "choices" in result and len(result["choices"]) > 0:
                        text = result["choices"][0].get("message", {}).get("content", "")
                        
                        # Save to cache
                        _RESPONSE_CACHE[cache_hash] = text
                        
                        return (text, messages_json_str, prompt)
                    else:
                        error_msg = f"Error: Unexpected response format: {result}"
                        return (error_msg, messages_json_str, prompt)
                        
            except urllib.error.HTTPError as e:
                status = e.code
                error_body = e.read().decode("utf-8")
                
                # Retry on 429 Too Many Requests or 5xx Server Errors
                if status in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    print(f"[NanoGPT] Attempt {attempt + 1}/{max_retries} failed with {status}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    return (f"HTTP {status} API Error: {error_body}", messages_json_str, prompt)
            
            except urllib.error.URLError as e:
                if attempt < max_retries - 1:
                    print(f"[NanoGPT] URLError on attempt {attempt + 1}/{max_retries}: {e.reason}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return (f"URL Error: Could not connect to API ({e.reason})", messages_json_str, prompt)
            
            except Exception as e:
                # For generic unhandled exceptions
                return (f"Error calling API: {str(e)}", messages_json_str, prompt)

        return ("Error: Maximum retries reached.", messages_json_str, prompt)


NODE_CLASS_MAPPINGS = {
    "NanoGPTTextGenerator": NanoGPTTextGenerator,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NanoGPTTextGenerator": "NanoGPT Text Generator",
}
