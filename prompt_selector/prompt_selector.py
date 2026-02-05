"""
Prompt Selector Nodes for ComfyUI
Dynamically generates one node per folder, each prompt file becomes a dropdown widget.
Supports both YAML and CSV formats. Outputs both positive and negative prompts.
"""

from .file_utils import (
    get_all_category_data,
    get_prompt_from_file,
    get_file_dropdown_options,
    refresh_cache,
    discover_categories,
    get_cache_checksum,
    DISABLED_OPTION,
    RANDOM_OPTION,
)

# Register custom API route for refresh functionality
try:
    from server import PromptServer
    from aiohttp import web
    
    @PromptServer.instance.routes.post('/prompt_selector/refresh')
    async def refresh_prompt_lists(request):
        """API endpoint to refresh the prompt cache."""
        try:
            data = refresh_cache()
            category_count = len(data)
            file_count = sum(len(files) for files in data.values())
            prompt_count = sum(
                len(prompts) 
                for files in data.values() 
                for prompts in files.values()
            )
            return web.json_response({
                "status": "ok",
                "categories": category_count,
                "files": file_count,
                "prompts": prompt_count
            })
        except Exception as e:
            return web.json_response({
                "status": "error",
                "message": str(e)
            }, status=500)
            
except Exception as e:
    print(f"[PromptSelector] Could not register API route: {e}")


def create_category_node_class(category_name: str):
    """
    Factory function to create a node class for a specific category.
    
    Each category folder gets its own node class, and each YAML file
    in that folder becomes a dropdown widget on the node.
    """
    
    class CategoryPromptNode:
        """
        Dynamically generated node for a prompt category.
        Each YAML file in the folder becomes a dropdown with its prompts.
        Outputs both positive and negative prompts.
        """
        
        _category = category_name
        
        def __init__(self):
            pass
        
        @classmethod
        def INPUT_TYPES(cls):
            """
            Generate inputs based on YAML files in this category.
            Each YAML file becomes a dropdown widget.
            """
            inputs = {
                "required": {
                    "separator": ("STRING", {
                        "default": ", ",
                        "multiline": False,
                    }),
                },
                "optional": {},
            }
            
            data = get_all_category_data()
            
            if cls._category not in data:
                return inputs
            
            files_data = data[cls._category]
            
            for filename, prompts in files_data.items():
                options = get_file_dropdown_options(cls._category, filename)
                
                inputs["optional"][filename] = (options, {
                    "default": DISABLED_OPTION,
                })
            
            return inputs
        
        RETURN_TYPES = ("STRING", "STRING")
        RETURN_NAMES = ("positive", "negative")
        FUNCTION = "select_prompts"
        CATEGORY = "utils/prompts"
        
        @classmethod
        def IS_CHANGED(cls, **kwargs):
            """Return checksum based on file modification times."""
            return get_cache_checksum()
        
        def select_prompts(self, separator=", ", **kwargs):
            """
            Collect selected prompts from all dropdowns and join them.
            Returns both positive and negative prompt strings.
            """
            positive_prompts = []
            negative_prompts = []
            
            for widget_name, selected_display in kwargs.items():
                if widget_name == "separator":
                    continue
                
                if selected_display in (DISABLED_OPTION, "(none)", ""):
                    continue
                
                filename = widget_name
                
                positive, negative = get_prompt_from_file(
                    self._category, 
                    filename, 
                    selected_display
                )
                
                if positive:
                    positive_prompts.append(positive)
                if negative:
                    negative_prompts.append(negative)
            
            positive_result = separator.join(positive_prompts)
            negative_result = separator.join(negative_prompts)
            
            return (positive_result, negative_result)
    
    return CategoryPromptNode


def generate_node_mappings():
    """
    Generate NODE_CLASS_MAPPINGS and NODE_DISPLAY_NAME_MAPPINGS
    dynamically based on discovered category folders.
    """
    class_mappings = {}
    display_mappings = {}
    
    categories = discover_categories()
    
    for category in categories:
        node_class = create_category_node_class(category)
        class_name = f"PromptSelector_{category.title().replace(' ', '').replace('_', '')}"
        display_name = f"Prompts: {category.replace('_', ' ').title()}"
        
        class_mappings[class_name] = node_class
        display_mappings[class_name] = display_name
    
    return class_mappings, display_mappings


# Generate mappings at import time
NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS = generate_node_mappings()

# Placeholder if no categories found
if not NODE_CLASS_MAPPINGS:
    class PromptSelectorPlaceholder:
        """Placeholder node shown when no YAML data is found."""
        
        @classmethod
        def INPUT_TYPES(cls):
            return {
                "required": {
                    "message": ("STRING", {
                        "default": "No YAML files found. Add folders with .yaml files to prompt_selector/data/",
                        "multiline": True,
                    }),
                },
            }
        
        RETURN_TYPES = ("STRING", "STRING")
        RETURN_NAMES = ("positive", "negative")
        FUNCTION = "show_message"
        CATEGORY = "utils/prompts"
        
        def show_message(self, message):
            return ("", "")
    
    NODE_CLASS_MAPPINGS = {"PromptSelector": PromptSelectorPlaceholder}
    NODE_DISPLAY_NAME_MAPPINGS = {"PromptSelector": "Prompt Selector (No Data)"}
