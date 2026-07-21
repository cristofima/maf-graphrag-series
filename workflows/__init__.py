"""Shim package that exposes ``src/workflows`` for ``python -m`` execution."""

from __future__ import annotations

import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
_PKG = _SRC / "workflows"

src_path = str(_SRC)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

__path__ = [str(_PKG)]

from workflows.base import (
    WorkflowResult,
    WorkflowStep,
    WorkflowType,
    create_concurrent_workflow,
    create_handoff_workflow,
    create_sequential_workflow,
)
from workflows.concurrent import ParallelSearchWorkflow
from workflows.handoff import ExpertHandoffWorkflow
from workflows.sequential import ResearchPipelineWorkflow

__all__ = [
    "WorkflowResult",
    "WorkflowStep",
    "WorkflowType",
    "ResearchPipelineWorkflow",
    "ParallelSearchWorkflow",
    "ExpertHandoffWorkflow",
    "create_sequential_workflow",
    "create_concurrent_workflow",
    "create_handoff_workflow",
]
