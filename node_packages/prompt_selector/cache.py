"""
Prompt Selector cache, indexing, and category discovery.
"""

from __future__ import annotations

import os
import random
import re
import threading
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
    load_csv_file,
    load_json_file,
    load_yaml_file,
)

_category_cache: CategoryData = {}
_display_index: DisplayIndex = {}
_option_index: OptionIndex = {}
_file_options: FileOptions = {}
_file_mtimes: Dict[str, float] = {}
_cache_valid = False
_cache_lock = threading.RLock()
_DUPLICATE_SUFFIX_RE = re.compile(r" \((\d+)\)$")


def get_data_directory() -> Path:
    return Path(__file__).parent.parent / "data" / "prompts"


def invalidate_cache() -> None:
    global _cache_valid
    with _cache_lock:
        _cache_valid = False


def load_prompt_file(filepath: Path) -> PromptList:
    global _file_mtimes

    ext = filepath.suffix.lower()

    try:
        with _cache_lock:
            _file_mtimes[str(filepath)] = filepath.stat().st_mtime
    except OSError:
        pass

    if ext in YAML_EXTENSIONS:
        return load_yaml_file(filepath)
    if ext in CSV_EXTENSIONS:
        return load_csv_file(filepath)
    if ext in JSON_EXTENSIONS:
        return load_json_file(filepath)
    return []


def discover_categories(data_dir: Optional[Path] = None) -> List[str]:
    if data_dir is None:
        data_dir = get_data_directory()

    if not data_dir.exists():
        return []

    categories = []
    for root, dirs, files in os.walk(data_dir):
        dirs[:] = [
            directory
            for directory in dirs
            if not directory.startswith(".") and directory not in EXCLUDED_FOLDERS
        ]

        root_path = Path(root)
        has_files = any(
            filename.lower().endswith(tuple(ALL_EXTENSIONS))
            for filename in files
        )

        if has_files:
            categories.append(root_path.relative_to(data_dir).as_posix())

    return sorted(categories)


def get_category_files(category: str, data_dir: Optional[Path] = None) -> FilePrompts:
    if data_dir is None:
        data_dir = get_data_directory()

    category_dir = data_dir / category
    if not category_dir.exists():
        return {}

    files_data: FilePrompts = {}
    all_files: List[Path] = []
    for ext in ALL_EXTENSIONS:
        all_files.extend(category_dir.glob(f"*{ext}"))

    sorted_files = sorted(
        all_files,
        key=lambda path: (path.stem.lower(), path.suffix.lower(), path.name.lower()),
    )
    stem_counts = Counter(path.stem for path in sorted_files)

    for prompt_file in sorted_files:
        prompts = load_prompt_file(prompt_file)
        if not prompts:
            continue

        file_key = prompt_file.stem
        if stem_counts[prompt_file.stem] > 1:
            file_key = f"{prompt_file.stem} [{prompt_file.suffix.lower().lstrip('.')}]"
        files_data[file_key] = prompts

    return files_data


def _build_file_indexes(
    prompts: PromptList,
) -> Tuple[List[str], Dict[str, PromptEntry], Dict[str, List[PromptEntry]]]:
    favorites = [entry for entry in prompts if entry.is_favorite]
    regular = [entry for entry in prompts if not entry.is_favorite]
    ordered = favorites + regular

    duplicate_counts = Counter(entry.display_name for entry in ordered)
    seen_counts: Dict[str, int] = defaultdict(int)

    option_labels: List[str] = []
    option_lookup: Dict[str, PromptEntry] = {}
    display_lookup: Dict[str, List[PromptEntry]] = {}

    for entry in ordered:
        base_label = entry.display_name
        seen_counts[base_label] += 1

        display_lookup.setdefault(base_label, []).append(entry)

        option_label = base_label
        if duplicate_counts[base_label] > 1:
            option_label = f"{base_label} ({seen_counts[base_label]})"
        if entry.is_favorite:
            option_label = f"⭐ {option_label}"

        option_labels.append(option_label)
        option_lookup[option_label] = entry

    return option_labels, option_lookup, display_lookup


def _build_indexes(data: CategoryData) -> Tuple[DisplayIndex, OptionIndex, FileOptions]:
    display_index: DisplayIndex = {}
    option_index: OptionIndex = {}
    file_options: FileOptions = {}

    for category, files in data.items():
        display_index[category] = {}
        option_index[category] = {}
        file_options[category] = {}

        for filename, prompts in files.items():
            option_labels, option_lookup, display_lookup = _build_file_indexes(prompts)
            display_index[category][filename] = display_lookup
            option_index[category][filename] = option_lookup
            file_options[category][filename] = option_labels

    return display_index, option_index, file_options


def get_all_category_data(data_dir: Optional[Path] = None) -> CategoryData:
    global _category_cache, _display_index, _option_index, _file_options, _cache_valid

    with _cache_lock:
        if _cache_valid:
            return _category_cache

        if data_dir is None:
            data_dir = get_data_directory()

        result: CategoryData = {}
        for category in discover_categories(data_dir):
            files_data = get_category_files(category, data_dir)
            if files_data:
                result[category] = files_data

        _category_cache = result
        _display_index, _option_index, _file_options = _build_indexes(result)
        _cache_valid = True
        return _category_cache


def refresh_cache() -> CategoryData:
    global _category_cache, _display_index, _option_index, _file_options
    global _file_mtimes, _cache_valid

    with _cache_lock:
        _category_cache = {}
        _display_index = {}
        _option_index = {}
        _file_options = {}
        _file_mtimes = {}
        _cache_valid = False

    return get_all_category_data()


def get_cache_checksum() -> str:
    get_all_category_data()

    with _cache_lock:
        if not _file_mtimes:
            return "empty"

        current_mtimes = []
        for filepath_str in sorted(_file_mtimes.keys()):
            filepath = Path(filepath_str)
            try:
                mtime = filepath.stat().st_mtime
                current_mtimes.append(f"{filepath_str}:{mtime}")
            except OSError:
                current_mtimes.append(f"{filepath_str}:missing")

    return "|".join(current_mtimes)


def get_prompt_from_file(
    category: str,
    filename: str,
    display_name: str,
) -> Tuple[str, str]:
    if display_name in (DISABLED_OPTION, "") or not display_name:
        return ("", "")

    if display_name == RANDOM_OPTION:
        return get_random_prompt_from_file(category, filename)

    entry = _resolve_entry(category, filename, display_name)
    if entry is not None:
        return (entry.positive_prompt, entry.negative_prompt)

    return ("", "")


def get_random_prompt_from_file(category: str, filename: str) -> Tuple[str, str]:
    get_all_category_data()

    with _cache_lock:
        prompts = _category_cache.get(category, {}).get(filename, [])
    if not prompts:
        return ("", "")

    entry = random.choice(prompts)
    return (entry.positive_prompt, entry.negative_prompt)


def get_file_dropdown_options(category: str, filename: str) -> List[str]:
    get_all_category_data()

    with _cache_lock:
        category_options = _file_options.get(category, {})
        if filename not in category_options:
            return [DISABLED_OPTION]
        options = list(category_options.get(filename, []))

    return [DISABLED_OPTION, RANDOM_OPTION] + options


def _resolve_entry(
    category: str,
    filename: str,
    display_name: str,
) -> Optional[PromptEntry]:
    get_all_category_data()

    with _cache_lock:
        entry = _option_index.get(category, {}).get(filename, {}).get(display_name)
        if entry is not None:
            return entry

        lookup_name = display_name
        if lookup_name.startswith("⭐ "):
            lookup_name = lookup_name[2:]

        occurrence_index: Optional[int] = None
        duplicate_match = _DUPLICATE_SUFFIX_RE.search(lookup_name)
        if duplicate_match:
            occurrence_index = int(duplicate_match.group(1)) - 1
            lookup_name = lookup_name[: duplicate_match.start()]

        entries = _display_index.get(category, {}).get(filename, {}).get(lookup_name, [])
        if not entries:
            return None

        if occurrence_index is not None and 0 <= occurrence_index < len(entries):
            return entries[occurrence_index]

        return entries[0]

