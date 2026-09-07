"""Workflow orchestration patterns for the MAF + GraphRAG series.

Exports the production `RouterWorkflow` alongside the sequential, concurrent,
and expert handoff patterns used for demos and regression tests. Each factory
returns a fresh WorkflowBuilder graph so router agents, MCP tools, and Azure
clients stay isolated per request.
"""

from maf_graphrag.workflows.base import (
    WorkflowResult,
    WorkflowStep,
    WorkflowType,
    create_concurrent_workflow,
    create_handoff_workflow,
    create_router_workflow,
    create_sequential_workflow,
)
from maf_graphrag.workflows.concurrent import ParallelSearchWorkflow
from maf_graphrag.workflows.handoff import ExpertHandoffWorkflow
from maf_graphrag.workflows.sequential import ResearchPipelineWorkflow

__all__ = [
    # Base types
    "WorkflowResult",
    "WorkflowStep",
    "WorkflowType",
    # Workflow classes
    "ResearchPipelineWorkflow",
    "ParallelSearchWorkflow",
    "ExpertHandoffWorkflow",
    "RouterWorkflow",
    "RouterWorkflowAgentAdapter",
    # Factory functions (state isolation)
    "create_sequential_workflow",
    "create_concurrent_workflow",
    "create_handoff_workflow",
    "create_router_workflow",
]


def __getattr__(name: str) -> object:
    """Lazily resolve router symbols to avoid a circular import via agents.router_classifier."""
    if name == "RouterWorkflow":
        from maf_graphrag.workflows.router import RouterWorkflow

        return RouterWorkflow
    if name == "RouterWorkflowAgentAdapter":
        from maf_graphrag.workflows.router_agent import RouterWorkflowAgentAdapter

        return RouterWorkflowAgentAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
