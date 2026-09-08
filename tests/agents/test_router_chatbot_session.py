"""Session-aware router chatbot integration tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from agent_framework import InMemoryCheckpointStorage, WorkflowCheckpoint

from maf_graphrag.agents.session_store import ActiveWorkflowRun, InMemorySessionStore, SessionKey
from maf_graphrag.workflows.base import WorkflowResult, WorkflowStep, WorkflowType
from maf_graphrag.workflows.router_agent import RouterWorkflowAgentAdapter
from maf_graphrag.workflows.router_chatbot_server import (
    RouterChatbotConfig,
    RouterChatReply,
    RouterChatService,
    create_router_chatbot_app,
)


class _FakeRouterWorkflow:
    def __init__(self, captured_queries: list[str], answers: list[str]) -> None:
        self._captured_queries = captured_queries
        self._answers = answers
        self.last_stream_kwargs: dict[str, Any] = {}

    async def __aenter__(self) -> _FakeRouterWorkflow:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        return None

    def prepare_run(self, query: object) -> str:
        text = str(query)
        self._captured_queries.append(text)
        return text

    async def create_stream(
        self,
        normalized_query: str,
        *,
        include_status_events: bool = True,
        session_telemetry: dict[str, object] | None = None,
        **kwargs: Any,
    ) -> tuple[Any, Any]:
        self.last_stream_kwargs = kwargs

        async def _stream() -> Any:
            if include_status_events:
                yield SimpleNamespace(
                    type="progress",
                    data={
                        "stage": "router_delegation",
                        "routed_workflow": "sequential",
                        "session_id": session_telemetry.get("session_id") if session_telemetry else None,
                    },
                )

        async def _finalize() -> WorkflowResult:
            answer = self._answers.pop(0)
            step = WorkflowStep(
                agent_name="WorkflowRouter",
                input_summary="Classify query",
                output="Workflow: sequential",
                elapsed_seconds=0.01,
                metadata={
                    "routed_workflow": "sequential",
                    "classified_workflow": "sequential",
                    "classifier_status": "success",
                    "classifier_attempts": 1,
                    "fallback_reason": None,
                },
            )
            return WorkflowResult(
                answer=answer,
                workflow_type=WorkflowType.ROUTER,
                steps=[step],
                total_elapsed_seconds=0.01,
                query=normalized_query,
            )

        return _stream(), _finalize


class _DelayedStubService:
    def __init__(self) -> None:
        self.inflight = 0
        self.max_inflight = 0

    async def answer(
        self,
        text: str,
        *,
        session_record: Any = None,
        on_progress: Any = None,
        lock_wait_ms: float | None = None,
    ) -> RouterChatReply:
        self.inflight += 1
        self.max_inflight = max(self.max_inflight, self.inflight)
        try:
            await asyncio.sleep(0.03)
            turn_index = session_record.turn_index + 1 if session_record is not None else 1
            return RouterChatReply(
                answer=f"ok::{text}",
                routed_workflow="sequential",
                classifier_status="success",
                session_id=session_record.session_id if session_record is not None else None,
                turn_index=turn_index,
                memory_hits=len(session_record.history_groups) if session_record is not None else 0,
                compaction_events=0,
            )
        finally:
            self.inflight -= 1


@pytest.mark.asyncio
async def test_router_chat_service_preserves_multi_turn_context() -> None:
    captured_queries: list[str] = []
    answers = ["First answer", "Second answer", "Third answer"]

    def _workflow_factory(_mcp_url: str | None) -> _FakeRouterWorkflow:
        return _FakeRouterWorkflow(captured_queries, answers)

    adapter = RouterWorkflowAgentAdapter(workflow_factory=_workflow_factory)
    session_store = InMemorySessionStore(
        ttl_seconds=300,
        max_count=100,
        cleanup_interval_seconds=60,
        max_history_groups=2,
    )
    service = RouterChatService(
        mcp_url=None,
        request_timeout_seconds=30.0,
        session_store=session_store,
        adapter=adapter,
    )

    key = SessionKey.create(channel_id="msteams", conversation_id="conv-1", user_id="user-1")
    record, _ = await session_store.get_or_create(key.session_id)

    reply_one = await service.answer("My name is Ana.", session_record=record)
    reply_two = await service.answer("What is my name?", session_record=record)
    reply_three = await service.answer("Repeat my name again.", session_record=record)

    assert captured_queries[0] == "My name is Ana."
    assert "My name is Ana." in captured_queries[1]
    assert "Assistant: First answer" in captured_queries[1]
    assert "What is my name?" in captured_queries[2]
    assert "Assistant: Second answer" in captured_queries[2]

    assert reply_one.turn_index == 1
    assert reply_one.memory_hits == 0
    assert reply_two.turn_index == 2
    assert reply_two.memory_hits == 1
    assert reply_three.turn_index == 3
    assert reply_three.memory_hits == 2
    assert reply_three.compaction_events == 1


@pytest.mark.asyncio
async def test_same_session_near_simultaneous_requests_are_serialized() -> None:
    app = create_router_chatbot_app(RouterChatbotConfig())
    delayed_service = _DelayedStubService()
    app.state.router_chat_service = delayed_service

    payload = {
        "type": "message",
        "id": "m1",
        "channelId": "msteams",
        "serviceUrl": "http://localhost",
        "conversation": {"id": "conv-serial"},
        "from": {"id": "user-serial", "name": "User"},
        "recipient": {"id": "bot-1", "name": "RouterBot"},
        "text": "hello",
    }

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = client.post("/api/messages", json=payload)
        second = client.post("/api/messages", json={**payload, "id": "m2", "text": "hello again"})
        response_one, response_two = await asyncio.gather(first, second)

    assert response_one.status_code == 200
    assert response_two.status_code == 200
    assert delayed_service.max_inflight == 1


@pytest.mark.asyncio
async def test_valid_checkpoint_passed_to_adapter_on_resume() -> None:
    """When active_workflow_run has a valid checkpoint_id, adapter receives checkpoint_id + storage."""
    checkpoint_storage = InMemoryCheckpointStorage()
    checkpoint = WorkflowCheckpoint(workflow_name="sequential", graph_signature_hash="hash-1")
    checkpoint_id = await checkpoint_storage.save(checkpoint)

    captured_queries: list[str] = []
    captured_fake: list[_FakeRouterWorkflow] = []
    answers = ["Resume answer"]

    def _workflow_factory(_mcp_url: str | None) -> _FakeRouterWorkflow:
        fake = _FakeRouterWorkflow(captured_queries, answers)
        captured_fake.append(fake)
        return fake

    adapter = RouterWorkflowAgentAdapter(workflow_factory=_workflow_factory)
    session_store = InMemorySessionStore(
        ttl_seconds=300,
        max_count=100,
        cleanup_interval_seconds=60,
        max_history_groups=4,
    )
    service = RouterChatService(
        mcp_url=None,
        request_timeout_seconds=30.0,
        session_store=session_store,
        adapter=adapter,
        checkpoint_storage=checkpoint_storage,
    )

    key = SessionKey.create(channel_id="msteams", conversation_id="conv-resume", user_id="user-r")
    record, _ = await session_store.get_or_create(key.session_id)
    record.active_workflow_run = ActiveWorkflowRun(
        workflow_run_id="run-001",
        checkpoint_id=checkpoint_id,
        workflow_type="sequential",
    )

    await service.answer("Resume from where we left off.", session_record=record)

    assert len(captured_fake) == 1
    kwargs = captured_fake[0].last_stream_kwargs
    assert kwargs.get("checkpoint_id") == checkpoint_id
    assert kwargs.get("checkpoint_storage") is checkpoint_storage
    # Cleared after successful completion
    assert record.active_workflow_run is None


@pytest.mark.asyncio
async def test_stale_checkpoint_rejected_proceeds_without_checkpoint_id() -> None:
    """When active_workflow_run has a stale checkpoint_id, it is discarded and run proceeds fresh."""
    checkpoint_storage = InMemoryCheckpointStorage()

    captured_queries: list[str] = []
    captured_fake: list[_FakeRouterWorkflow] = []
    answers = ["Fresh answer"]

    def _workflow_factory(_mcp_url: str | None) -> _FakeRouterWorkflow:
        fake = _FakeRouterWorkflow(captured_queries, answers)
        captured_fake.append(fake)
        return fake

    adapter = RouterWorkflowAgentAdapter(workflow_factory=_workflow_factory)
    session_store = InMemorySessionStore(
        ttl_seconds=300,
        max_count=100,
        cleanup_interval_seconds=60,
        max_history_groups=4,
    )
    service = RouterChatService(
        mcp_url=None,
        request_timeout_seconds=30.0,
        session_store=session_store,
        adapter=adapter,
        checkpoint_storage=checkpoint_storage,
    )

    key = SessionKey.create(channel_id="msteams", conversation_id="conv-stale", user_id="user-s")
    record, _ = await session_store.get_or_create(key.session_id)
    session_store.append_turn(record, user_text="previous turn", assistant_text="previous reply")
    record.active_workflow_run = ActiveWorkflowRun(
        workflow_run_id="run-stale",
        checkpoint_id="nonexistent-checkpoint-id",
        workflow_type="sequential",
    )

    await service.answer("New question.", session_record=record)

    assert len(captured_fake) == 1
    kwargs = captured_fake[0].last_stream_kwargs
    # No checkpoint_id passed — stale checkpoint discarded
    assert "checkpoint_id" not in kwargs
    # Checkpoint_storage is still threaded through for future runs
    assert kwargs.get("checkpoint_storage") is checkpoint_storage
    # Session history preserved; active_workflow_run cleared
    assert record.active_workflow_run is None
    assert len(record.history_groups) == 2  # previous + new turn


@pytest.mark.asyncio
async def test_incompatible_checkpoint_rejected_proceeds_without_checkpoint_id() -> None:
    """A checkpoint whose workflow_name doesn't match workflow_type is rejected as incompatible."""
    checkpoint_storage = InMemoryCheckpointStorage()
    # Saved as "concurrent" but the session expects a "sequential" resume.
    checkpoint = WorkflowCheckpoint(workflow_name="concurrent", graph_signature_hash="hash-2")
    checkpoint_id = await checkpoint_storage.save(checkpoint)

    captured_queries: list[str] = []
    captured_fake: list[_FakeRouterWorkflow] = []
    answers = ["Fresh answer"]

    def _workflow_factory(_mcp_url: str | None) -> _FakeRouterWorkflow:
        fake = _FakeRouterWorkflow(captured_queries, answers)
        captured_fake.append(fake)
        return fake

    adapter = RouterWorkflowAgentAdapter(workflow_factory=_workflow_factory)
    session_store = InMemorySessionStore(
        ttl_seconds=300,
        max_count=100,
        cleanup_interval_seconds=60,
        max_history_groups=4,
    )
    service = RouterChatService(
        mcp_url=None,
        request_timeout_seconds=30.0,
        session_store=session_store,
        adapter=adapter,
        checkpoint_storage=checkpoint_storage,
    )

    key = SessionKey.create(channel_id="msteams", conversation_id="conv-incompat", user_id="user-i")
    record, _ = await session_store.get_or_create(key.session_id)
    session_store.append_turn(record, user_text="prior question", assistant_text="prior answer")
    record.active_workflow_run = ActiveWorkflowRun(
        workflow_run_id="run-incompat",
        checkpoint_id=checkpoint_id,
        workflow_type="sequential",  # mismatches checkpoint's workflow_name="concurrent"
    )

    await service.answer("Next question.", session_record=record)

    assert len(captured_fake) == 1
    kwargs = captured_fake[0].last_stream_kwargs
    # Incompatible checkpoint must not be passed through
    assert "checkpoint_id" not in kwargs
    assert kwargs.get("checkpoint_storage") is checkpoint_storage
    # History preserved and active_workflow_run cleared
    assert record.active_workflow_run is None
    assert len(record.history_groups) == 2


@pytest.mark.asyncio
async def test_save_checkpoint_after_interruption_captures_sequential_checkpoint() -> None:
    """After a timeout the latest sequential checkpoint is saved to active_workflow_run."""
    checkpoint_storage = InMemoryCheckpointStorage()
    checkpoint = WorkflowCheckpoint(workflow_name="sequential", graph_signature_hash="hash-t1")
    checkpoint_id = await checkpoint_storage.save(checkpoint)

    session_store = InMemorySessionStore(
        ttl_seconds=300, max_count=100, cleanup_interval_seconds=60, max_history_groups=4
    )
    service = RouterChatService(
        mcp_url=None,
        request_timeout_seconds=30.0,
        session_store=session_store,
        checkpoint_storage=checkpoint_storage,
    )

    key = SessionKey.create(channel_id="msteams", conversation_id="conv-t", user_id="user-t")
    record, _ = await session_store.get_or_create(key.session_id)
    session_store.append_turn(record, user_text="q", assistant_text="a")

    await service._save_checkpoint_after_interruption(record)

    assert record.active_workflow_run is not None
    assert record.active_workflow_run.checkpoint_id == checkpoint_id
    assert record.active_workflow_run.workflow_type == "sequential"
    # History is unaffected by checkpoint capture
    assert len(record.history_groups) == 1


@pytest.mark.asyncio
async def test_save_checkpoint_after_interruption_noop_when_storage_empty() -> None:
    """If no checkpoint exists in storage the session record is left unchanged."""
    checkpoint_storage = InMemoryCheckpointStorage()

    session_store = InMemorySessionStore(
        ttl_seconds=300, max_count=100, cleanup_interval_seconds=60, max_history_groups=4
    )
    service = RouterChatService(
        mcp_url=None,
        request_timeout_seconds=30.0,
        session_store=session_store,
        checkpoint_storage=checkpoint_storage,
    )

    key = SessionKey.create(channel_id="msteams", conversation_id="conv-empty", user_id="user-e")
    record, _ = await session_store.get_or_create(key.session_id)

    await service._save_checkpoint_after_interruption(record)

    assert record.active_workflow_run is None
