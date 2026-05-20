"""
Prompt file parsing helpers for Prompt Selector nodes.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

try:
    import yaml
except ImportError:
    yaml = None
    print(
        "[PromptSelector] Warning: PyYAML not installed. YAML files will be skipped. "
        "Install with: pip install pyyaml"
    )


class PromptEntry(NamedTuple):
    """A single prompt entry with display name and prompts."""

    display_name: str
    positive_prompt: str
    negative_prompt: str
    is_favorite: bool = False


PromptList = List[PromptEntry]
FilePrompts = Dict[str, PromptList]
CategoryData = Dict[str, FilePrompts]
DisplayIndex = Dict[str, Dict[str, Dict[str, List[PromptEntry]]]]
OptionIndex = Dict[str, Dict[str, Dict[str, PromptEntry]]]
FileOptions = Dict[str, Dict[str, List[str]]]

YAML_EXTENSIONS = {".yaml", ".yml"}
CSV_EXTENSIONS = {".csv"}
JSON_EXTENSIONS = {".json"}
ALL_EXTENSIONS = YAML_EXTENSIONS | CSV_EXTENSIONS | JSON_EXTENSIONS

DISABLED_OPTION = "❌ Disabled"
RANDOM_OPTION = "🎲 Random"
EXCLUDED_FOLDERS = {"examples", "__pycache__"}


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "on"}
    return False


def _entry_from_mapping(item: dict) -> PromptEntry | None:
    positive = str(item.get("positive", "")).strip()
    negative = str(item.get("negative", "")).strip()
    name = str(item.get("name", "")).strip()
    favorite = _parse_bool(item.get("favorite", False))

    display = name or positive or negative
    if not display:
        return None
    return PromptEntry(display, positive, negative, favorite)


def load_yaml_file(filepath: Path) -> PromptList:
    if yaml is None:
        return []

    prompts: PromptList = []
    try:
        with open(filepath, "r", encoding="utf-8") as file_handle:
            data = yaml.safe_load(file_handle)

        if not data or not isinstance(data, list):
            return prompts

        for item in data:
            if not isinstance(item, dict):
                continue
            entry = _entry_from_mapping(item)
            if entry is not None:
                prompts.append(entry)
    except Exception as exc:
        print(f"[PromptSelector] Error loading YAML {filepath}: {exc}")

    return prompts


def load_csv_file(filepath: Path) -> PromptList:
    prompts: PromptList = []

    try:
        with open(filepath, "r", encoding="utf-8") as file_handle:
            reader = csv.reader(file_handle)

            first_row = next(reader, None)
            if first_row is None:
                return prompts

            normalized = [
                str(cell).strip().lower().lstrip("\ufeff").replace(" ", "_")
                for cell in first_row
            ]
            header_names = {
                "name",
                "display",
                "positive",
                "prompt",
                "negative",
                "favorite",
            }
            header_hits = sum(1 for col in normalized if col in header_names)
            is_header = header_hits >= 2 and any(
                col in {"name", "display", "positive", "prompt"}
                for col in normalized
            )

            def parse_row(row: list) -> Optional[PromptEntry]:
                col1 = row[0].strip() if len(row) > 0 else ""
                col2 = row[1].strip() if len(row) > 1 else ""
                col3 = row[2].strip() if len(row) > 2 else ""
                col4 = row[3].strip() if len(row) > 3 else ""

                return _entry_from_mapping(
                    {
                        "name": col1,
                        "positive": col2,
                        "negative": col3,
                        "favorite": col4,
                    }
                )

            if not is_header:
                entry = parse_row(first_row)
                if entry is not None:
                    prompts.append(entry)

            for row in reader:
                entry = parse_row(row)
                if entry is not None:
                    prompts.append(entry)
    except Exception as exc:
        print(f"[PromptSelector] Error loading CSV {filepath}: {exc}")

    return prompts


def load_json_file(filepath: Path) -> PromptList:
    prompts: PromptList = []

    try:
        with open(filepath, "r", encoding="utf-8") as file_handle:
            data = json.load(file_handle)

        if not data or not isinstance(data, list):
            return prompts

        for item in data:
            if not isinstance(item, dict):
                continue
            entry = _entry_from_mapping(item)
            if entry is not None:
                prompts.append(entry)
    except Exception as exc:
        print(f"[PromptSelector] Error loading JSON {filepath}: {exc}")

    return prompts

