"""Tests for the router-agent adapter surface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
from agent_framework import InMemoryCheckpointStorage

from agents.session_store import InMemorySessionStore, SessionKey
from workflows.base import WorkflowResult, WorkflowStep, WorkflowType
from workflows.router_agent import RouterWorkflowAgentAdapter


class _StubRouterWorkflow:
    async def __aenter__(self) -> _StubRouterWorkflow:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object
    ) -> None:
        return None

    def prepare_run(self, message: object) -> str:
        return str(message)

    async def run(self, query: str, **kwargs: Any) -> WorkflowResult:
        return WorkflowResult(
            answer=f"answer::{query}",
            workflow_type=WorkflowType.ROUTER,
            steps=[
                WorkflowStep(
                    agent_name="WorkflowRouter",
                    input_summary="Classify query",
                    output="Workflow: sequential",
                    metadata={
                        "classified_workflow": "sequential",
                        "routed_workflow": "sequential",
                        "classifier_status": "success",
                        "classifier_attempts": 1,
                    },
                )
            ],
            query=query,
        )

    async def create_stream(
        self,
        normalized_query: str,
        *,
        session_telemetry: Any = None,
        **kwargs: Any,
    ) -> tuple[Any, Any]:
        async def _stream() -> AsyncIterator[Any]:
            yield SimpleNamespace(
                type="progress",
                data={"stage": "router_delegation", "routed_workflow": "sequential"},
            )

        async def _finalize() -> WorkflowResult:
            return WorkflowResult(
                answer=f"stream-answer::{normalized_query}",
                workflow_type=WorkflowType.ROUTER,
                steps=[
                    WorkflowStep(
                        agent_name="WorkflowRouter",
                        input_summary="Classify query",
                        output="Workflow: sequential",
                        metadata={
                            "classified_workflow": "sequential",
                            "routed_workflow": "sequential",
                            "classifier_status": "success",
                            "classifier_attempts": 1,
                        },
                    )
                ],
                query=normalized_query,
            )

        return _stream(), _finalize


@pytest.mark.asyncio
async def test_router_agent_adapter_delegates_without_changing_router_contract() -> None:
    received_kwargs: dict[str, Any] = {}

    class _ContractCapture(_StubRouterWorkflow):
        async def run(self, query: str, **kwargs: Any) -> WorkflowResult:
            received_kwargs.update(kwargs)
            return await super().run(query, **kwargs)

    adapter = RouterWorkflowAgentAdapter(
        workflow_factory=lambda _mcp_url: _ContractCapture(),
        checkpoint_storage=InMemoryCheckpointStorage(),
    )

    result = await adapter.run(
        {"query": "Who leads Project Alpha?"},
        session_telemetry={"session_id": "session-1", "turn_index": 1},
    )

    assert result.answer == "answer::{'query': 'Who leads Project Alpha?'}"
    metadata = result.steps[0].metadata
    assert metadata["classified_workflow"] == "sequential"
    assert metadata["routed_workflow"] == "sequential"
    assert metadata["classifier_status"] == "success"
    assert metadata["classifier_attempts"] == 1
    assert received_kwargs["session_telemetry"] == {"session_id": "session-1", "turn_index": 1}
    assert isinstance(received_kwargs["checkpoint_storage"], InMemoryCheckpointStorage)


@pytest.mark.asyncio
async def test_adapter_create_stream_merges_session_record_telemetry() -> None:
    store = InMemorySessionStore(
        ttl_seconds=300,
        max_count=100,
        cleanup_interval_seconds=60,
        max_history_groups=10,
    )
    key = SessionKey.create(channel_id="test", conversation_id="conv-1", user_id="user-1")
    record, _ = await store.get_or_create(key.session_id)
    store.append_turn(record, user_text="hello", assistant_text="hi")

    received_telemetry: dict[str, Any] = {}

    class _TelemetryCapture(_StubRouterWorkflow):
        async def create_stream(self, query: str, *, session_telemetry: Any = None, **kwargs: Any) -> tuple[Any, Any]:
            if session_telemetry:
                received_telemetry.update(session_telemetry)
            return await super().create_stream(query, session_telemetry=session_telemetry, **kwargs)

    adapter = RouterWorkflowAgentAdapter(workflow_factory=lambda _url: _TelemetryCapture())

    stream, finalize = await adapter.create_stream("test query", session_record=record)
    async for _ in stream:
        pass
    await finalize()

    assert received_telemetry["session_id"] == record.session_id
    assert received_telemetry["turn_index"] == 2  # record.turn_index(1) + 1
    assert received_telemetry["memory_hits"] == 1
