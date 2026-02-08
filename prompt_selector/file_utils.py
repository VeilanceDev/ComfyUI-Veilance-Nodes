"""
File Utilities for Prompt Selector Node
Handles loading and parsing YAML, CSV, and JSON files for prompt data.

Supported formats:
- YAML (.yaml, .yml): Flexible format with name, positive, negative, favorite fields
- CSV (.csv): Four columns - name, positive, negative, favorite (use quotes for commas)
- JSON (.json): Array of objects with name, positive, negative, favorite fields
"""

import csv
import json
import os
import random
import re
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional, NamedTuple

# Try to import yaml, provide helpful error if not installed
try:
    import yaml
except ImportError:
    yaml = None
    print("[PromptSelector] Warning: PyYAML not installed. YAML files will be skipped. "
          "Install with: pip install pyyaml")

# Try to import watchdog for folder watching
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("[PromptSelector] Info: watchdog not installed. Folder auto-refresh disabled. "
          "Install with: pip install watchdog")


class PromptEntry(NamedTuple):
    """A single prompt entry with display name and prompts."""
    display_name: str
    positive_prompt: str
    negative_prompt: str
    is_favorite: bool = False


# Type aliases
PromptList = List[PromptEntry]
FilePrompts = Dict[str, PromptList]  # filename -> prompts
CategoryData = Dict[str, FilePrompts]  # category_name -> {filename -> prompts}
DisplayIndex = Dict[str, Dict[str, Dict[str, List[PromptEntry]]]]  # category -> filename -> display_name -> entries
OptionIndex = Dict[str, Dict[str, Dict[str, PromptEntry]]]  # category -> filename -> option_value -> entry
FileOptions = Dict[str, Dict[str, List[str]]]  # category -> filename -> ordered option values

# Cache for loaded prompt data
_category_cache: CategoryData = {}
_display_index: DisplayIndex = {}
_option_index: OptionIndex = {}
_file_options: FileOptions = {}
_file_mtimes: Dict[str, float] = {}  # filepath -> mtime
_cache_valid = False
_cache_lock = threading.RLock()

# Folder watcher instance
_file_watcher: Optional["PromptFileWatcher"] = None
_watcher_started = False

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
_DUPLICATE_SUFFIX_RE = re.compile(r" \((\d+)\)$")


def _parse_bool(value) -> bool:
    """
    Parse common boolean-ish values.
    Strings only return True for explicit truthy values.
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "on"}

    return False


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
      favorite: true/false (optional, default false)
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
            favorite = _parse_bool(item.get('favorite', False))
            
            # Fallback chain: name -> positive -> negative
            display = name or positive or negative
            
            if display:
                prompts.append(PromptEntry(display, positive, negative, favorite))
                    
    except Exception as e:
        print(f"[PromptSelector] Error loading YAML {filepath}: {e}")
        
    return prompts


def load_csv_file(filepath: Path) -> PromptList:
    """
    Load a CSV file and return list of PromptEntry objects.
    
    CSV format: name, positive, negative, favorite
    - All columns are optional
    - Use quotes around values containing commas
    - Use "" for literal quotes inside quoted values
    - favorite column accepts: true, 1, yes (case-insensitive)
    """
    prompts = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            
            first_row = next(reader, None)
            if first_row is None:
                return prompts
            
            # Check for header row using exact normalized column names.
            # This avoids false positives when prompt text merely contains
            # words like "prompt" in normal data rows.
            normalized = [
                str(cell).strip().lower().lstrip('\ufeff').replace(" ", "_")
                for cell in first_row
            ]
            header_names = {'name', 'display', 'positive', 'prompt', 'negative', 'favorite'}
            header_hits = sum(1 for col in normalized if col in header_names)
            is_header = header_hits >= 2 and any(
                col in {'name', 'display', 'positive', 'prompt'} for col in normalized
            )
            
            def parse_row(row: list) -> Optional[PromptEntry]:
                """Parse a CSV row into a PromptEntry."""
                col1 = row[0].strip() if len(row) > 0 else ""
                col2 = row[1].strip() if len(row) > 1 else ""
                col3 = row[2].strip() if len(row) > 2 else ""
                col4 = row[3].strip().lower() if len(row) > 3 else ""
                
                # Columns: name, positive, negative, favorite
                name = col1
                positive = col2
                negative = col3
                favorite = _parse_bool(col4)
                
                # Fallback chain: name -> positive -> negative
                display = name or positive or negative
                
                if not display:
                    return None
                    
                return PromptEntry(display, positive, negative, favorite)
            
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
        {"name": "display name", "positive": "...", "negative": "...", "favorite": true},
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
            favorite = _parse_bool(item.get('favorite', False))
            
            # Fallback chain: name -> positive -> negative
            display = name or positive or negative
            
            if display:
                prompts.append(PromptEntry(display, positive, negative, favorite))
                    
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
        with _cache_lock:
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
    Uses forward slash as canonical separator for cross-platform compatibility.
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
            # Use forward slash as canonical separator (works on both Windows and Linux)
            rel_path = root_path.relative_to(data_dir)
            category_name = rel_path.as_posix()  # Always uses forward slashes
            categories.append(category_name)
    
    return sorted(categories)


def get_category_files(category: str, data_dir: Optional[Path] = None) -> FilePrompts:
    """
    Load all prompt files (YAML, CSV, JSON) from a category folder.
    Category uses forward slash for nested paths (e.g., 'characters/heroes').
    """
    if data_dir is None:
        data_dir = get_data_directory()
    
    # Category uses forward slash as canonical separator
    # Path() handles conversion to OS-native separator automatically
    category_dir = data_dir / category
    
    if not category_dir.exists():
        return {}
    
    files_data: FilePrompts = {}
    
    # Collect all supported files in this directory only (not recursive)
    all_files: List[Path] = []
    for ext in ALL_EXTENSIONS:
        all_files.extend(category_dir.glob(f"*{ext}"))

    # Sort by stem then extension for deterministic widget ordering.
    sorted_files = sorted(
        all_files,
        key=lambda p: (p.stem.lower(), p.suffix.lower(), p.name.lower()),
    )
    stem_counts = Counter(p.stem for p in sorted_files)

    # Load files and ensure unique keys even when stems collide across extensions.
    for prompt_file in sorted_files:
        prompts = load_prompt_file(prompt_file)
        if prompts:
            file_key = prompt_file.stem
            if stem_counts[prompt_file.stem] > 1:
                file_key = f"{prompt_file.stem} [{prompt_file.suffix.lower().lstrip('.')}]"
            files_data[file_key] = prompts

    return files_data


def _build_file_indexes(prompts: PromptList) -> Tuple[List[str], Dict[str, PromptEntry], Dict[str, List[PromptEntry]]]:
    """
    Build per-file indexes:
    - Ordered option labels (favorites first, duplicates disambiguated)
    - option_label -> PromptEntry lookup
    - display_name -> [PromptEntry, ...] lookup for backwards compatibility
    """
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
    """Build indexed lookup tables used by dropdowns and prompt resolution."""
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
    """
    Load all categories with their files and prompts.
    Uses lazy loading - only loads on first access.
    """
    global _category_cache, _display_index, _option_index, _file_options, _cache_valid
    
    with _cache_lock:
        if _cache_valid:
            return _category_cache

        if data_dir is None:
            data_dir = get_data_directory()

        result: CategoryData = {}
        categories = discover_categories(data_dir)

        for category in categories:
            files_data = get_category_files(category, data_dir)
            if files_data:
                result[category] = files_data

        _category_cache = result
        _display_index, _option_index, _file_options = _build_indexes(result)
        _cache_valid = True

        return _category_cache


def refresh_cache() -> CategoryData:
    """
    Invalidate the cache and reload all prompt data.
    """
    global _category_cache, _display_index, _option_index, _file_options, _file_mtimes, _cache_valid
    
    with _cache_lock:
        _category_cache = {}
        _display_index = {}
        _option_index = {}
        _file_options = {}
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
    
    with _cache_lock:
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
    Handles star-prefixed favorites by stripping the prefix.
    """
    if display_name in (DISABLED_OPTION, "") or not display_name:
        return ("", "")
    
    # Handle random selection
    if display_name == RANDOM_OPTION:
        return get_random_prompt_from_file(category, filename)
    
    entry = _resolve_entry(category, filename, display_name)
    if entry is not None:
        return (entry.positive_prompt, entry.negative_prompt)

    return ("", "")


def get_random_prompt_from_file(category: str, filename: str) -> Tuple[str, str]:
    """
    Get a random prompt from a specific file.
    """
    get_all_category_data()

    with _cache_lock:
        prompts = _category_cache.get(category, {}).get(filename, [])
    if not prompts:
        return ("", "")

    entry = random.choice(prompts)
    return (entry.positive_prompt, entry.negative_prompt)


def get_file_dropdown_options(category: str, filename: str) -> List[str]:
    """
    Get dropdown options for a specific prompt file.
    Includes disabled option and random option.
    Favorites are shown first with a star prefix.
    """
    get_all_category_data()

    with _cache_lock:
        category_options = _file_options.get(category, {})
        if filename not in category_options:
            return [DISABLED_OPTION]
        options = list(category_options.get(filename, []))

    return [DISABLED_OPTION, RANDOM_OPTION] + options


def get_prompt_entry_details(category: str, filename: str, display_name: str) -> Optional[dict]:
    """
    Get full details of a prompt entry for preview tooltip.
    Returns dict with positive, negative, and is_favorite fields.
    """
    if display_name in (DISABLED_OPTION, RANDOM_OPTION, "") or not display_name:
        return None
    
    entry = _resolve_entry(category, filename, display_name)
    if entry:
        return {
            "positive": entry.positive_prompt,
            "negative": entry.negative_prompt,
            "is_favorite": entry.is_favorite,
            "display_name": entry.display_name
        }
    
    return None


def _resolve_entry(category: str, filename: str, display_name: str) -> Optional[PromptEntry]:
    """
    Resolve a dropdown option value to a PromptEntry.
    Supports current disambiguated labels and older saved values.
    """
    get_all_category_data()

    with _cache_lock:
        # Fast path: direct option value lookup.
        entry = _option_index.get(category, {}).get(filename, {}).get(display_name)
        if entry is not None:
            return entry

        # Backwards compatibility for older workflows using raw display labels.
        lookup_name = display_name
        if lookup_name.startswith("⭐ "):
            lookup_name = lookup_name[2:]

        occurrence_index: Optional[int] = None
        duplicate_match = _DUPLICATE_SUFFIX_RE.search(lookup_name)
        if duplicate_match:
            occurrence_index = int(duplicate_match.group(1)) - 1
            lookup_name = lookup_name[:duplicate_match.start()]

        entries = _display_index.get(category, {}).get(filename, {}).get(lookup_name, [])
        if not entries:
            return None

        if occurrence_index is not None and 0 <= occurrence_index < len(entries):
            return entries[occurrence_index]

        return entries[0]


# ============================================================================
# Folder Watch Implementation
# ============================================================================

class PromptFileWatcher:
    """
    Watches the data/prompts directory for changes and auto-refreshes cache.
    Uses debouncing to avoid excessive refreshes on rapid file changes.
    """
    
    def __init__(self, debounce_seconds: float = 0.5):
        self.debounce_seconds = debounce_seconds
        self._observer = None
        self._last_event_time = 0.0
        self._pending_refresh = False
        self._refresh_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
    
    def _on_file_change(self, event):
        """Handle file system events with debouncing."""
        # Only process relevant file types
        if hasattr(event, 'src_path'):
            src_path = event.src_path
            if not any(src_path.lower().endswith(ext) for ext in ALL_EXTENSIONS):
                # Check if it's a directory event (for new/deleted folders)
                if not event.is_directory:
                    return
        
        with self._lock:
            self._last_event_time = time.time()
            
            # Cancel existing timer if any
            if self._refresh_timer:
                self._refresh_timer.cancel()
            
            # Schedule a new refresh after debounce period
            self._refresh_timer = threading.Timer(
                self.debounce_seconds, 
                self._do_refresh
            )
            self._refresh_timer.daemon = True
            self._refresh_timer.start()
    
    def _do_refresh(self):
        """Actually perform the cache refresh."""
        global _cache_valid
        
        with self._lock:
            self._refresh_timer = None
            with _cache_lock:
                _cache_valid = False
        
        print("[PromptSelector] File change detected, cache invalidated")
    
    def start(self, watch_path: Optional[Path] = None):
        """Start watching the data directory."""
        if not WATCHDOG_AVAILABLE:
            return False
        
        if self._observer is not None:
            return True  # Already running
        
        if watch_path is None:
            watch_path = get_data_directory()
        
        if not watch_path.exists():
            print(f"[PromptSelector] Watch path does not exist: {watch_path}")
            return False
        
        try:
            # Create event handler
            handler = FileSystemEventHandler()
            handler.on_created = self._on_file_change
            handler.on_deleted = self._on_file_change
            handler.on_modified = self._on_file_change
            handler.on_moved = self._on_file_change
            
            # Create and start observer
            self._observer = Observer()
            self._observer.schedule(handler, str(watch_path), recursive=True)
            self._observer.daemon = True
            self._observer.start()
            
            print(f"[PromptSelector] Watching for file changes: {watch_path}")
            return True
            
        except Exception as e:
            print(f"[PromptSelector] Failed to start file watcher: {e}")
            self._observer = None
            return False
    
    def stop(self):
        """Stop watching."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=1.0)
            self._observer = None
        
        if self._refresh_timer:
            self._refresh_timer.cancel()
            self._refresh_timer = None


def start_file_watcher() -> bool:
    """
    Start the file watcher if not already running.
    Called automatically on first data access.
    Returns True if watcher is running, False otherwise.
    """
    global _file_watcher, _watcher_started
    
    if _watcher_started:
        return _file_watcher is not None
    
    _watcher_started = True
    
    if not WATCHDOG_AVAILABLE:
        return False
    
    _file_watcher = PromptFileWatcher(debounce_seconds=0.5)
    return _file_watcher.start()


def stop_file_watcher():
    """Stop the file watcher if running."""
    global _file_watcher
    
    if _file_watcher:
        _file_watcher.stop()
        _file_watcher = None
