"""Unit tests for the workflow router."""

from __future__ import annotations

import pytest

from agents.router_classifier import RouterClassification
from workflows.base import WorkflowResult, WorkflowStep, WorkflowType
from workflows.router import RouterWorkflow


class StubClassifier:
    """Minimal classifier stub for testing."""

    def __init__(self, responses: list[RouterClassification | Exception]) -> None:
        self._responses = responses
        self.entered = False
        self.calls: list[str] = []

    async def __aenter__(self) -> "StubClassifier":
        self.entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.entered = False

    async def classify(self, query: str) -> RouterClassification:
        if not self.entered:
            raise RuntimeError("Classifier must be used inside context")
        self.calls.append(query)
        if not self._responses:
            raise RuntimeError("No stub responses available")
        next_response = self._responses.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return next_response


class StubWorkflow:
    """Async context manager that records invocations."""

    def __init__(self, result: WorkflowResult) -> None:
        self._result = result
        self.entered = False
        self.run_queries: list[str] = []

    async def __aenter__(self) -> "StubWorkflow":
        self.entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.entered = False

    async def run(self, query: str) -> WorkflowResult:
        self.run_queries.append(query)
        return self._result


def _make_result(workflow_type: WorkflowType, answer: str) -> WorkflowResult:
    step = WorkflowStep(
        agent_name="InnerAgent",
        input_summary="Process query",
        output="Step output",
        elapsed_seconds=0.4,
    )
    return WorkflowResult(
        answer=answer,
        workflow_type=workflow_type,
        steps=[step],
        total_elapsed_seconds=0.4,
        query="",
    )


@pytest.mark.asyncio
async def test_router_delegates_to_selected_workflow() -> None:
    classification = RouterClassification(
        workflow=WorkflowType.CONCURRENT,
        raw_response="{\"workflow\": \"concurrent\"}",
        reason="Needs both perspectives",
        confidence_score=95,
        elapsed_seconds=0.1,
        model_name="router-mini",
        router_mode="balanced",
        router_subset="knowledge",
    )
    classifier = StubClassifier([classification])

    inner_result = _make_result(WorkflowType.CONCURRENT, "Concurrent answer")
    created: list[StubWorkflow] = []

    def concurrent_factory(_mcp_url: str | None) -> StubWorkflow:
        workflow = StubWorkflow(inner_result)
        created.append(workflow)
        return workflow

    workflow = RouterWorkflow(
        classifier=classifier,
        workflow_factories={WorkflowType.CONCURRENT: concurrent_factory},
    )

    async with workflow:
        result = await workflow.run("Tell me everything about Project Alpha")

    assert classifier.calls == ["Tell me everything about Project Alpha"]
    assert created and created[0].run_queries == ["Tell me everything about Project Alpha"]
    assert result.workflow_type == WorkflowType.ROUTER
    assert result.answer == "Concurrent answer"
    assert result.steps[0].agent_name == "WorkflowRouter"
    assert result.steps[0].metadata["routed_workflow"] == WorkflowType.CONCURRENT.value
    assert result.steps[0].metadata["classified_workflow"] == WorkflowType.CONCURRENT.value
    assert result.steps[0].metadata["router_model"] == "router-mini"
    assert result.steps[0].metadata["router_mode"] == "balanced"
    assert result.steps[0].metadata["router_subset"] == "knowledge"
    assert result.steps[0].metadata["confidence_score"] == 95
    assert result.steps[0].metadata["classifier_status"] == "success"
    assert result.steps[0].metadata["classifier_attempts"] == 1
    assert result.steps[1:] == inner_result.steps
    assert result.query == "Tell me everything about Project Alpha"


@pytest.mark.asyncio
async def test_router_falls_back_to_sequential(monkeypatch: pytest.MonkeyPatch) -> None:
    classification = RouterClassification(
        workflow=WorkflowType.ROUTER,
        raw_response="fallback",
        reason=None,
        confidence_score=None,
        elapsed_seconds=0.05,
        model_name="router-mini",
    )
    classifier = StubClassifier([classification])

    inner_result = _make_result(WorkflowType.SEQUENTIAL, "Sequential answer")
    created: list[StubWorkflow] = []

    def sequential_factory(_mcp_url: str | None) -> StubWorkflow:
        workflow = StubWorkflow(inner_result)
        created.append(workflow)
        return workflow

    workflow = RouterWorkflow(
        classifier=classifier,
        workflow_factories={WorkflowType.SEQUENTIAL: sequential_factory},
    )

    async with workflow:
        result = await workflow.run("Fallback question")

    assert classifier.calls == ["Fallback question"]
    assert created and created[0].run_queries == ["Fallback question"]
    assert result.steps[0].metadata["routed_workflow"] == WorkflowType.SEQUENTIAL.value
    assert result.steps[0].metadata["classified_workflow"] == WorkflowType.ROUTER.value
    assert result.steps[0].metadata["fallback_reason"] == "missing_confidence_score"
    assert result.steps[0].metadata["classifier_status"] == "success"
    assert result.steps[0].metadata["router_model"] == "router-mini"
    assert result.steps[1:] == inner_result.steps
    assert result.answer == "Sequential answer"


@pytest.mark.asyncio
async def test_router_requires_context_manager() -> None:
    classification = RouterClassification(
        workflow=WorkflowType.SEQUENTIAL,
        raw_response="sequential",
        reason="",
        confidence_score=85,
        elapsed_seconds=0.01,
        model_name="router-mini",
    )
    classifier = StubClassifier([classification])
    workflow = RouterWorkflow(classifier=classifier)

    with pytest.raises(RuntimeError):
        await workflow.run("Query outside context")


@pytest.mark.asyncio
async def test_router_retries_transient_classifier_error_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classification = RouterClassification(
        workflow=WorkflowType.HANDOFF,
        raw_response="{\"workflow\": \"handoff\"}",
        reason="Direct specialist route.",
        confidence_score=82,
        model_name="router-mini",
    )
    classifier = StubClassifier([
        TimeoutError("temporary timeout"),
        classification,
    ])

    inner_result = _make_result(WorkflowType.HANDOFF, "Handoff answer")

    async def _no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("workflows.router.asyncio.sleep", _no_sleep)

    workflow = RouterWorkflow(
        classifier=classifier,
        workflow_factories={WorkflowType.HANDOFF: lambda _mcp_url: StubWorkflow(inner_result)},
    )

    async with workflow:
        result = await workflow.run("Retry question")

    assert classifier.calls == ["Retry question", "Retry question"]
    assert result.steps[0].metadata["routed_workflow"] == WorkflowType.HANDOFF.value
    assert result.steps[0].metadata["classifier_status"] == "success"
    assert result.steps[0].metadata["classifier_attempts"] == 2


@pytest.mark.asyncio
async def test_router_classifier_failure_falls_back_to_sequential_with_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classifier = StubClassifier([RuntimeError("router unavailable")])

    inner_result = _make_result(WorkflowType.SEQUENTIAL, "Sequential fallback answer")
    created: list[StubWorkflow] = []

    def sequential_factory(_mcp_url: str | None) -> StubWorkflow:
        workflow = StubWorkflow(inner_result)
        created.append(workflow)
        return workflow

    async def _no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("workflows.router.asyncio.sleep", _no_sleep)

    workflow = RouterWorkflow(
        classifier=classifier,
        workflow_factories={WorkflowType.SEQUENTIAL: sequential_factory},
    )

    async with workflow:
        result = await workflow.run("Fallback by error")

    assert created and created[0].run_queries == ["Fallback by error"]
    assert classifier.calls == ["Fallback by error"]
    assert result.steps[0].metadata["routed_workflow"] == WorkflowType.SEQUENTIAL.value
    assert result.steps[0].metadata["classified_workflow"] == WorkflowType.SEQUENTIAL.value
    assert result.steps[0].metadata["classifier_status"] == "fallback"
    assert result.steps[0].metadata["fallback_reason"] == "classifier_error"
    assert result.steps[0].metadata["classifier_attempts"] == 1
    assert "router unavailable" in result.steps[0].metadata["classifier_error"]


@pytest.mark.asyncio
async def test_router_low_confidence_degrades_to_sequential() -> None:
    classification = RouterClassification(
        workflow=WorkflowType.CONCURRENT,
        raw_response='{"workflow": "concurrent"}',
        reason="Uncertain route.",
        confidence_score=40,
        elapsed_seconds=0.05,
        model_name="router-mini",
    )
    classifier = StubClassifier([classification])

    inner_result = _make_result(WorkflowType.SEQUENTIAL, "Sequential by low confidence")
    created: list[StubWorkflow] = []

    def sequential_factory(_mcp_url: str | None) -> StubWorkflow:
        workflow = StubWorkflow(inner_result)
        created.append(workflow)
        return workflow

    workflow = RouterWorkflow(
        classifier=classifier,
        workflow_factories={WorkflowType.SEQUENTIAL: sequential_factory},
    )

    async with workflow:
        result = await workflow.run("Ambiguous question")

    assert created and created[0].run_queries == ["Ambiguous question"]
    assert result.steps[0].metadata["classified_workflow"] == WorkflowType.CONCURRENT.value
    assert result.steps[0].metadata["routed_workflow"] == WorkflowType.SEQUENTIAL.value
    assert result.steps[0].metadata["fallback_reason"] == "low_confidence_score"


@pytest.mark.asyncio
async def test_router_normalizes_dict_query_payload() -> None:
    classification = RouterClassification(
        workflow=WorkflowType.SEQUENTIAL,
        raw_response='{"workflow": "sequential"}',
        reason="",
        confidence_score=88,
        elapsed_seconds=0.01,
        model_name="router-mini",
    )
    classifier = StubClassifier([classification])

    inner_result = _make_result(WorkflowType.SEQUENTIAL, "Sequential answer")
    captured_query: list[str] = []

    class QueryCaptureWorkflow(StubWorkflow):
        async def run(self, query: str) -> WorkflowResult:
            captured_query.append(query)
            return await super().run(query)

    workflow = RouterWorkflow(
        classifier=classifier,
        workflow_factories={WorkflowType.SEQUENTIAL: lambda _mcp_url: QueryCaptureWorkflow(inner_result)},
    )

    async with workflow:
        result = await workflow.run({"input": "What are the key projects and their tech stack?"})

    assert captured_query == ["What are the key projects and their tech stack?"]
    assert result.query == "What are the key projects and their tech stack?"
