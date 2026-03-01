"""
Workflow Base Types and Utilities

Shared dataclasses and helpers used across all workflow patterns in Part 4.

Workflow Patterns Overview:
    - SequentialWorkflow: Chain agents one after another (analyze → search → report)
    - ConcurrentWorkflow: Run searches in parallel, then synthesize (local + global)
    - HandoffWorkflow: Route to the right specialist (entity vs. themes expert)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkflowType(str, Enum):
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
