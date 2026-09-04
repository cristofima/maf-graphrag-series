"""
MAF + GraphRAG Series - Workflows Module
=========================================

Part 4: Workflow Patterns (Microsoft Agent Framework Orchestrations)

This module implements three multi-agent workflow patterns that build on
the single-agent Knowledge Captain from Part 3:

    - SequentialWorkflow: Chain agents in a pipeline (analyze → search → write)
    - ConcurrentWorkflow: Run searches in parallel, then synthesize results
    - HandoffWorkflow:    Route to specialist agents based on query type

All workflows connect to the same GraphRAG MCP Server from Part 2.

Usage:
    # Sequential Research Pipeline
    from maf_graphrag.workflows import ResearchPipelineWorkflow

    async with ResearchPipelineWorkflow() as workflow:
        result = await workflow.run("What are the key projects and their technology stack?")
        print(result.answer)
        print(result.step_summary())

    # Concurrent Parallel Search
    from maf_graphrag.workflows import ParallelSearchWorkflow

    async with ParallelSearchWorkflow() as workflow:
        result = await workflow.run("Who leads Project Alpha and what are the main themes?")
        print(result.answer)

    # Expert Handoff Router
    from maf_graphrag.workflows import ExpertHandoffWorkflow

    async with ExpertHandoffWorkflow() as workflow:
        result = await workflow.run("Who leads Project Alpha?")
        print(result.answer)

See also:
    - run_workflow.py: CLI demo for all workflow patterns
    - workflows/README.md: Architecture diagrams and detailed documentation
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
