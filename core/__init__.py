"""Shim package that exposes ``src/core`` for ``python -m`` execution."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
_PKG = _SRC / "core"

src_path = str(_SRC)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

__path__ = [str(_PKG)]

_SYMBOL_TO_MODULE = {
    "get_config": "core.config",
    "get_root_dir": "core.config",
    "load_all": "core.data_loader",
    "GraphData": "core.data_loader",
    "local_search": "core.search",
    "global_search": "core.search",
    "build_index": "core.indexer",
    "build_index_sync": "core.indexer",
}

__all__ = [
    "get_config",
    "get_root_dir",
    "load_all",
    "GraphData",
    "local_search",
    "global_search",
    "build_index",
    "build_index_sync",
]

__version__ = "2.0.0"


def __getattr__(name: str) -> Any:
    """Lazily resolve public symbols from the real package modules."""
    module_name = _SYMBOL_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

    module = importlib.import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
