"""Shared workflow types, telemetry helpers, and DevUI adapters.

This module centralizes the dataclasses and utilities every workflow implementation
relies on: ``WorkflowResult``/``WorkflowStep`` capture execution traces, while
``MCPWorkflowBase`` and the related helpers provide WorkflowBuilder integration and
DevUI streaming support.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from contextlib import AsyncExitStack
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Awaitable, Callable, cast

from agent_framework import Executor, WorkflowEvent
from typing_extensions import Self

from core.logging_config import workflow_step_logs_enabled

logger = logging.getLogger(__name__)
_STEP_LOGS_ENABLED = workflow_step_logs_enabled()

if TYPE_CHECKING:  # pragma: no cover - import guard for typing only
    from agent_framework import MCPStreamableHTTPTool, Workflow

    from workflows.concurrent import ParallelSearchWorkflow
    from workflows.handoff import ExpertHandoffWorkflow
    from workflows.router import RouterWorkflow
    from workflows.sequential import ResearchPipelineWorkflow


class WorkflowType(StrEnum):
    """Available workflow patterns exposed through DevUI."""

    SEQUENTIAL = "sequential"
    CONCURRENT = "concurrent"
    HANDOFF = "handoff"
    ROUTER = "router"


_STEP_LOGGER_BY_WORKFLOW: dict[WorkflowType, str] = {
    WorkflowType.SEQUENTIAL: "workflows.sequential",
    WorkflowType.CONCURRENT: "workflows.concurrent",
    WorkflowType.HANDOFF: "workflows.handoff",
    WorkflowType.ROUTER: "workflows.router",
}


@dataclass(slots=True)
class StepTelemetry:
    """Internal telemetry emitted by instrumented executors."""

    agent_name: str
    input_summary: str
    output: str
    elapsed_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowStep:
    """Public step payload persisted on ``WorkflowResult``."""

    agent_name: str
    input_summary: str
    output: str
    elapsed_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """Structured workflow output consumed by the DevUI."""

    answer: str
    workflow_type: WorkflowType
    steps: list[WorkflowStep] = field(default_factory=list)
    total_elapsed_seconds: float = 0.0
    query: str = ""

    def step_summary(self) -> str:
        """Return a human-readable summary of the workflow trace."""

        lines = [
            f"Workflow: {self.workflow_type.value} ({self.total_elapsed_seconds:.1f}s total)",
        ]
        for index, step in enumerate(self.steps, 1):
            lines.append(f"  Step {index} [{step.agent_name}] ({step.elapsed_seconds:.1f}s): {step.input_summary}")
        return "\n".join(lines)


class WorkflowGraphSupport:
    """Shared utilities for workflow classes built with WorkflowBuilder."""

    def __init__(self, *, workflow_type: WorkflowType | None = None) -> None:
        self._workflow: Workflow | None = None
        self._executors: list[Any] = []
        self._step_telemetry: list[StepTelemetry] = []
        self._workflow_type: WorkflowType | None = workflow_type

    def get_workflow(self) -> Workflow:
        if self._workflow is None:
            raise RuntimeError("Workflow not built. Did you enter the context manager?")
        return self._workflow.clone()

    def _set_workflow(self, workflow: Workflow, executors: Sequence[Any] | None = None) -> None:
        self._workflow = workflow
        if executors is not None:
            self._executors = list(executors)
            return
        if hasattr(workflow, "get_executors_list"):
            try:
                self._executors = list(workflow.get_executors_list())
            except Exception:  # pragma: no cover - defensive guard
                self._executors = []

    def _record_step(self, telemetry: StepTelemetry) -> None:
        self._step_telemetry.append(telemetry)
        if _STEP_LOGS_ENABLED:
            workflow_type = self._workflow_type or WorkflowType.SEQUENTIAL
            step_logger_name = _STEP_LOGGER_BY_WORKFLOW.get(workflow_type, __name__)
            logging.getLogger(step_logger_name).info(
                "Workflow step [%s] %.2fs | %s",
                telemetry.agent_name,
                telemetry.elapsed_seconds,
                telemetry.input_summary,
            )

    def _reset_step_telemetry(self) -> None:
        self._step_telemetry.clear()

    def iter_step_telemetry(self) -> Sequence[StepTelemetry]:
        return tuple(self._step_telemetry)

    def get_executors_list(self) -> list[Any]:
        if self._workflow and hasattr(self._workflow, "get_executors_list"):
            try:
                return list(self._workflow.get_executors_list())
            except Exception:  # pragma: no cover - defensive guard
                return list(self._executors)
        return list(self._executors)

    def to_dict(self) -> dict[str, Any]:
        if self._workflow is None:
            raise RuntimeError("Workflow not built. Did you enter the context manager?")
        return self._workflow.to_dict()

    @property
    def workflow_type(self) -> WorkflowType:
        if self._workflow_type is None:
            raise RuntimeError("Workflow type not configured for this workflow.")
        return self._workflow_type

    def set_workflow_type(self, workflow_type: WorkflowType) -> None:
        self._workflow_type = workflow_type

    def prepare_run(self, query: str) -> str:
        normalized = ensure_text(query)
        self._reset_step_telemetry()
        return normalized

    def create_stream(
        self,
        normalized_query: str,
    ) -> tuple[Any, Callable[[], Awaitable[WorkflowResult]]]:
        if self._workflow is None:
            raise RuntimeError("Workflow not built. Did you enter the context manager?")

        run_started = time.perf_counter()
        stream = self._workflow.run(normalized_query, stream=True)

        async def finalize() -> WorkflowResult:
            run_result = await stream.get_final_response()
            total_elapsed = time.perf_counter() - run_started
            return self.build_workflow_result(
                normalized_query=normalized_query,
                run_result=run_result,
                total_elapsed=total_elapsed,
            )

        return stream, finalize

    def build_workflow_result(
        self,
        *,
        normalized_query: str,
        run_result: Any,
        total_elapsed: float,
    ) -> WorkflowResult:
        steps = [
            WorkflowStep(
                agent_name=telemetry.agent_name,
                input_summary=telemetry.input_summary,
                output=telemetry.output,
                elapsed_seconds=telemetry.elapsed_seconds,
                metadata=dict(telemetry.metadata),
            )
            for telemetry in self.iter_step_telemetry()
        ]

        outputs: list[Any] = []
        if hasattr(run_result, "get_outputs"):
            try:
                outputs = list(run_result.get_outputs())
            except Exception:  # pragma: no cover - defensive guard
                outputs = []
        elif hasattr(run_result, "outputs"):
            candidate = run_result.outputs
            outputs = list(candidate if isinstance(candidate, list) else [candidate])

        answer = ensure_text(outputs[-1]) if outputs else (steps[-1].output if steps else "")

        status_events: list[Any] = []
        if hasattr(run_result, "status_timeline"):
            try:
                status_events = list(run_result.status_timeline())
            except Exception:  # pragma: no cover - defensive guard
                status_events = []

        if steps and status_events:
            states = [getattr(event.state, "value", getattr(event, "state", None)) for event in status_events]
            status_values = [state for state in states if isinstance(state, str)]
            if status_values:
                steps[-1].metadata.setdefault("status", status_values)

        return WorkflowResult(
            answer=answer,
            workflow_type=self.workflow_type,
            steps=steps,
            total_elapsed_seconds=total_elapsed,
            query=normalized_query,
        )


class InstrumentedAgentExecutor(Executor):
    """Executor wrapper that emits ``StepTelemetry`` entries for DevUI."""

    def __init__(
        self,
        *,
        executor_id: str,
        display_name: str,
        record_step: Callable[[StepTelemetry], None],
    ) -> None:
        super().__init__(id=executor_id)
        self._display_name = display_name
        self._record_step = record_step

    def _emit_step(
        self,
        *,
        input_summary: str,
        output: str,
        elapsed: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._record_step(
            StepTelemetry(
                agent_name=self._display_name,
                input_summary=input_summary,
                output=output,
                elapsed_seconds=elapsed,
                metadata={} if metadata is None else dict(metadata),
            )
        )


# Maintain compatibility with earlier private naming used by workflows.
_InstrumentedAgentExecutor = InstrumentedAgentExecutor


class MCPWorkflowBase(WorkflowGraphSupport, ABC):
    """Base class for workflows that share a single MCP tool connection."""

    def __init__(self, mcp_url: str | None = None, *, workflow_type: WorkflowType) -> None:
        super().__init__(workflow_type=workflow_type)
        self._mcp_url = mcp_url
        self._mcp_tool: MCPStreamableHTTPTool | None = None
        self._exit_stack: AsyncExitStack | None = None

    @abstractmethod
    def _create_agents(self, mcp_tool: MCPStreamableHTTPTool) -> None:
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


def ensure_text(value: Any) -> str:
    """Return a textual representation for DevUI compatibility."""

    if isinstance(value, str):
        return value

    content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            if isinstance(item, str):
                pieces.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    pieces.append(text)
            else:
                text_attr = getattr(item, "text", None)
                if isinstance(text_attr, str):
                    pieces.append(text_attr)
                else:
                    pieces.append(str(item))
        if pieces:
            return "\n".join(pieces)

    text_attr = getattr(value, "text", None)
    if isinstance(text_attr, str):
        return text_attr

    return str(value)


def collect_tool_names(agent: Any) -> list[str]:
    """Return stable tool names for telemetry metadata."""

    names: list[str] = []
    for tool in getattr(agent, "tools", []):
        name = getattr(tool, "name", None)
        names.append(name if isinstance(name, str) else tool.__class__.__name__)
    return names


_STREAM_END = object()


class _WorkflowStreamAdapter:
    """Adapter that satisfies DevUI's streaming expectations."""

    def __init__(
        self,
        event_queue: asyncio.Queue[Any],
        result_future: asyncio.Future[WorkflowResult],
    ) -> None:
        self._event_queue = event_queue
        self._result_future = result_future

    def __aiter__(self) -> _WorkflowStreamAdapter:
        return self

    async def __anext__(self) -> Any:
        item = await self._event_queue.get()
        if item is _STREAM_END:
            raise StopAsyncIteration
        return item

    async def get_final_response(self) -> WorkflowResult:
        return await self._result_future

    def get_structured_result(self) -> WorkflowResult:
        if not self._result_future.done():
            raise RuntimeError("Final response not available yet; await get_final_response() first")
        return self._result_future.result()


WORKFLOW_START_EXECUTOR: dict[WorkflowType, str] = {
    WorkflowType.SEQUENTIAL: "QueryAnalyzer",
    WorkflowType.CONCURRENT: "QueryBroadcast",
    WorkflowType.HANDOFF: "Router",
    WorkflowType.ROUTER: "WorkflowRouter",
}

WORKFLOW_EXECUTOR_DETAILS: dict[WorkflowType, dict[str, dict[str, str]] | None] = {
    WorkflowType.SEQUENTIAL: {
        "QueryAnalyzer": {"type": "AgentExecutor", "display_name": "QueryAnalyzer"},
        "KnowledgeSearcher": {"type": "AgentExecutor", "display_name": "KnowledgeSearcher"},
        "ReportWriter": {"type": "AgentExecutor", "display_name": "ReportWriter"},
    },
    WorkflowType.CONCURRENT: {
        "QueryBroadcast": {"type": "Executor", "display_name": "QueryBroadcast"},
        "EntitySearcher": {"type": "AgentExecutor", "display_name": "EntitySearcher"},
        "ThemesSearcher": {"type": "AgentExecutor", "display_name": "ThemesSearcher"},
        "AnswerSynthesizer": {"type": "AgentExecutor", "display_name": "AnswerSynthesizer"},
    },
    WorkflowType.HANDOFF: {
        "Router": {"type": "AgentExecutor", "display_name": "Router"},
        "EntityExpert": {"type": "AgentExecutor", "display_name": "EntityExpert"},
        "ThemesExpert": {"type": "AgentExecutor", "display_name": "ThemesExpert"},
        "HandoffComposer": {"type": "AgentExecutor", "display_name": "AnswerComposer"},
    },
    WorkflowType.ROUTER: {
        "WorkflowRouter": {"type": "Router", "display_name": "WorkflowRouter"},
        "SequentialWorkflow": {"type": "WorkflowRunner", "display_name": "SequentialWorkflow"},
        "QueryAnalyzer": {"type": "AgentExecutor", "display_name": "QueryAnalyzer"},
        "KnowledgeSearcher": {"type": "AgentExecutor", "display_name": "KnowledgeSearcher"},
        "ReportWriter": {"type": "AgentExecutor", "display_name": "ReportWriter"},
        "ConcurrentWorkflow": {"type": "WorkflowRunner", "display_name": "ConcurrentWorkflow"},
        "QueryBroadcast": {"type": "Executor", "display_name": "QueryBroadcast"},
        "EntitySearcher": {"type": "AgentExecutor", "display_name": "EntitySearcher"},
        "ThemesSearcher": {"type": "AgentExecutor", "display_name": "ThemesSearcher"},
        "AnswerSynthesizer": {"type": "AgentExecutor", "display_name": "AnswerSynthesizer"},
        "HandoffWorkflow": {"type": "WorkflowRunner", "display_name": "HandoffWorkflow"},
        "Router": {"type": "AgentExecutor", "display_name": "Router"},
        "EntityExpert": {"type": "AgentExecutor", "display_name": "EntityExpert"},
        "ThemesExpert": {"type": "AgentExecutor", "display_name": "ThemesExpert"},
        "HandoffComposer": {"type": "AgentExecutor", "display_name": "AnswerComposer"},
    },
}

WORKFLOW_EDGE_BLUEPRINTS: dict[WorkflowType, list[dict[str, str]]] = {
    WorkflowType.SEQUENTIAL: [
        {"source_id": "QueryAnalyzer", "target_id": "KnowledgeSearcher"},
        {"source_id": "KnowledgeSearcher", "target_id": "ReportWriter"},
    ],
    WorkflowType.CONCURRENT: [
        {"source_id": "QueryBroadcast", "target_id": "EntitySearcher"},
        {"source_id": "QueryBroadcast", "target_id": "ThemesSearcher"},
        {"source_id": "EntitySearcher", "target_id": "AnswerSynthesizer"},
        {"source_id": "ThemesSearcher", "target_id": "AnswerSynthesizer"},
    ],
    WorkflowType.HANDOFF: [
        {"source_id": "Router", "target_id": "EntityExpert", "condition_name": "entity/both"},
        {"source_id": "Router", "target_id": "ThemesExpert", "condition_name": "themes/both"},
        {"source_id": "EntityExpert", "target_id": "HandoffComposer"},
        {"source_id": "ThemesExpert", "target_id": "HandoffComposer"},
    ],
    WorkflowType.ROUTER: [
        {"source_id": "WorkflowRouter", "target_id": "SequentialWorkflow", "condition_name": "sequential"},
        {"source_id": "SequentialWorkflow", "target_id": "QueryAnalyzer"},
        {"source_id": "QueryAnalyzer", "target_id": "KnowledgeSearcher"},
        {"source_id": "KnowledgeSearcher", "target_id": "ReportWriter"},
        {"source_id": "WorkflowRouter", "target_id": "ConcurrentWorkflow", "condition_name": "concurrent"},
        {"source_id": "ConcurrentWorkflow", "target_id": "QueryBroadcast"},
        {"source_id": "QueryBroadcast", "target_id": "EntitySearcher"},
        {"source_id": "QueryBroadcast", "target_id": "ThemesSearcher"},
        {"source_id": "EntitySearcher", "target_id": "AnswerSynthesizer"},
        {"source_id": "ThemesSearcher", "target_id": "AnswerSynthesizer"},
        {"source_id": "WorkflowRouter", "target_id": "HandoffWorkflow", "condition_name": "handoff"},
        {"source_id": "HandoffWorkflow", "target_id": "Router"},
        {"source_id": "Router", "target_id": "EntityExpert", "condition_name": "entity/both"},
        {"source_id": "Router", "target_id": "ThemesExpert", "condition_name": "themes/both"},
        {"source_id": "EntityExpert", "target_id": "HandoffComposer"},
        {"source_id": "ThemesExpert", "target_id": "HandoffComposer"},
    ],
}

DEFAULT_EXECUTORS: dict[WorkflowType, list[str]] = {
    WorkflowType.SEQUENTIAL: ["QueryAnalyzer", "KnowledgeSearcher", "ReportWriter"],
    WorkflowType.CONCURRENT: ["QueryBroadcast", "EntitySearcher", "ThemesSearcher", "AnswerSynthesizer"],
    WorkflowType.HANDOFF: ["Router", "EntityExpert", "ThemesExpert", "HandoffComposer"],
    WorkflowType.ROUTER: [
        "WorkflowRouter",
        "SequentialWorkflow",
        "QueryAnalyzer",
        "KnowledgeSearcher",
        "ReportWriter",
        "ConcurrentWorkflow",
        "QueryBroadcast",
        "EntitySearcher",
        "ThemesSearcher",
        "AnswerSynthesizer",
        "HandoffWorkflow",
        "Router",
        "EntityExpert",
        "ThemesExpert",
        "HandoffComposer",
    ],
}


def build_workflow_blueprint(
    workflow_type: WorkflowType,
    *,
    name: str,
    description: str,
) -> dict[str, Any]:
    """Return a static workflow graph description for DevUI visualization."""

    executor_details = WORKFLOW_EXECUTOR_DETAILS.get(workflow_type) or {}
    edges = WORKFLOW_EDGE_BLUEPRINTS.get(workflow_type, [])
    start_executor = WORKFLOW_START_EXECUTOR.get(workflow_type) or next(iter(executor_details), "Executor")

    blueprint: dict[str, Any] = {
        "name": name,
        "id": f"maf-workflow-{workflow_type.value}",
        "start_executor_id": start_executor,
        "max_iterations": 100,
        "edge_groups": [],
        "executors": {},
        "output_executors": None,
        "intermediate_executors": None,
        "description": description,
    }

    for index, edge in enumerate(edges, 1):
        group = {
            "id": f"maf-{workflow_type.value}-edge-{index}",
            "type": "SingleEdgeGroup",
            "edges": [edge],
        }
        cast(list[dict[str, Any]], blueprint["edge_groups"]).append(group)

    blueprint_executors: dict[str, dict[str, Any]] = {}
    for executor_id, details in executor_details.items():
        blueprint_executors[executor_id] = {"id": executor_id, **details}

    blueprint["executors"] = blueprint_executors
    return deepcopy(blueprint)


class MCPWorkflowRunner:
    """Adapter that exposes WorkflowBuilder patterns to the DevUI."""

    def __init__(
        self,
        factory: Callable[[str | None], Any],
        *,
        workflow_type: WorkflowType,
        mcp_url: str | None = None,
        name: str | None = None,
        description: str = "",
        executors: list[str] | None = None,
    ) -> None:
        self._factory = factory
        self._workflow_type = workflow_type
        self._mcp_url = mcp_url
        self.name = name or f"{workflow_type.value.title()} Workflow"
        self.description = description
        self.executors = executors or list(DEFAULT_EXECUTORS.get(workflow_type, []))
        self._blueprint_cache: dict[str, Any] | None = None

    async def __aenter__(self) -> MCPWorkflowRunner:  # pragma: no cover - passthrough
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:  # pragma: no cover - passthrough
        return None

    def run(
        self,
        message: Any,
        *,
        stream: bool = False,
        include_status_events: bool = True,
        **run_kwargs: Any,
    ) -> asyncio.Task[WorkflowResult] | _WorkflowStreamAdapter:
        normalized_message = ensure_text(message)
        if stream:
            event_queue: asyncio.Queue[Any] = asyncio.Queue()
            result_future: asyncio.Future[WorkflowResult] = asyncio.get_running_loop().create_future()
            adapter = _WorkflowStreamAdapter(event_queue, result_future)

            async def _run_stream() -> None:
                try:
                    await event_queue.put(
                        WorkflowEvent(
                            type=cast(Any, "progress"),
                            data={
                                "stage": "workflow_runner_started",
                                "workflow_type": self._workflow_type.value,
                            },
                        )
                    )
                    async with self._factory(self._mcp_url) as workflow:
                        normalized_query = workflow.prepare_run(normalized_message)
                        stream_result = workflow.create_stream(normalized_query)
                        if inspect.isawaitable(stream_result):
                            stream_obj, finalize = await stream_result
                        else:
                            stream_obj, finalize = stream_result
                        async for event in stream_obj:
                            await event_queue.put(event)
                        final_result = await finalize()
                        if not result_future.done():
                            result_future.set_result(final_result)
                        await event_queue.put(
                            WorkflowEvent(
                                type=cast(Any, "progress"),
                                data={
                                    "stage": "workflow_runner_completed",
                                    "workflow_type": self._workflow_type.value,
                                },
                            )
                        )
                except Exception as exc:
                    if not result_future.done():
                        result_future.set_exception(exc)
                    await event_queue.put(WorkflowEvent(type="error", data=str(exc)))
                finally:
                    await event_queue.put(_STREAM_END)

            asyncio.create_task(_run_stream())
            return adapter

        return asyncio.create_task(self._execute_workflow(normalized_message))

    def run_structured(
        self,
        message: Any,
        *,
        include_status_events: bool = True,
        **run_kwargs: Any,
    ) -> asyncio.Task[WorkflowResult]:
        return asyncio.create_task(self._execute_workflow(ensure_text(message)))

    def get_executors_list(self) -> list[str]:
        return list(self.executors)

    async def _execute_workflow(self, message: str) -> WorkflowResult:
        async with self._factory(self._mcp_url) as workflow:
            return cast(WorkflowResult, await workflow.run(message))

    def to_dict(self) -> dict[str, Any]:
        if self._blueprint_cache is not None:
            return deepcopy(self._blueprint_cache)

        if self._workflow_type is WorkflowType.ROUTER:
            blueprint = build_workflow_blueprint(
                self._workflow_type,
                name=self.name,
                description=self.description,
            )
            self._blueprint_cache = deepcopy(blueprint)
            return blueprint

        try:
            blueprint = self._build_dynamic_blueprint()
        except Exception as exc:  # pragma: no cover - fallback path
            logging.getLogger(__name__).warning(
                "Falling back to static workflow blueprint for %s due to error: %s",
                self._workflow_type.value,
                exc,
            )
            blueprint = build_workflow_blueprint(
                self._workflow_type,
                name=self.name,
                description=self.description,
            )

        blueprint["name"] = self.name
        blueprint["description"] = self.description
        blueprint.setdefault("id", f"maf-workflow-{self._workflow_type.value}")

        self._blueprint_cache = deepcopy(blueprint)
        return blueprint

    def _build_dynamic_blueprint(self) -> dict[str, Any]:
        workflow = self._factory(self._mcp_url)
        if not isinstance(workflow, MCPWorkflowBase):
            raise TypeError(
                "Workflow factory must return an MCPWorkflowBase implementation to build dynamic blueprint",
            )

        from agents.supervisor import create_mcp_tool

        dummy_tool = create_mcp_tool(self._mcp_url)
        workflow._create_agents(dummy_tool)

        dynamic_blueprint = workflow.get_workflow().to_dict()

        return dynamic_blueprint


# ---------------------------------------------------------------------------
# Factory Functions for State Isolation (Improvement 4.4)
# ---------------------------------------------------------------------------


def create_sequential_workflow(mcp_url: str | None = None) -> ResearchPipelineWorkflow:
    """Create a fresh sequential workflow with isolated agent state."""

    from workflows.sequential import ResearchPipelineWorkflow

    return ResearchPipelineWorkflow(mcp_url=mcp_url)


def create_concurrent_workflow(mcp_url: str | None = None) -> ParallelSearchWorkflow:
    """Create a fresh concurrent workflow with isolated agent state."""

    from workflows.concurrent import ParallelSearchWorkflow

    return ParallelSearchWorkflow(mcp_url=mcp_url)


def create_handoff_workflow(mcp_url: str | None = None) -> ExpertHandoffWorkflow:
    """Create a fresh handoff workflow with isolated agent state."""

    from workflows.handoff import ExpertHandoffWorkflow

    return ExpertHandoffWorkflow(mcp_url=mcp_url)


def create_router_workflow(mcp_url: str | None = None) -> RouterWorkflow:
    """Create a workflow router that delegates to other patterns."""

    from workflows.router import RouterWorkflow

    return RouterWorkflow(mcp_url=mcp_url)


def create_sequential_workflow_runner(mcp_url: str | None = None) -> MCPWorkflowRunner:
    """Expose the sequential workflow to DevUI as a runnable entity."""

    return MCPWorkflowRunner(
        create_sequential_workflow,
        workflow_type=WorkflowType.SEQUENTIAL,
        mcp_url=mcp_url,
        name="Sequential Workflow",
        description="Three-step research pipeline (analyze → search → report).",
    )


def create_concurrent_workflow_runner(mcp_url: str | None = None) -> MCPWorkflowRunner:
    """Expose the concurrent workflow to DevUI as a runnable entity."""

    return MCPWorkflowRunner(
        create_concurrent_workflow,
        workflow_type=WorkflowType.CONCURRENT,
        mcp_url=mcp_url,
        name="Concurrent Workflow",
        description="Parallel entity and themes search with synthesis.",
    )


def create_handoff_workflow_runner(mcp_url: str | None = None) -> MCPWorkflowRunner:
    """Expose the handoff workflow to DevUI as a runnable entity."""

    return MCPWorkflowRunner(
        create_handoff_workflow,
        workflow_type=WorkflowType.HANDOFF,
        mcp_url=mcp_url,
        name="Handoff Workflow",
        description="Router delegates to entity or themes specialists based on the query.",
    )


def create_router_workflow_runner(mcp_url: str | None = None) -> MCPWorkflowRunner:
    """Expose the router workflow to DevUI as a runnable entity."""

    return MCPWorkflowRunner(
        create_router_workflow,
        workflow_type=WorkflowType.ROUTER,
        mcp_url=mcp_url,
        name="Router Workflow",
        description="Model router selects sequential, concurrent, or handoff execution per query.",
    )
