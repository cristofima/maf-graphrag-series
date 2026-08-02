"""Shim package that exposes ``src/workflows`` for ``python -m`` execution."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
_PKG = _SRC / "workflows"

src_path = str(_SRC)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

__path__ = [str(_PKG)]

_MOD_BASE = "workflows.base"
_MOD_SEQUENTIAL = "workflows.sequential"
_MOD_CONCURRENT = "workflows.concurrent"
_MOD_HANDOFF = "workflows.handoff"
_MOD_ROUTER = "workflows.router"

_SYMBOL_TO_MODULE = {
    # Base types
    "WorkflowResult": _MOD_BASE,
    "WorkflowStep": _MOD_BASE,
    "WorkflowType": _MOD_BASE,
    # Workflow classes
    "ResearchPipelineWorkflow": _MOD_SEQUENTIAL,
    "ParallelSearchWorkflow": _MOD_CONCURRENT,
    "ExpertHandoffWorkflow": _MOD_HANDOFF,
    "RouterWorkflow": _MOD_ROUTER,
    # Factory functions
    "create_sequential_workflow": _MOD_BASE,
    "create_concurrent_workflow": _MOD_BASE,
    "create_handoff_workflow": _MOD_BASE,
    "create_router_workflow": _MOD_BASE,
}

__all__ = [
    "WorkflowResult",
    "WorkflowStep",
    "WorkflowType",
    "RouterWorkflow",
    "ResearchPipelineWorkflow",
    "ParallelSearchWorkflow",
    "ExpertHandoffWorkflow",
    "create_router_workflow",
    "create_sequential_workflow",
    "create_concurrent_workflow",
    "create_handoff_workflow",
]


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
