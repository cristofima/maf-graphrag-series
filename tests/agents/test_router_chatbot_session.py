"""Session-aware router chatbot integration tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from agents.session_store import InMemorySessionStore, SessionKey
from workflows.base import WorkflowResult, WorkflowStep, WorkflowType
from workflows.router_agent import RouterWorkflowAgentAdapter
from workflows.router_chatbot_server import (
    RouterChatbotConfig,
    RouterChatReply,
    RouterChatService,
    create_router_chatbot_app,
)


class _FakeRouterWorkflow:
    def __init__(self, captured_queries: list[str], answers: list[str]) -> None:
        self._captured_queries = captured_queries
        self._answers = answers

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
    ) -> tuple[Any, Any]:
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
