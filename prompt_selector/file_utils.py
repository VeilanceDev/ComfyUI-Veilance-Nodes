"""
File Utilities for Prompt Selector Node
Handles loading and parsing YAML, CSV, and JSON files for prompt data.

Supported formats:
- YAML (.yaml, .yml): Flexible format with name, positive, negative fields
- CSV (.csv): Three columns - name, positive, negative (use quotes for commas)
- JSON (.json): Array of objects with name, positive, negative fields
"""

import csv
import json
import os
import random
from pathlib import Path
from typing import Dict, List, Tuple, Optional, NamedTuple

# Try to import yaml, provide helpful error if not installed
try:
    import yaml
except ImportError:
    yaml = None
    print("[PromptSelector] Warning: PyYAML not installed. YAML files will be skipped. "
          "Install with: pip install pyyaml")


class PromptEntry(NamedTuple):
    """A single prompt entry with display name and prompts."""
    display_name: str
    positive_prompt: str
    negative_prompt: str


# Type aliases
PromptList = List[PromptEntry]
FilePrompts = Dict[str, PromptList]  # filename -> prompts
CategoryData = Dict[str, FilePrompts]  # category_name -> {filename -> prompts}
DisplayIndex = Dict[str, Dict[str, Dict[str, PromptEntry]]]  # category -> filename -> display_name -> entry

# Cache for loaded prompt data
_category_cache: CategoryData = {}
_display_index: DisplayIndex = {}
_file_mtimes: Dict[str, float] = {}  # filepath -> mtime
_cache_valid = False

# Supported file extensions
YAML_EXTENSIONS = {'.yaml', '.yml'}
CSV_EXTENSIONS = {'.csv'}
JSON_EXTENSIONS = {'.json'}
ALL_EXTENSIONS = YAML_EXTENSIONS | CSV_EXTENSIONS | JSON_EXTENSIONS

# Special dropdown options
DISABLED_OPTION = "❌ Disabled"
RANDOM_OPTION = "🎲 Random"


# Folders to exclude from category discovery
EXCLUDED_FOLDERS = {'examples', '__pycache__'}


def get_data_directory() -> Path:
    """Get the path to the data/prompts directory relative to project root."""
    # Go up from prompt_selector/ to project root, then into data/prompts
    return Path(__file__).parent.parent / "data" / "prompts"


def load_yaml_file(filepath: Path) -> PromptList:
    """
    Load a YAML file and return list of PromptEntry objects.
    
    YAML format:
    - name: display name (optional, falls back to positive)
      positive: positive prompt text
      negative: negative prompt text (optional)
    """
    if yaml is None:
        return []
    
    prompts = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not data or not isinstance(data, list):
            return prompts
        
        for item in data:
            if not isinstance(item, dict):
                continue
            
            positive = str(item.get('positive', '')).strip()
            negative = str(item.get('negative', '')).strip()
            name = str(item.get('name', '')).strip()
            
            # Fallback chain: name -> positive -> negative
            display = name or positive or negative
            
            if display:
                prompts.append(PromptEntry(display, positive, negative))
                    
    except Exception as e:
        print(f"[PromptSelector] Error loading YAML {filepath}: {e}")
        
    return prompts


def load_csv_file(filepath: Path) -> PromptList:
    """
    Load a CSV file and return list of PromptEntry objects.
    
    CSV format: name, positive, negative
    - All columns are optional
    - Use quotes around values containing commas
    - Use "" for literal quotes inside quoted values
    """
    prompts = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            
            first_row = next(reader, None)
            if first_row is None:
                return prompts
            
            # Check for header row
            header_keywords = ['name', 'positive', 'negative', 'display', 'prompt']
            is_header = any(
                keyword in str(cell).lower() 
                for cell in first_row 
                for keyword in header_keywords
            )
            
            def parse_row(row: list) -> Optional[PromptEntry]:
                """Parse a CSV row into a PromptEntry."""
                col1 = row[0].strip() if len(row) > 0 else ""
                col2 = row[1].strip() if len(row) > 1 else ""
                col3 = row[2].strip() if len(row) > 2 else ""
                
                # Columns: name, positive, negative
                name = col1
                positive = col2
                negative = col3
                
                # Fallback chain: name -> positive -> negative
                display = name or positive or negative
                
                if not display:
                    return None
                    
                return PromptEntry(display, positive, negative)
            
            # Process first row if not header
            if not is_header:
                entry = parse_row(first_row)
                if entry:
                    prompts.append(entry)
            
            # Process remaining rows
            for row in reader:
                entry = parse_row(row)
                if entry:
                    prompts.append(entry)
                    
    except Exception as e:
        print(f"[PromptSelector] Error loading CSV {filepath}: {e}")
        
    return prompts


def load_json_file(filepath: Path) -> PromptList:
    """
    Load a JSON file and return list of PromptEntry objects.
    
    JSON format:
    [
        {"name": "display name", "positive": "positive prompt", "negative": "negative prompt"},
        ...
    ]
    """
    prompts = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not data or not isinstance(data, list):
            return prompts
        
        for item in data:
            if not isinstance(item, dict):
                continue
            
            positive = str(item.get('positive', '')).strip()
            negative = str(item.get('negative', '')).strip()
            name = str(item.get('name', '')).strip()
            
            # Fallback chain: name -> positive -> negative
            display = name or positive or negative
            
            if display:
                prompts.append(PromptEntry(display, positive, negative))
                    
    except Exception as e:
        print(f"[PromptSelector] Error loading JSON {filepath}: {e}")
        
    return prompts


def load_prompt_file(filepath: Path) -> PromptList:
    """
    Load a prompt file (YAML, CSV, or JSON) based on extension.
    Also tracks file modification time.
    """
    global _file_mtimes
    
    ext = filepath.suffix.lower()
    
    # Track file modification time
    try:
        _file_mtimes[str(filepath)] = filepath.stat().st_mtime
    except OSError:
        pass
    
    if ext in YAML_EXTENSIONS:
        return load_yaml_file(filepath)
    elif ext in CSV_EXTENSIONS:
        return load_csv_file(filepath)
    elif ext in JSON_EXTENSIONS:
        return load_json_file(filepath)
    else:
        return []


def discover_categories(data_dir: Optional[Path] = None) -> List[str]:
    """
    Scan data directory recursively for folders containing prompt files.
    Supports nested subcategories like 'characters/heroes'.
    """
    if data_dir is None:
        data_dir = get_data_directory()
    
    if not data_dir.exists():
        return []
    
    categories = []
    
    # Walk directory tree recursively
    for root, dirs, files in os.walk(data_dir):
        # Skip hidden directories and excluded folders
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in EXCLUDED_FOLDERS]
        
        root_path = Path(root)
        
        # Check if this directory has any prompt files
        has_files = any(
            f.lower().endswith(tuple(ALL_EXTENSIONS))
            for f in files
        )
        
        if has_files:
            # Get relative path from data_dir as category name
            rel_path = root_path.relative_to(data_dir)
            category_name = str(rel_path).replace(os.sep, '_')
            categories.append(category_name)
    
    return sorted(categories)


def get_category_files(category: str, data_dir: Optional[Path] = None) -> FilePrompts:
    """
    Load all prompt files (YAML, CSV, JSON) from a category folder.
    Category can include underscores for nested paths (e.g., 'characters_heroes').
    """
    if data_dir is None:
        data_dir = get_data_directory()
    
    # Convert category name back to path (underscores -> path separators)
    category_path = category.replace('_', os.sep)
    category_dir = data_dir / category_path
    
    if not category_dir.exists():
        return {}
    
    files_data = {}
    
    # Collect all supported files in this directory only (not recursive)
    all_files = []
    for ext in ALL_EXTENSIONS:
        all_files.extend(category_dir.glob(f"*{ext}"))
    
    # Sort by filename and load
    for prompt_file in sorted(all_files, key=lambda p: p.stem):
        prompts = load_prompt_file(prompt_file)
        if prompts:
            files_data[prompt_file.stem] = prompts
    
    return files_data


def _build_display_index(data: CategoryData) -> DisplayIndex:
    """Build indexed lookup table for fast display_name -> PromptEntry access."""
    index: DisplayIndex = {}
    
    for category, files in data.items():
        index[category] = {}
        for filename, prompts in files.items():
            index[category][filename] = {
                entry.display_name: entry for entry in prompts
            }
    
    return index


def get_all_category_data(data_dir: Optional[Path] = None) -> CategoryData:
    """
    Load all categories with their files and prompts.
    Uses lazy loading - only loads on first access.
    """
    global _category_cache, _display_index, _cache_valid
    
    if _cache_valid and _category_cache:
        return _category_cache
    
    if data_dir is None:
        data_dir = get_data_directory()
    
    result = {}
    categories = discover_categories(data_dir)
    
    for category in categories:
        files_data = get_category_files(category, data_dir)
        if files_data:
            result[category] = files_data
    
    _category_cache = result
    _display_index = _build_display_index(result)
    _cache_valid = True
    
    return result


def refresh_cache() -> CategoryData:
    """
    Invalidate the cache and reload all prompt data.
    """
    global _category_cache, _display_index, _file_mtimes, _cache_valid
    
    _category_cache = {}
    _display_index = {}
    _file_mtimes = {}
    _cache_valid = False
    
    return get_all_category_data()


def get_cache_checksum() -> str:
    """
    Get a checksum based on file modification times.
    Returns a stable value if files haven't changed.
    Used by IS_CHANGED to enable caching.
    """
    global _file_mtimes
    
    # Ensure cache is loaded
    get_all_category_data()
    
    if not _file_mtimes:
        return "empty"
    
    # Check current mtimes against cached ones
    current_mtimes = []
    for filepath_str in sorted(_file_mtimes.keys()):
        filepath = Path(filepath_str)
        try:
            mtime = filepath.stat().st_mtime
            current_mtimes.append(f"{filepath_str}:{mtime}")
        except OSError:
            current_mtimes.append(f"{filepath_str}:missing")
    
    return "|".join(current_mtimes)


def get_prompt_from_file(category: str, filename: str, display_name: str) -> Tuple[str, str]:
    """
    Get the positive and negative prompts for a specific selection.
    Uses indexed lookup for O(1) access.
    """
    if display_name in (DISABLED_OPTION, "(none)", "") or not display_name:
        return ("", "")
    
    # Handle random selection
    if display_name == RANDOM_OPTION:
        return get_random_prompt_from_file(category, filename)
    
    # Ensure data is loaded
    get_all_category_data()
    
    # Use indexed lookup (O(1) instead of O(n))
    if category not in _display_index:
        return ("", "")
    
    if filename not in _display_index[category]:
        return ("", "")
    
    entry = _display_index[category][filename].get(display_name)
    if entry:
        return (entry.positive_prompt, entry.negative_prompt)
    
    return ("", "")


def get_random_prompt_from_file(category: str, filename: str) -> Tuple[str, str]:
    """
    Get a random prompt from a specific file.
    """
    data = get_all_category_data()
    
    if category not in data:
        return ("", "")
    
    if filename not in data[category]:
        return ("", "")
    
    prompts = data[category][filename]
    if not prompts:
        return ("", "")
    
    entry = random.choice(prompts)
    return (entry.positive_prompt, entry.negative_prompt)


def get_file_dropdown_options(category: str, filename: str) -> List[str]:
    """
    Get dropdown options for a specific prompt file.
    Includes disabled option and random option.
    """
    data = get_all_category_data()
    
    if category not in data or filename not in data[category]:
        return [DISABLED_OPTION]
    
    prompts = data[category][filename]
    options = [DISABLED_OPTION, RANDOM_OPTION] + [entry.display_name for entry in prompts]
    
    return options
