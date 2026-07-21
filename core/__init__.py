"""Shim package that exposes ``src/core`` for ``python -m`` execution."""

from __future__ import annotations

import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
_PKG = _SRC / "core"

src_path = str(_SRC)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

__path__ = [str(_PKG)]

from core.config import get_config, get_root_dir
from core.data_loader import GraphData, load_all
from core.indexer import build_index, build_index_sync
from core.search import global_search, local_search

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
