"""
Prompt Selector filesystem watching.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

from .cache import get_data_directory, invalidate_cache
from .parsers import ALL_EXTENSIONS

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print(
        "[PromptSelector] Info: watchdog not installed. Folder auto-refresh disabled. "
        "Install with: pip install watchdog"
    )


class PromptFileWatcher:
    def __init__(self, debounce_seconds: float = 0.5):
        self.debounce_seconds = debounce_seconds
        self._observer = None
        self._last_event_time = 0.0
        self._refresh_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def _on_file_change(self, event):
        if hasattr(event, "src_path"):
            src_path = event.src_path
            if not any(src_path.lower().endswith(ext) for ext in ALL_EXTENSIONS):
                if not event.is_directory:
                    return

        with self._lock:
            self._last_event_time = time.time()

            if self._refresh_timer:
                self._refresh_timer.cancel()

            self._refresh_timer = threading.Timer(
                self.debounce_seconds,
                self._do_refresh,
            )
            self._refresh_timer.daemon = True
            self._refresh_timer.start()

    def _do_refresh(self):
        with self._lock:
            self._refresh_timer = None
            invalidate_cache()

        print("[PromptSelector] File change detected, cache invalidated")

    def start(self, watch_path: Optional[Path] = None):
        if not WATCHDOG_AVAILABLE:
            return False

        if self._observer is not None:
            return True

        if watch_path is None:
            watch_path = get_data_directory()

        if not watch_path.exists():
            print(f"[PromptSelector] Watch path does not exist: {watch_path}")
            return False

        try:
            handler = FileSystemEventHandler()
            handler.on_created = self._on_file_change
            handler.on_deleted = self._on_file_change
            handler.on_modified = self._on_file_change
            handler.on_moved = self._on_file_change

            self._observer = Observer()
            self._observer.schedule(handler, str(watch_path), recursive=True)
            self._observer.daemon = True
            self._observer.start()

            print(f"[PromptSelector] Watching for file changes: {watch_path}")
            return True
        except Exception as exc:
            print(f"[PromptSelector] Failed to start file watcher: {exc}")
            self._observer = None
            return False

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=1.0)
            self._observer = None

        if self._refresh_timer:
            self._refresh_timer.cancel()
            self._refresh_timer = None


_file_watcher: Optional[PromptFileWatcher] = None
_watcher_started = False


def start_file_watcher() -> bool:
    global _file_watcher, _watcher_started

    if _watcher_started:
        return _file_watcher is not None

    _watcher_started = True

    if not WATCHDOG_AVAILABLE:
        return False

    _file_watcher = PromptFileWatcher(debounce_seconds=0.5)
    return _file_watcher.start()


def stop_file_watcher():
    global _file_watcher

    if _file_watcher:
        _file_watcher.stop()
        _file_watcher = None

