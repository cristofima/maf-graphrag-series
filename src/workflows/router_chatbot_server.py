"""Teams/Agents Playground-compatible chatbot endpoint backed by RouterWorkflow.

This module exposes a minimal Bot Framework-style `/api/messages` endpoint for
local testing with Microsoft 365 Agents Playground. The router workflow remains
the single production-facing orchestration entry point.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx
from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.trace import SpanKind
from pydantic import BaseModel, Field, ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from workflows.base import create_router_workflow

logger = logging.getLogger(__name__)

_LOCAL_ERROR_MESSAGE = (
    "I ran into an error while processing your request. "
    "Please try again with a knowledge-base question."
)
_WELCOME_MESSAGE = "Welcome. I can route your question across GraphRAG workflows. Ask me anything about the knowledge base."
_TRACER = trace.get_tracer(__name__)
_PLAYGROUND_HEADER = "x-ms-agents-playground"
_CONNECTOR_DELIVERY_TIMEOUT_SECONDS = 15.0
_DEFAULT_PROGRESS_STATUS = "Processing your request..."

_EXECUTOR_PROGRESS_MESSAGES: dict[str, str] = {
    "WorkflowRouter": "Routing your question...",
    "QueryAnalyzer": "Analyzing your question...",
    "KnowledgeSearcher": "Searching the knowledge base...",
    "QueryBroadcast": "Preparing parallel search...",
    "EntitySearcher": "Searching entities and facts...",
    "ThemesSearcher": "Searching themes and context...",
    "AnswerSynthesizer": "Summarizing findings...",
    "Router": "Selecting specialist path...",
    "EntityExpert": "Expanding entity details...",
    "ThemesExpert": "Expanding thematic context...",
    "HandoffComposer": "Composing final answer...",
    "OutOfContextResponder": "Preparing guidance response...",
}

_WORKFLOW_EXECUTOR_PROGRESS_MESSAGES: dict[str, dict[str, str]] = {
    "sequential": {
        "QueryAnalyzer": "Analyzing question and planning retrieval...",
        "KnowledgeSearcher": "Searching focused knowledge context...",
        "ReportWriter": "Drafting final response...",
    },
    "concurrent": {
        "QueryBroadcast": "Preparing parallel retrieval branches...",
        "EntitySearcher": "Retrieving entities and factual links...",
        "ThemesSearcher": "Retrieving themes and cross-document patterns...",
        "AnswerSynthesizer": "Synthesizing parallel findings...",
    },
    "handoff": {
        "Router": "Selecting specialist collaboration path...",
        "EntityExpert": "Expanding entity-level details...",
        "ThemesExpert": "Expanding thematic narrative...",
        "HandoffComposer": "Composing specialist handoff answer...",
    },
    "out_of_context": {
        "OutOfContextResponder": "Preparing guidance response...",
    },
}

_STAGE_PROGRESS_MESSAGES: dict[str, str] = {
    "router_delegation": "Routing your question...",
    "out_of_context_response": "Preparing guidance response...",
    "workflow_runner_started": "Starting workflow execution...",
    "workflow_runner_completed": "Finalizing response...",
}


class RouterChatbotConfig(BaseModel):
    """Configuration for the local router chatbot endpoint."""

    host: str = "::"
    port: int = 3978
    endpoint_path: str = "/api/messages"
    mcp_url: str | None = None
    request_timeout_seconds: float = Field(default=180.0, gt=1.0)
    welcome_message: str = _WELCOME_MESSAGE
    typing_keepalive_fast_seconds: float = Field(default=1.2, gt=0.2)
    typing_keepalive_slow_seconds: float = Field(default=3.0, gt=0.2)
    typing_keepalive_slow_after_seconds: float = Field(default=20.0, gt=1.0)
    progress_status_after_seconds: float = Field(default=8.0, ge=0.0)
    progress_status_min_interval_seconds: float = Field(default=6.0, gt=0.2)

    @classmethod
    def from_env(cls) -> RouterChatbotConfig:
        """Build validated configuration from environment variables."""

        data = {
            "host": os.getenv("ROUTER_CHATBOT_HOST", "::"),
            "port": os.getenv("ROUTER_CHATBOT_PORT", "3978"),
            "endpoint_path": os.getenv("ROUTER_CHATBOT_ENDPOINT", "/api/messages"),
            "mcp_url": os.getenv("MCP_SERVER_URL"),
            "request_timeout_seconds": os.getenv("ROUTER_CHATBOT_TIMEOUT_SECONDS", "180"),
            "welcome_message": os.getenv("ROUTER_CHATBOT_WELCOME_MESSAGE", _WELCOME_MESSAGE),
            "typing_keepalive_fast_seconds": os.getenv("ROUTER_CHATBOT_TYPING_KEEPALIVE_SECONDS", "1.2"),
            "typing_keepalive_slow_seconds": os.getenv("ROUTER_CHATBOT_TYPING_KEEPALIVE_SLOW_SECONDS", "3.0"),
            "typing_keepalive_slow_after_seconds": os.getenv("ROUTER_CHATBOT_TYPING_KEEPALIVE_SLOW_AFTER_SECONDS", "20"),
            "progress_status_after_seconds": os.getenv("ROUTER_CHATBOT_PROGRESS_STATUS_AFTER_SECONDS", "8"),
            "progress_status_min_interval_seconds": os.getenv(
                "ROUTER_CHATBOT_PROGRESS_STATUS_MIN_INTERVAL_SECONDS",
                "6",
            ),
        }
        try:
            return cls.model_validate(data)
        except ValidationError as exc:  # pragma: no cover - defensive guard
            raise ValueError(str(exc)) from exc


class RouterChatService:
    """Async facade that executes RouterWorkflow for a single user message."""

    def __init__(self, *, mcp_url: str | None, request_timeout_seconds: float) -> None:
        self._mcp_url = mcp_url
        self._request_timeout_seconds = request_timeout_seconds

    async def answer(
        self,
        text: str,
        *,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> RouterChatReply:
        """Return the router workflow answer for a user text input."""

        async with asyncio.timeout(self._request_timeout_seconds):
            async with create_router_workflow(self._mcp_url) as workflow:
                normalized_query = workflow.prepare_run(text)
                stream, finalize = await workflow.create_stream(
                    normalized_query,
                    include_status_events=True,
                )

                if on_progress is not None:
                    await on_progress("Routing your question...")

                stream_routed_workflow: str | None = None
                async for event in stream:
                    if on_progress is None:
                        continue
                    status_text, stream_routed_workflow = _status_text_from_event(
                        event,
                        routed_workflow=stream_routed_workflow,
                    )
                    if status_text is None:
                        continue
                    await on_progress(status_text)

                result = await finalize()

        routed_workflow: str | None = None
        classifier_status: str | None = None
        fallback_reason: str | None = None
        if result.steps:
            metadata = result.steps[0].metadata
            routed = metadata.get("routed_workflow")
            status = metadata.get("classifier_status")
            fallback = metadata.get("fallback_reason")
            routed_workflow = routed if isinstance(routed, str) else None
            classifier_status = status if isinstance(status, str) else None
            fallback_reason = fallback if isinstance(fallback, str) else None

        return RouterChatReply(
            answer=result.answer,
            routed_workflow=routed_workflow,
            classifier_status=classifier_status,
            fallback_reason=fallback_reason,
            total_elapsed_seconds=result.total_elapsed_seconds,
        )


@dataclass(slots=True)
class RouterChatReply:
    """Structured chatbot reply plus router metadata for diagnostics."""

    answer: str
    routed_workflow: str | None = None
    classifier_status: str | None = None
    fallback_reason: str | None = None
    total_elapsed_seconds: float | None = None


def _log_json(level: int, event: str, **fields: Any) -> None:
    """Emit one-line JSON logs that are portable across log providers."""

    payload: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "event": event,
        "logger": __name__,
    }

    span_context = trace.get_current_span().get_span_context()
    if span_context.is_valid:
        payload["trace_id"] = f"{span_context.trace_id:032x}"
        payload["span_id"] = f"{span_context.span_id:016x}"

    for key, value in fields.items():
        if value is not None:
            payload[key] = value
    logger.log(level, json.dumps(payload, ensure_ascii=True, separators=(",", ":")))


def _inject_trace_headers(response_headers: dict[str, str]) -> None:
    """Inject active OpenTelemetry context into response headers."""

    carrier: dict[str, str] = {}
    inject(carrier)
    traceparent = carrier.get("traceparent")
    tracestate = carrier.get("tracestate")
    if traceparent:
        response_headers["traceparent"] = traceparent
    if tracestate:
        response_headers["tracestate"] = tracestate


def _normalize_routed_workflow(value: Any) -> str | None:
    """Normalize routed workflow labels from stream payloads."""

    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"sequential", "concurrent", "handoff", "out_of_context"}:
        return normalized
    return None


def _status_text_from_event(
    event: Any,
    *,
    routed_workflow: str | None,
) -> tuple[str | None, str | None]:
    """Map workflow stream events to human-readable progress text and route context."""

    event_type = getattr(event, "type", None)
    if not isinstance(event_type, str):
        return None, routed_workflow

    data = getattr(event, "data", None)
    updated_workflow = routed_workflow
    if event_type == "progress" and isinstance(data, Mapping):
        stage = data.get("stage")
        routed = _normalize_routed_workflow(data.get("routed_workflow"))
        if routed is not None:
            updated_workflow = routed

        if isinstance(stage, str):
            stage_message = _STAGE_PROGRESS_MESSAGES.get(stage)
            if stage_message is not None:
                return stage_message, updated_workflow

        if updated_workflow == "sequential":
            return "Running sequential reasoning...", updated_workflow
        if updated_workflow == "concurrent":
            return "Running parallel retrieval...", updated_workflow
        if updated_workflow == "handoff":
            return "Coordinating specialist handoff...", updated_workflow
        if updated_workflow == "out_of_context":
            return "Preparing guidance response...", updated_workflow

    if event_type in {"executor_invoked", "executor_completed"}:
        executor_id = getattr(event, "executor_id", None)
        if isinstance(executor_id, str):
            if updated_workflow is not None:
                workflow_messages = _WORKFLOW_EXECUTOR_PROGRESS_MESSAGES.get(updated_workflow, {})
                workflow_message = workflow_messages.get(executor_id)
                if workflow_message is not None:
                    return workflow_message, updated_workflow

            generic_message = _EXECUTOR_PROGRESS_MESSAGES.get(executor_id)
            if generic_message is not None:
                return generic_message, updated_workflow

    return None, updated_workflow


def _is_playground_request(headers: Mapping[str, str]) -> bool:
    """Return whether the request originates from Agents Playground."""

    return headers.get(_PLAYGROUND_HEADER, "").strip().lower() == "true"


def _conversation_id(activity: Mapping[str, Any]) -> str:
    """Extract conversation ID from an activity payload."""

    conversation = activity.get("conversation")
    if isinstance(conversation, Mapping):
        candidate_id = conversation.get("id")
        if isinstance(candidate_id, str):
            return candidate_id
    return ""


def _connector_delivery_candidates(activity: Mapping[str, Any]) -> list[str]:
    """Build candidate connector URLs for reply delivery via serviceUrl."""

    service_url = activity.get("serviceUrl")
    if not isinstance(service_url, str) or not service_url.strip():
        return []

    conversation = activity.get("conversation")
    conversation_id = ""
    if isinstance(conversation, Mapping):
        candidate = conversation.get("id")
        if isinstance(candidate, str):
            conversation_id = candidate

    if not conversation_id:
        return []

    base = service_url.rstrip("/")
    encoded_conversation = quote(conversation_id, safe="")
    paths = [f"{base}/v3/conversations/{encoded_conversation}/activities"]

    activity_id = activity.get("id")
    if isinstance(activity_id, str) and activity_id:
        encoded_activity = quote(activity_id, safe="")
        paths.insert(0, f"{base}/v3/conversations/{encoded_conversation}/activities/{encoded_activity}")

    return paths


async def _dispatch_reply_to_connector(
    *,
    incoming_activity: Mapping[str, Any],
    reply_activity: Mapping[str, Any],
    incoming_headers: Mapping[str, str],
) -> bool:
    """Send reply activity to the connector serviceUrl used by Agents Playground."""

    candidates = _connector_delivery_candidates(incoming_activity)
    if not candidates:
        return False

    headers = {"Content-Type": "application/json"}
    if _is_playground_request(incoming_headers):
        headers[_PLAYGROUND_HEADER] = "true"

    async with httpx.AsyncClient(timeout=_CONNECTOR_DELIVERY_TIMEOUT_SECONDS) as client:
        for url in candidates:
            response = await client.post(url, json=dict(reply_activity), headers=headers)
            if response.status_code < 400:
                _log_json(
                    logging.INFO,
                    "router_chatbot.connector_delivery_success",
                    url=url,
                    status_code=response.status_code,
                )
                return True

            _log_json(
                logging.WARNING,
                "router_chatbot.connector_delivery_attempt_failed",
                url=url,
                status_code=response.status_code,
            )

    return False


async def _typing_keepalive_loop(
    *,
    incoming_activity: Mapping[str, Any],
    incoming_headers: Mapping[str, str],
    stop_event: asyncio.Event,
    fast_interval_seconds: float,
    slow_interval_seconds: float,
    slow_after_seconds: float,
) -> None:
    """Keep sending typing activities while the workflow is still processing."""

    started = time.perf_counter()
    while not stop_event.is_set():
        elapsed = time.perf_counter() - started
        interval_seconds = fast_interval_seconds if elapsed < slow_after_seconds else slow_interval_seconds

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            break
        except TimeoutError:
            pass

        try:
            delivered = await _dispatch_reply_to_connector(
                incoming_activity=incoming_activity,
                reply_activity=build_typing_activity(incoming_activity),
                incoming_headers=incoming_headers,
            )
            if delivered:
                _log_json(logging.INFO, "router_chatbot.typing_keepalive_sent")
        except Exception as exc:
            _log_json(
                logging.WARNING,
                "router_chatbot.typing_keepalive_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )


async def _dispatch_progress_status_message(
    *,
    incoming_activity: Mapping[str, Any],
    incoming_headers: Mapping[str, str],
    status_text: str,
) -> bool:
    """Dispatch a visible progress status message via connector."""

    activity = build_status_activity(incoming_activity, status_text)
    return await _dispatch_reply_to_connector(
        incoming_activity=incoming_activity,
        reply_activity=activity,
        incoming_headers=incoming_headers,
    )


def extract_activity_text(activity: Mapping[str, Any]) -> str | None:
    """Extract the user message text from a Bot Framework activity payload."""

    text = activity.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    value = activity.get("value")
    if isinstance(value, Mapping):
        value_text = value.get("text")
        if isinstance(value_text, str) and value_text.strip():
            return value_text.strip()

    return None


def build_reply_activity(request_activity: Mapping[str, Any], reply: RouterChatReply) -> dict[str, Any]:
    """Build a minimal reply activity compatible with local playground clients."""

    response: dict[str, Any] = {
        "type": "message",
        "text": reply.answer,
    }

    router_metadata: dict[str, Any] = {}
    if reply.routed_workflow is not None:
        router_metadata["routed_workflow"] = reply.routed_workflow
    if reply.classifier_status is not None:
        router_metadata["classifier_status"] = reply.classifier_status
    if reply.fallback_reason is not None:
        router_metadata["fallback_reason"] = reply.fallback_reason
    if reply.total_elapsed_seconds is not None:
        router_metadata["elapsed_seconds"] = round(reply.total_elapsed_seconds, 3)
    if router_metadata:
        response["channelData"] = {"router": router_metadata}

    for key in ("channelId", "serviceUrl", "conversation"):
        value = request_activity.get(key)
        if value is not None:
            response[key] = value

    sender = request_activity.get("from")
    recipient = request_activity.get("recipient")
    if isinstance(recipient, Mapping):
        response["from"] = dict(recipient)
    if isinstance(sender, Mapping):
        response["recipient"] = dict(sender)

    reply_to = request_activity.get("id")
    if isinstance(reply_to, str) and reply_to:
        response["replyToId"] = reply_to

    return response


def build_typing_activity(request_activity: Mapping[str, Any]) -> dict[str, Any]:
    """Build a typing activity compatible with Bot Framework channels."""

    response: dict[str, Any] = {
        "type": "typing",
    }

    for key in ("channelId", "serviceUrl", "conversation"):
        value = request_activity.get(key)
        if value is not None:
            response[key] = value

    sender = request_activity.get("from")
    recipient = request_activity.get("recipient")
    if isinstance(recipient, Mapping):
        response["from"] = dict(recipient)
    if isinstance(sender, Mapping):
        response["recipient"] = dict(sender)

    return response


def build_status_activity(request_activity: Mapping[str, Any], status_text: str) -> dict[str, Any]:
    """Build an informational message activity for long-running operations."""

    response: dict[str, Any] = {
        "type": "message",
        "text": status_text,
        "channelData": {"router": {"status": "processing"}},
    }

    for key in ("channelId", "serviceUrl", "conversation"):
        value = request_activity.get(key)
        if value is not None:
            response[key] = value

    sender = request_activity.get("from")
    recipient = request_activity.get("recipient")
    if isinstance(recipient, Mapping):
        response["from"] = dict(recipient)
    if isinstance(sender, Mapping):
        response["recipient"] = dict(sender)

    return response


async def _messages_handler(request: Request) -> JSONResponse:
    """Handle incoming activity messages from local Agents Playground."""

    service: RouterChatService = request.app.state.router_chat_service
    config: RouterChatbotConfig = request.app.state.router_chatbot_config
    welcomed_conversation_ids: set[str] = request.app.state.welcomed_conversation_ids
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON payload."}, status_code=400)

    if not isinstance(payload, dict):
        return JSONResponse({"error": "Activity payload must be a JSON object."}, status_code=400)

    incoming_headers = dict(request.headers.items())
    incoming_context = extract(incoming_headers)

    with _TRACER.start_as_current_span("router_chatbot.handle_activity", context=incoming_context, kind=SpanKind.SERVER):
        activity_type = payload.get("type")
        if activity_type in {"conversationUpdate", "installationUpdate"}:
            conversation_id = _conversation_id(payload)
            if conversation_id and conversation_id in welcomed_conversation_ids:
                _log_json(
                    logging.INFO,
                    "router_chatbot.welcome_skipped_duplicate",
                    activity_type=str(activity_type),
                    conversation_id=conversation_id,
                )
                return JSONResponse({"status": "ignored", "reason": "welcome_already_sent"})

            if conversation_id:
                welcomed_conversation_ids.add(conversation_id)

            _log_json(logging.INFO, "router_chatbot.welcome", activity_type=str(activity_type))
            welcome = RouterChatReply(answer=config.welcome_message, classifier_status="welcome")
            welcome_payload = build_reply_activity(payload, welcome)
            response_headers: dict[str, str] = {}
            _inject_trace_headers(response_headers)

            if _is_playground_request(incoming_headers):
                try:
                    delivered = await _dispatch_reply_to_connector(
                        incoming_activity=payload,
                        reply_activity=welcome_payload,
                        incoming_headers=incoming_headers,
                    )
                except Exception as exc:
                    _log_json(
                        logging.ERROR,
                        "router_chatbot.connector_welcome_delivery_failed",
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
                    delivered = False

                if delivered:
                    return JSONResponse({"status": "accepted", "delivery": "connector"}, headers=response_headers)

                _log_json(logging.WARNING, "router_chatbot.connector_welcome_fallback_to_response_body")

            return JSONResponse(welcome_payload, headers=response_headers)

        if activity_type != "message":
            _log_json(logging.INFO, "router_chatbot.unsupported_activity", activity_type=str(activity_type))
            info_answer = "This endpoint only supports message activities in local development."
            response_headers = {}
            _inject_trace_headers(response_headers)
            return JSONResponse(build_reply_activity(payload, RouterChatReply(answer=info_answer)), headers=response_headers)

        text = extract_activity_text(payload)
        if text is None:
            return JSONResponse({"error": "Message activity is missing non-empty text."}, status_code=400)

        conversation_id = _conversation_id(payload)

        message_id = payload.get("id")
        message_id_text = message_id if isinstance(message_id, str) else ""
        _log_json(
            logging.INFO,
            "router_chatbot.message_received",
            conversation_id=conversation_id,
            message_id=message_id_text,
            text=text,
        )

        typing_task: asyncio.Task[None] | None = None
        typing_stop_event: asyncio.Event | None = None
        status_message_sent = False
        last_progress_status = _DEFAULT_PROGRESS_STATUS
        last_status_sent_at = 0.0
        processing_started_at = time.perf_counter()

        async def _on_progress(status_text: str) -> None:
            nonlocal last_progress_status, last_status_sent_at, status_message_sent

            if not status_text.strip():
                return

            last_progress_status = status_text.strip()

            if not _is_playground_request(incoming_headers):
                return
            if config.progress_status_after_seconds <= 0:
                return

            now = time.perf_counter()
            elapsed = now - processing_started_at
            if elapsed < config.progress_status_after_seconds:
                return

            if status_message_sent and status_text == _DEFAULT_PROGRESS_STATUS:
                return

            if status_message_sent and (now - last_status_sent_at) < config.progress_status_min_interval_seconds:
                return

            delivered = await _dispatch_progress_status_message(
                incoming_activity=payload,
                incoming_headers=incoming_headers,
                status_text=last_progress_status,
            )
            if delivered:
                status_message_sent = True
                last_status_sent_at = now
                _log_json(logging.INFO, "router_chatbot.progress_status_sent", status_text=last_progress_status)

        if _is_playground_request(incoming_headers):
            typing_activity = build_typing_activity(payload)
            try:
                delivered_typing = await _dispatch_reply_to_connector(
                    incoming_activity=payload,
                    reply_activity=typing_activity,
                    incoming_headers=incoming_headers,
                )
                if delivered_typing:
                    _log_json(logging.INFO, "router_chatbot.typing_sent")
            except Exception as exc:
                _log_json(
                    logging.WARNING,
                    "router_chatbot.typing_delivery_failed",
                    error_type=type(exc).__name__,
                    error=str(exc),
                )

            typing_stop_event = asyncio.Event()
            typing_task = asyncio.create_task(
                _typing_keepalive_loop(
                    incoming_activity=payload,
                    incoming_headers=incoming_headers,
                    stop_event=typing_stop_event,
                    fast_interval_seconds=config.typing_keepalive_fast_seconds,
                    slow_interval_seconds=config.typing_keepalive_slow_seconds,
                    slow_after_seconds=config.typing_keepalive_slow_after_seconds,
                )
            )

        started = time.perf_counter()

        try:
            reply = await service.answer(text, on_progress=_on_progress)
        except Exception as exc:
            _log_json(
                logging.ERROR,
                "router_chatbot.processing_failed",
                conversation_id=conversation_id,
                message_id=message_id_text,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            reply = RouterChatReply(answer=_LOCAL_ERROR_MESSAGE, classifier_status="error")
        finally:
            if _is_playground_request(incoming_headers):
                elapsed = time.perf_counter() - processing_started_at
                if not status_message_sent and config.progress_status_after_seconds > 0:
                    if elapsed >= config.progress_status_after_seconds:
                        delivered_status = await _dispatch_progress_status_message(
                            incoming_activity=payload,
                            incoming_headers=incoming_headers,
                            status_text=last_progress_status,
                        )
                        if delivered_status:
                            _log_json(
                                logging.INFO,
                                "router_chatbot.progress_status_sent",
                                status_text=last_progress_status,
                                mode="fallback",
                            )
            if typing_stop_event is not None:
                typing_stop_event.set()
            if typing_task is not None:
                await typing_task

        elapsed_ms = (time.perf_counter() - started) * 1000
        _log_json(
            logging.INFO,
            "router_chatbot.message_processed",
            conversation_id=conversation_id,
            message_id=message_id_text,
            routed_workflow=reply.routed_workflow,
            classifier_status=reply.classifier_status,
            fallback_reason=reply.fallback_reason,
            elapsed_ms=round(elapsed_ms, 1),
        )

        response_payload = build_reply_activity(payload, reply)
        response_headers = {}
        if reply.routed_workflow:
            response_headers["x-router-routed-workflow"] = reply.routed_workflow
        if reply.classifier_status:
            response_headers["x-router-classifier-status"] = reply.classifier_status
        _inject_trace_headers(response_headers)

        if _is_playground_request(incoming_headers):
            try:
                delivered = await _dispatch_reply_to_connector(
                    incoming_activity=payload,
                    reply_activity=response_payload,
                    incoming_headers=incoming_headers,
                )
            except Exception as exc:
                _log_json(
                    logging.ERROR,
                    "router_chatbot.connector_delivery_failed",
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                delivered = False

            if delivered:
                return JSONResponse({"status": "accepted", "delivery": "connector"}, headers=response_headers)

            _log_json(logging.WARNING, "router_chatbot.connector_delivery_fallback_to_response_body")

        return JSONResponse(response_payload, headers=response_headers)


async def _messages_health_handler(request: Request) -> JSONResponse:
    """Return a simple readiness response for Agents Playground wait-on checks."""

    config: RouterChatbotConfig = request.app.state.router_chatbot_config
    return JSONResponse(
        {
            "status": "ok",
            "endpoint": config.endpoint_path,
            "ready": True,
        }
    )


def create_router_chatbot_app(config: RouterChatbotConfig | None = None) -> Starlette:
    """Create an ASGI app exposing RouterWorkflow as a single chatbot endpoint."""

    resolved = config or RouterChatbotConfig.from_env()
    service = RouterChatService(
        mcp_url=resolved.mcp_url,
        request_timeout_seconds=resolved.request_timeout_seconds,
    )

    app = Starlette(
        debug=False,
        routes=[
            Route(resolved.endpoint_path, _messages_health_handler, methods=["GET", "HEAD"]),
            Route(resolved.endpoint_path, _messages_handler, methods=["POST"]),
        ],
    )
    app.state.router_chat_service = service
    app.state.router_chatbot_config = resolved
    app.state.welcomed_conversation_ids = set()
    return app
