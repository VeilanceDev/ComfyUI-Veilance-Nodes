from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


PACKAGE_NAME = "veilance_nodes_testpkg"
REPO_ROOT = Path(__file__).resolve().parents[1]


def ensure_test_package():
    package = sys.modules.get(PACKAGE_NAME)
    if package is not None:
        return package

    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(REPO_ROOT)]
    sys.modules[PACKAGE_NAME] = package
    return package


def import_repo_module(relative_name: str):
    ensure_test_package()
    return importlib.import_module(f"{PACKAGE_NAME}.{relative_name}")

