"""Shim package that exposes ``src/mcp_server`` for ``python -m`` execution."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
_PKG = _SRC / "mcp_server"

src_path = str(_SRC)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

__path__ = [str(_PKG)]

_SYMBOL_TO_MODULE = {
    "MCPConfig": "mcp_server.config",
    "create_mcp_server": "mcp_server.server",
}

__all__ = ["MCPConfig", "create_mcp_server"]


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
