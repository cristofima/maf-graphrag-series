"""Unit tests for router chatbot endpoint adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import ValidationError

from agents.session_store import InMemorySessionStore
from workflows.router_chatbot_server import (
    RouterChatbotConfig,
    RouterChatReply,
    RouterChatService,
    _connector_delivery_candidates,
    _emit_lock_span_diagnostics,
    _status_text_from_event,
    _typing_keepalive_loop,
    build_reply_activity,
    build_status_activity,
    build_typing_activity,
    create_router_chatbot_app,
    extract_activity_text,
)


class _StubRouterChatService(RouterChatService):
    """Test double that returns deterministic answers."""

    def __init__(self) -> None:
        super().__init__(
            mcp_url=None,
            request_timeout_seconds=30.0,
            session_store=InMemorySessionStore(
                ttl_seconds=300,
                max_count=100,
                cleanup_interval_seconds=60,
                max_history_groups=8,
            ),
        )
        self.calls: list[str] = []

    async def answer(
        self,
        text: str,
        *,
        session_record: Any = None,
        on_progress: Any = None,
        lock_wait_ms: float | None = None,
    ) -> RouterChatReply:
        _ = session_record
        _ = on_progress
        _ = lock_wait_ms
        self.calls.append(text)
        return RouterChatReply(
            answer=f"answer::{text}",
            routed_workflow="out_of_context",
            classifier_status="success",
            fallback_reason="out_of_context",
            total_elapsed_seconds=0.123,
        )


def _sample_activity(text: str) -> dict[str, Any]:
    return {
        "type": "message",
        "id": "abc123",
        "channelId": "msteams",
        "serviceUrl": "http://localhost",
        "conversation": {"id": "conv-1"},
        "from": {"id": "user-1", "name": "User"},
        "recipient": {"id": "bot-1", "name": "RouterBot"},
        "text": text,
    }


async def _request(app: Any, method: str, path: str, **kwargs: Any) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def test_extract_activity_text_from_text_field() -> None:
    activity = _sample_activity("  hello router  ")
    assert extract_activity_text(activity) == "hello router"


def test_extract_activity_text_from_value_object() -> None:
    activity: Mapping[str, Any] = {"type": "message", "value": {"text": "  hi from value  "}}
    assert extract_activity_text(activity) == "hi from value"


def test_build_reply_activity_swaps_sender_and_recipient() -> None:
    request_activity = _sample_activity("hello")

    reply = build_reply_activity(request_activity, RouterChatReply(answer="response text"))

    assert reply["type"] == "message"
    assert reply["text"] == "response text"
    assert reply["from"]["id"] == "bot-1"
    assert reply["recipient"]["id"] == "user-1"
    assert reply["conversation"]["id"] == "conv-1"
    assert reply["replyToId"] == "abc123"


def test_build_typing_activity_swaps_sender_and_recipient() -> None:
    request_activity = _sample_activity("hello")

    typing = build_typing_activity(request_activity)

    assert typing["type"] == "typing"
    assert typing["from"]["id"] == "bot-1"
    assert typing["recipient"]["id"] == "user-1"
    assert typing["conversation"]["id"] == "conv-1"


def test_build_status_activity_swaps_sender_and_recipient() -> None:
    request_activity = _sample_activity("hello")

    status = build_status_activity(request_activity, "Searching the knowledge base...")

    assert status["type"] == "message"
    assert status["text"] == "Searching the knowledge base..."
    assert status["from"]["id"] == "bot-1"
    assert status["recipient"]["id"] == "user-1"
    assert status["conversation"]["id"] == "conv-1"
    assert status["channelData"]["router"]["status"] == "processing"


def test_status_text_from_event_tracks_routed_workflow_context() -> None:
    route_event = SimpleNamespace(
        type="progress",
        data={"stage": "router_delegation", "routed_workflow": "concurrent"},
    )

    status, routed = _status_text_from_event(route_event, routed_workflow=None)

    assert status == "Routing your question..."
    assert routed == "concurrent"


def test_status_text_from_event_uses_workflow_specific_executor_messages() -> None:
    executor_event = SimpleNamespace(
        type="executor_invoked",
        executor_id="ThemesSearcher",
        data={},
    )

    status, routed = _status_text_from_event(executor_event, routed_workflow="concurrent")

    assert status == "Retrieving themes and cross-document patterns..."
    assert routed == "concurrent"


async def test_messages_endpoint_routes_to_router_service() -> None:
    app = create_router_chatbot_app(RouterChatbotConfig())
    stub = _StubRouterChatService()
    app.state.router_chat_service = stub

    response = await _request(
        app,
        "POST",
        "/api/messages",
        json=_sample_activity("Who leads Project Alpha?"),
        headers={"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "message"
    assert payload["text"] == "answer::Who leads Project Alpha?"
    assert payload["channelData"]["router"]["routed_workflow"] == "out_of_context"
    assert payload["channelData"]["router"]["classifier_status"] == "success"
    assert payload["channelData"]["router"]["fallback_reason"] == "out_of_context"
    assert response.headers["x-router-routed-workflow"] == "out_of_context"
    assert response.headers["x-router-classifier-status"] == "success"
    assert "traceparent" in response.headers
    assert stub.calls == ["Who leads Project Alpha?"]


async def test_messages_endpoint_health_check_returns_ready() -> None:
    app = create_router_chatbot_app(RouterChatbotConfig())

    response = await _request(app, "GET", "/api/messages")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["ready"] is True
    assert payload["endpoint"] == "/api/messages"


async def test_messages_endpoint_conversation_update_returns_welcome() -> None:
    app = create_router_chatbot_app(RouterChatbotConfig(welcome_message="welcome from test"))

    activity = {
        "type": "conversationUpdate",
        "id": "evt-1",
        "channelId": "msteams",
        "serviceUrl": "http://localhost",
        "conversation": {"id": "conv-1"},
        "from": {"id": "user-1", "name": "User"},
        "recipient": {"id": "bot-1", "name": "RouterBot"},
    }

    response = await _request(
        app,
        "POST",
        "/api/messages",
        json=activity,
        headers={"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "message"
    assert payload["text"] == "welcome from test"
    assert payload["conversation"]["id"] == "conv-1"
    assert "traceparent" in response.headers


async def test_installation_update_uses_connector_delivery_for_welcome(monkeypatch: Any) -> None:
    app = create_router_chatbot_app(RouterChatbotConfig())
    delivery_mock = AsyncMock(return_value=True)
    monkeypatch.setattr("workflows.router_chatbot_server._dispatch_reply_to_connector", delivery_mock)

    activity = {
        "type": "installationUpdate",
        "id": "install-1",
        "channelId": "msteams",
        "serviceUrl": "http://localhost/_connector",
        "conversation": {"id": "conv-1"},
        "from": {"id": "user-1", "name": "User"},
        "recipient": {"id": "bot-1", "name": "RouterBot"},
    }

    response = await _request(
        app,
        "POST",
        "/api/messages",
        json=activity,
        headers={"x-ms-agents-playground": "true"},
    )

    assert response.status_code == 200
    assert response.json()["delivery"] == "connector"
    assert delivery_mock.await_count == 1


async def test_duplicate_welcome_is_suppressed_per_conversation(monkeypatch: Any) -> None:
    app = create_router_chatbot_app(RouterChatbotConfig())
    delivery_mock = AsyncMock(return_value=True)
    monkeypatch.setattr("workflows.router_chatbot_server._dispatch_reply_to_connector", delivery_mock)

    activity = {
        "type": "conversationUpdate",
        "id": "evt-1",
        "channelId": "msteams",
        "serviceUrl": "http://localhost/_connector",
        "conversation": {"id": "conv-1"},
        "from": {"id": "user-1", "name": "User"},
        "recipient": {"id": "bot-1", "name": "RouterBot"},
    }

    first = await _request(
        app,
        "POST",
        "/api/messages",
        json=activity,
        headers={"x-ms-agents-playground": "true"},
    )
    second = await _request(
        app,
        "POST",
        "/api/messages",
        json=activity,
        headers={"x-ms-agents-playground": "true"},
    )

    assert first.status_code == 200
    assert first.json()["delivery"] == "connector"
    assert second.status_code == 200
    assert second.json()["status"] == "ignored"
    assert second.json()["reason"] == "welcome_already_sent"
    assert delivery_mock.await_count == 1


def test_connector_delivery_candidates_build_reply_and_send_paths() -> None:
    activity = _sample_activity("hello")
    activity["serviceUrl"] = "http://localhost/_connector"

    candidates = _connector_delivery_candidates(activity)

    assert candidates == [
        "http://localhost/_connector/v3/conversations/conv-1/activities/abc123",
        "http://localhost/_connector/v3/conversations/conv-1/activities",
    ]


async def test_playground_request_uses_connector_delivery_when_available(monkeypatch: Any) -> None:
    app = create_router_chatbot_app(RouterChatbotConfig())
    stub = _StubRouterChatService()
    app.state.router_chat_service = stub

    delivery_mock = AsyncMock(return_value=True)
    monkeypatch.setattr("workflows.router_chatbot_server._dispatch_reply_to_connector", delivery_mock)

    response = await _request(
        app,
        "POST",
        "/api/messages",
        json=_sample_activity("Who leads Project Alpha?"),
        headers={"x-ms-agents-playground": "true"},
    )

    assert response.status_code == 200
    assert response.json()["delivery"] == "connector"
    assert delivery_mock.await_count == 2


@pytest.mark.asyncio
async def test_typing_keepalive_sends_until_stop_event(monkeypatch: Any) -> None:
    dispatch_mock = AsyncMock(return_value=True)
    monkeypatch.setattr("workflows.router_chatbot_server._dispatch_reply_to_connector", dispatch_mock)

    stop_event = asyncio.Event()
    activity = _sample_activity("hello")

    task = asyncio.create_task(
        _typing_keepalive_loop(
            incoming_activity=activity,
            incoming_headers={"x-ms-agents-playground": "true"},
            stop_event=stop_event,
            fast_interval_seconds=0.01,
            slow_interval_seconds=0.01,
            slow_after_seconds=1.0,
        )
    )

    await asyncio.sleep(0.03)
    stop_event.set()
    await task

    assert dispatch_mock.await_count >= 1


async def test_messages_endpoint_rejects_empty_text() -> None:
    app = create_router_chatbot_app(RouterChatbotConfig())

    response = await _request(app, "POST", "/api/messages", json=_sample_activity("   "))

    assert response.status_code == 400
    assert "missing non-empty text" in response.json()["error"]


def test_emit_lock_span_diagnostics_adds_attributes_and_contention_event(monkeypatch: Any) -> None:
    class _FakeSpanContext:
        @property
        def is_valid(self) -> bool:
            return True

    class _FakeSpan:
        def __init__(self) -> None:
            self.attributes: dict[str, object] = {}
            self.events: list[tuple[str, dict[str, object]]] = []

        def get_span_context(self) -> _FakeSpanContext:
            return _FakeSpanContext()

        def set_attribute(self, key: str, value: object) -> None:
            self.attributes[key] = value

        def add_event(self, name: str, attributes: dict[str, object]) -> None:
            self.events.append((name, attributes))

    fake_span = _FakeSpan()
    monkeypatch.setattr("workflows.router_chatbot_server.trace.get_current_span", lambda: fake_span)

    _emit_lock_span_diagnostics(lock_wait_ms=140.0, lock_hold_ms=33.0)

    assert fake_span.attributes["router.lock_wait_ms"] == 140.0
    assert fake_span.attributes["router.lock_hold_ms"] == 33.0
    assert any(name == "router.session_lock_contention" for name, _attrs in fake_span.events)


class _FailingRouterChatService(RouterChatService):
    """Test double whose answer() holds the session lock briefly, then raises."""

    def __init__(self) -> None:
        super().__init__(
            mcp_url=None,
            request_timeout_seconds=30.0,
            session_store=InMemorySessionStore(
                ttl_seconds=300,
                max_count=100,
                cleanup_interval_seconds=60,
                max_history_groups=8,
            ),
        )

    async def answer(
        self,
        text: str,
        *,
        session_record: Any = None,
        on_progress: Any = None,
        lock_wait_ms: float | None = None,
    ) -> RouterChatReply:
        _ = session_record
        _ = on_progress
        _ = lock_wait_ms
        await asyncio.sleep(0.02)
        raise RuntimeError("simulated downstream failure")


async def test_lock_hold_ms_reported_even_when_answer_raises() -> None:
    app = create_router_chatbot_app(RouterChatbotConfig())
    app.state.router_chat_service = _FailingRouterChatService()

    response = await _request(app, "POST", "/api/messages", json=_sample_activity("hello"))

    assert response.status_code == 200
    session_metadata = response.json()["channelData"]["session"]
    assert session_metadata["lock_hold_ms"] > 0


def test_router_chatbot_config_session_ttl_upper_bound_rejected() -> None:
    with pytest.raises(ValidationError):
        RouterChatbotConfig(session_ttl_seconds=999_999_999)


def test_router_chatbot_config_session_bounds_match_session_config() -> None:
    from agents.config import SessionConfig

    router_fields = RouterChatbotConfig.model_fields
    session_fields = SessionConfig.model_fields

    for router_field, session_field in (
        ("session_ttl_seconds", "ttl_seconds"),
        ("session_max_count", "max_count"),
        ("session_cleanup_interval_seconds", "cleanup_interval_seconds"),
        ("session_max_history_groups", "max_history_groups"),
    ):
        router_constraints = router_fields[router_field].metadata
        session_constraints = session_fields[session_field].metadata
        assert router_constraints == session_constraints
