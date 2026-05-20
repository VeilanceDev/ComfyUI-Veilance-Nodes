"""
Compatibility exports for Prompt Selector file utilities.

Implementation is split across:
- parsers.py: YAML/CSV/JSON parsing and shared data types
- cache.py: category discovery, indexing, cache lifecycle, prompt lookup
- watcher.py: optional watchdog integration
"""

from __future__ import annotations

from .cache import (
    _build_file_indexes,
    _build_indexes,
    _resolve_entry,
    discover_categories,
    get_all_category_data,
    get_cache_checksum,
    get_category_files,
    get_data_directory,
    get_file_dropdown_options,
    get_prompt_from_file,
    get_random_prompt_from_file,
    invalidate_cache,
    load_prompt_file,
    refresh_cache,
)
from .parsers import (
    ALL_EXTENSIONS,
    CSV_EXTENSIONS,
    DISABLED_OPTION,
    EXCLUDED_FOLDERS,
    JSON_EXTENSIONS,
    RANDOM_OPTION,
    YAML_EXTENSIONS,
    CategoryData,
    DisplayIndex,
    FileOptions,
    FilePrompts,
    OptionIndex,
    PromptEntry,
    PromptList,
    _parse_bool,
    load_csv_file,
    load_json_file,
    load_yaml_file,
)
from .watcher import (
    WATCHDOG_AVAILABLE,
    PromptFileWatcher,
    start_file_watcher,
    stop_file_watcher,
)

__all__ = [
    "ALL_EXTENSIONS",
    "CSV_EXTENSIONS",
    "DISABLED_OPTION",
    "EXCLUDED_FOLDERS",
    "JSON_EXTENSIONS",
    "RANDOM_OPTION",
    "YAML_EXTENSIONS",
    "CategoryData",
    "DisplayIndex",
    "FileOptions",
    "FilePrompts",
    "OptionIndex",
    "PromptEntry",
    "PromptFileWatcher",
    "PromptList",
    "WATCHDOG_AVAILABLE",
    "_build_file_indexes",
    "_build_indexes",
    "_parse_bool",
    "_resolve_entry",
    "discover_categories",
    "get_all_category_data",
    "get_cache_checksum",
    "get_category_files",
    "get_data_directory",
    "get_file_dropdown_options",
    "get_prompt_from_file",
    "get_random_prompt_from_file",
    "invalidate_cache",
    "load_csv_file",
    "load_json_file",
    "load_prompt_file",
    "load_yaml_file",
    "refresh_cache",
    "start_file_watcher",
    "stop_file_watcher",
]
