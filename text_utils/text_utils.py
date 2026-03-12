import textwrap

class StringCombiner:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "delimiter": ("STRING", {"default": ", "}),
            },
            "optional": {
                "string_1": ("STRING", {"forceInput": True}),
                "string_2": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("string",)
    FUNCTION = "combine"
    CATEGORY = "Veilance/Utils/Prompts"

    def combine(self, delimiter=", ", **kwargs):
        # Sort keys to maintain correct order (string_1, string_2, etc.)
        strings = []
        for key in sorted(kwargs.keys()):
            if key.startswith("string_") and isinstance(kwargs[key], str):
                s = kwargs[key].strip()
                if s:
                    strings.append(s)
        
        return (delimiter.join(strings), )

class TextSearchAndReplace:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True}),
            },
            "optional": {
                "search_1": ("STRING", {"default": ""}),
                "replace_1": ("STRING", {"default": ""}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "replace"
    CATEGORY = "Veilance/Utils/Prompts"

    def replace(self, text="", **kwargs):
        if not text:
            return ("",)

        result = text
        # Find all search/replace pairs based on key index
        indices = set()
        for key in kwargs.keys():
            if key.startswith("search_"):
                indices.add(key.split("_")[1])
            elif key.startswith("replace_"):
                indices.add(key.split("_")[1])
        
        for idx in sorted(list(indices), key=lambda x: int(x) if x.isdigit() else 0):
            search_str = kwargs.get(f"search_{idx}", "")
            replace_str = kwargs.get(f"replace_{idx}", "")
            if search_str:
                result = result.replace(search_str, replace_str)
                
        return (result,)

NODE_CLASS_MAPPINGS = {
    "VeilanceStringCombiner": StringCombiner,
    "VeilanceTextSearchAndReplace": TextSearchAndReplace,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VeilanceStringCombiner": "String Combiner",
    "VeilanceTextSearchAndReplace": "Text Search & Replace",
}
