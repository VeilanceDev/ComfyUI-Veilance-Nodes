"""
Prompt Cleaner node for ComfyUI.
"""

from __future__ import annotations


class PromptCleaner:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"default": "", "multiline": True}),
                "trim_trailing_spaces_commas": ("BOOLEAN", {"default": True}),
                "replace_underscores_with_spaces": ("BOOLEAN", {"default": False}),
                "remove_duplicate_tags": ("BOOLEAN", {"default": True}),
                "convert_to_lowercase": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("cleaned_prompt",)
    FUNCTION = "clean_prompt"
    CATEGORY = "Veilance/Utils/Prompts"

    @staticmethod
    def _prepare_text(
        text: str,
        replace_underscores_with_spaces: bool,
        convert_to_lowercase: bool,
        trim_trailing_spaces_commas: bool,
    ) -> str:
        result = text
        if replace_underscores_with_spaces:
            result = result.replace("_", " ")
        if convert_to_lowercase:
            result = result.lower()
        if trim_trailing_spaces_commas:
            result = result.rstrip(" ,\t\r\n")
        return result

    @staticmethod
    def _clean_tags(
        text: str,
        trim_trailing_spaces_commas: bool,
        remove_duplicate_tags: bool,
    ) -> str:
        tags = text.split(",")
        cleaned_tags = []
        seen = set()

        for tag in tags:
            normalized = tag.strip()
            output_tag = normalized if trim_trailing_spaces_commas else tag

            if trim_trailing_spaces_commas and not normalized:
                continue

            if remove_duplicate_tags:
                dedupe_key = normalized
                if not dedupe_key:
                    continue
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

            cleaned_tags.append(output_tag)

        if trim_trailing_spaces_commas:
            return ", ".join(cleaned_tags).rstrip(" ,\t\r\n")
        return ",".join(cleaned_tags)

    def clean_prompt(
        self,
        prompt: str,
        trim_trailing_spaces_commas: bool,
        replace_underscores_with_spaces: bool,
        remove_duplicate_tags: bool,
        convert_to_lowercase: bool,
    ):
        cleaned = self._prepare_text(
            text=prompt or "",
            replace_underscores_with_spaces=replace_underscores_with_spaces,
            convert_to_lowercase=convert_to_lowercase,
            trim_trailing_spaces_commas=trim_trailing_spaces_commas,
        )

        cleaned = self._clean_tags(
            text=cleaned,
            trim_trailing_spaces_commas=trim_trailing_spaces_commas,
            remove_duplicate_tags=remove_duplicate_tags,
        )
        return (cleaned,)


NODE_CLASS_MAPPINGS = {
    "PromptCleaner": PromptCleaner,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptCleaner": "Prompt Cleaner",
}
