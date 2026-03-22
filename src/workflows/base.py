"""
Workflow Base Types and Utilities

Shared dataclasses and helpers used across all workflow patterns in Part 4.

Workflow Patterns Overview:
    - SequentialWorkflow: Chain agents one after another (analyze → search → report)
    - ConcurrentWorkflow: Run searches in parallel, then synthesize (local + global)
    - HandoffWorkflow: Route to the right specialist (entity vs. themes expert)
"""

from abc import ABC, abstractmethod
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from typing_extensions import Self  # noqa: UP035

if TYPE_CHECKING:
    from agent_framework import MCPStreamableHTTPTool

    from workflows.concurrent import ParallelSearchWorkflow
    from workflows.handoff import ExpertHandoffWorkflow
    from workflows.sequential import ResearchPipelineWorkflow


class WorkflowType(StrEnum):
    """Available workflow patterns."""

    SEQUENTIAL = "sequential"
    CONCURRENT = "concurrent"
    HANDOFF = "handoff"


@dataclass
class WorkflowStep:
    """A single step within a multi-agent workflow.

    Records the agent name, its input prompt, and its output text,
    along with optional timing information.
    """

    agent_name: str
    """Name of the agent that executed this step."""

    input_summary: str
    """Short description of what was passed to this agent."""

    output: str
    """The agent's response text."""

    elapsed_seconds: float = 0.0
    """Time taken to complete this step."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Optional metadata (e.g. which MCP tool was called)."""


@dataclass
class WorkflowResult:
    """Aggregated result from a complete workflow run.

    Contains the final answer, all intermediate steps, total elapsed time,
    and the workflow type that produced this result.
    """

    answer: str
    """The final synthesized answer."""

    workflow_type: WorkflowType
    """Which workflow pattern was used."""

    steps: list[WorkflowStep] = field(default_factory=list)
    """Ordered list of steps with intermediate outputs."""

    total_elapsed_seconds: float = 0.0
    """Wall-clock time for the entire workflow."""

    query: str = ""
    """The original user query."""

    def step_summary(self) -> str:
        """Return a concise human-readable step trace."""
        lines = [f"Workflow: {self.workflow_type.value} ({self.total_elapsed_seconds:.1f}s total)"]
        for i, step in enumerate(self.steps, 1):
            lines.append(f"  Step {i} [{step.agent_name}] ({step.elapsed_seconds:.1f}s): {step.input_summary}")
        return "\n".join(lines)


class MCPWorkflowBase(ABC):
    """Base for workflows that manage a single shared MCP tool connection.

    Encapsulates the async-context-manager lifecycle shared by
    ``ResearchPipelineWorkflow`` and ``ExpertHandoffWorkflow``.

    The MCP tool is managed externally (not via Agent context managers)
    because multiple agents share the same tool instance: only one agent
    uses it at a time, but the connection must persist across agent runs.
    Subclasses only need to implement ``_create_agents``.
    """

    def __init__(self, mcp_url: str | None = None) -> None:
        self._mcp_url = mcp_url
        self._mcp_tool: MCPStreamableHTTPTool | None = None
        self._exit_stack: AsyncExitStack | None = None

    @abstractmethod
    def _create_agents(self, mcp_tool: "MCPStreamableHTTPTool") -> None:
        """Instantiate workflow-specific agents using *mcp_tool*."""

    async def __aenter__(self) -> Self:
        from agents.supervisor import create_mcp_tool

        self._exit_stack = AsyncExitStack()
        self._mcp_tool = create_mcp_tool(self._mcp_url)
        await self._exit_stack.enter_async_context(self._mcp_tool)
        self._create_agents(self._mcp_tool)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if self._exit_stack:
            await self._exit_stack.aclose()


# ---------------------------------------------------------------------------
# Factory Functions for State Isolation (Improvement 4.4)
# ---------------------------------------------------------------------------


def create_sequential_workflow(mcp_url: str | None = None) -> "ResearchPipelineWorkflow":
    """Create a fresh sequential workflow with isolated agent state.

    Each call returns a new instance — agents and MCP tool connections
    are created on ``__aenter__``, ensuring no state leaks between
    requests.

    Args:
        mcp_url: Optional MCP server URL override.

    Returns:
        A new ``ResearchPipelineWorkflow`` ready for ``async with``.

    Example::

        workflow = create_sequential_workflow()
        async with workflow:
            result = await workflow.run("Analyze Project Alpha")
    """
    from workflows.sequential import ResearchPipelineWorkflow

    return ResearchPipelineWorkflow(mcp_url=mcp_url)


def create_concurrent_workflow(mcp_url: str | None = None) -> "ParallelSearchWorkflow":
    """Create a fresh concurrent workflow with isolated agent state.

    Args:
        mcp_url: Optional MCP server URL override.

    Returns:
        A new ``ParallelSearchWorkflow`` ready for ``async with``.
    """
    from workflows.concurrent import ParallelSearchWorkflow

    return ParallelSearchWorkflow(mcp_url=mcp_url)


def create_handoff_workflow(mcp_url: str | None = None) -> "ExpertHandoffWorkflow":
    """Create a fresh handoff workflow with isolated agent state.

    Args:
        mcp_url: Optional MCP server URL override.

    Returns:
        A new ``ExpertHandoffWorkflow`` ready for ``async with``.
    """
    from workflows.handoff import ExpertHandoffWorkflow

    return ExpertHandoffWorkflow(mcp_url=mcp_url)
