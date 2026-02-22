"""
Seed Strategy node for ComfyUI.
Generates seeds using multiple strategies.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import List


class SeedStrategy:
    _MIN_SEED = 0
    _MAX_SEED = 0xFFFFFFFFFFFFFFFF
    _SEED_SPACE = _MAX_SEED + 1

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (
                    ["fixed", "random", "increment", "hash_prompt", "cycle_list"],
                    {"default": "fixed"},
                ),
                "base_seed": (
                    "INT",
                    {"default": 0, "min": cls._MIN_SEED, "max": cls._MAX_SEED, "step": 1},
                ),
                "step": ("INT", {"default": 1, "min": 1, "max": 1_000_000, "step": 1}),
                "run_index": (
                    "INT",
                    {"default": 0, "min": 0, "max": 1_000_000_000, "step": 1},
                ),
                "prompt": ("STRING", {"default": "", "multiline": True}),
                "seed_list": ("STRING", {"default": "0, 1, 2, 3", "multiline": True}),
                "random_min": (
                    "INT",
                    {"default": 0, "min": cls._MIN_SEED, "max": cls._MAX_SEED, "step": 1},
                ),
                "random_max": (
                    "INT",
                    {"default": cls._MAX_SEED, "min": cls._MIN_SEED, "max": cls._MAX_SEED, "step": 1},
                ),
            },
        }

    RETURN_TYPES = ("INT", "STRING")
    RETURN_NAMES = ("seed", "strategy_info")
    FUNCTION = "generate_seed"
    CATEGORY = "Veilance/Sampling"

    @classmethod
    def IS_CHANGED(cls, mode, **kwargs):
        if str(mode) == "random":
            return float("nan")
        return (
            str(mode),
            int(kwargs.get("base_seed", 0)),
            int(kwargs.get("step", 1)),
            int(kwargs.get("run_index", 0)),
            str(kwargs.get("prompt", "")),
            str(kwargs.get("seed_list", "")),
            int(kwargs.get("random_min", 0)),
            int(kwargs.get("random_max", cls._MAX_SEED)),
        )

    @classmethod
    def _normalize_seed(cls, value: int) -> int:
        return int(value) % cls._SEED_SPACE

    @classmethod
    def _parse_seed_list(cls, seed_list: str) -> List[int]:
        normalized = str(seed_list).replace("\n", ",").replace(";", ",")
        values = []
        for token in normalized.split(","):
            stripped = token.strip()
            if not stripped:
                continue
            try:
                values.append(cls._normalize_seed(int(stripped)))
            except ValueError:
                continue
        return values

    def generate_seed(
        self,
        mode,
        base_seed,
        step,
        run_index,
        prompt,
        seed_list,
        random_min,
        random_max,
    ):
        mode_name = str(mode)
        base = self._normalize_seed(int(base_seed))
        increment = max(1, int(step))
        index = max(0, int(run_index))

        random_low = self._normalize_seed(int(random_min))
        random_high = self._normalize_seed(int(random_max))
        if random_high < random_low:
            random_low, random_high = random_high, random_low

        if mode_name == "fixed":
            seed = base
            info = f"fixed:{seed}"
        elif mode_name == "random":
            span = random_high - random_low + 1
            seed = random_low + secrets.randbelow(span)
            info = f"random:{seed} [{random_low},{random_high}]"
        elif mode_name == "increment":
            seed = self._normalize_seed(base + (index * increment))
            info = f"increment:{seed} base={base} step={increment} index={index}"
        elif mode_name == "hash_prompt":
            digest = hashlib.sha256(str(prompt).encode("utf-8")).digest()
            hash_seed = int.from_bytes(digest[:8], "big", signed=False)
            seed = self._normalize_seed(hash_seed)
            info = f"hash_prompt:{seed}"
        elif mode_name == "cycle_list":
            values = self._parse_seed_list(seed_list)
            if not values:
                seed = base
                info = f"cycle_list:fallback_base:{seed}"
            else:
                list_index = index % len(values)
                seed = values[list_index]
                info = f"cycle_list:{seed} idx={list_index}/{len(values)}"
        else:
            seed = base
            info = f"fixed:{seed}"

        return (int(seed), info)


NODE_CLASS_MAPPINGS = {
    "SeedStrategy": SeedStrategy,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SeedStrategy": "Seed Strategy",
}
