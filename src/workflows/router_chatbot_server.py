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
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx
from agent_framework import CheckpointStorage, InMemoryCheckpointStorage, WorkflowCheckpointException
from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.trace import SpanKind
from pydantic import BaseModel, Field, ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from agents.session_store import ActiveWorkflowRun, InMemorySessionStore, SessionKey, SessionRecord
from workflows.router_agent import RouterWorkflowAgentAdapter

# NOTE: InMemorySessionStore now extends agent_framework.SessionStore
# SessionKey is maintained for backward compatibility (generates session_id via SHA256)
# SessionRecord holds metadata and history for multi-turn conversations

logger = logging.getLogger(__name__)

_LOCAL_ERROR_MESSAGE = (
    "I ran into an error while processing your request. Please try again with a knowledge-base question."
)
_WELCOME_MESSAGE = (
    "Welcome. I can route your question across GraphRAG workflows. Ask me anything about the knowledge base."
)
_TRACER = trace.get_tracer(__name__)
_PLAYGROUND_HEADER = "x-ms-agents-playground"
_CONNECTOR_DELIVERY_TIMEOUT_SECONDS = 15.0
_DEFAULT_PROGRESS_STATUS = "Processing your request..."

_ROUTING_STATUS_MESSAGE = "Routing your question..."
_GUIDANCE_STATUS_MESSAGE = "Preparing guidance response..."
_EXECUTOR_PROGRESS_MESSAGES: dict[str, str] = {
    "WorkflowRouter": _ROUTING_STATUS_MESSAGE,
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
    "OutOfContextResponder": _GUIDANCE_STATUS_MESSAGE,
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
        "OutOfContextResponder": _GUIDANCE_STATUS_MESSAGE,
    },
}

_STAGE_PROGRESS_MESSAGES: dict[str, str] = {
    "router_delegation": _ROUTING_STATUS_MESSAGE,
    "out_of_context_response": _GUIDANCE_STATUS_MESSAGE,
    "workflow_runner_started": "Starting workflow execution...",
    "workflow_runner_completed": "Finalizing response...",
}
_MESSAGE_ACTIVITY_TYPE = "message"
_TYPING_ACTIVITY_TYPE = "typing"
_CONVERSATION_UPDATE_ACTIVITY_TYPE = "conversationUpdate"
_INSTALLATION_UPDATE_ACTIVITY_TYPE = "installationUpdate"
_ROUTER_CHANNEL_DATA_TYPE = "router"
_LOCK_CONTENTION_WARN_MS = 100.0


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
    session_ttl_seconds: int = Field(default=1800, ge=60, le=86400)
    session_max_count: int = Field(default=1000, ge=1, le=50000)
    session_cleanup_interval_seconds: int = Field(default=60, ge=1, le=3600)
    session_max_history_groups: int = Field(default=12, ge=1, le=200)

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
            "typing_keepalive_slow_after_seconds": os.getenv(
                "ROUTER_CHATBOT_TYPING_KEEPALIVE_SLOW_AFTER_SECONDS", "20"
            ),
            "progress_status_after_seconds": os.getenv("ROUTER_CHATBOT_PROGRESS_STATUS_AFTER_SECONDS", "8"),
            "progress_status_min_interval_seconds": os.getenv(
                "ROUTER_CHATBOT_PROGRESS_STATUS_MIN_INTERVAL_SECONDS",
                "6",
            ),
            "session_ttl_seconds": os.getenv("SESSION_TTL_SECONDS", "1800"),
            "session_max_count": os.getenv("SESSION_MAX_COUNT", "1000"),
            "session_cleanup_interval_seconds": os.getenv("SESSION_CLEANUP_INTERVAL_SECONDS", "60"),
            "session_max_history_groups": os.getenv("SESSION_MAX_HISTORY_GROUPS", "12"),
        }
        try:
            return cls.model_validate(data)
        except ValidationError as exc:  # pragma: no cover - defensive guard
            raise ValueError(str(exc)) from exc


class RouterChatService:
    """Async facade that executes RouterWorkflow for a single user message."""

    def __init__(
        self,
        *,
        mcp_url: str | None,
        request_timeout_seconds: float,
        session_store: InMemorySessionStore,
        adapter: RouterWorkflowAgentAdapter | None = None,
        checkpoint_storage: CheckpointStorage | None = None,
    ) -> None:
        self._request_timeout_seconds = request_timeout_seconds
        self._session_store = session_store
        self._adapter = adapter if adapter is not None else RouterWorkflowAgentAdapter(mcp_url=mcp_url)
        self._checkpoint_storage = checkpoint_storage

    async def answer(
        self,
        text: str,
        *,
        session_record: SessionRecord | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        lock_wait_ms: float | None = None,
    ) -> RouterChatReply:
        """Return the router workflow answer for a user text input."""

        session_id: str | None = None
        turn_index = 1
        memory_hits = 0
        query_text = text

        if session_record is not None:
            session_id = session_record.session_id
            turn_index = session_record.turn_index + 1
            memory_hits = len(session_record.history_groups)
            query_text = self._build_session_aware_query(text, session_record)

        runtime_telemetry: dict[str, object] | None = None
        if lock_wait_ms is not None:
            runtime_telemetry = {"lock_wait_ms": lock_wait_ms}

        # Validate and resolve checkpoint for resume
        resume_checkpoint_id: str | None = None
        if session_record is not None and session_record.active_workflow_run is not None:
            resume_checkpoint_id = await self._resolve_resume_checkpoint(session_record.active_workflow_run)
            if resume_checkpoint_id is None:
                session_record.active_workflow_run = None  # stale or incompatible — discard

        stream_kwargs: dict[str, Any] = {}
        if self._checkpoint_storage is not None:
            stream_kwargs["checkpoint_storage"] = self._checkpoint_storage
        if resume_checkpoint_id is not None:
            stream_kwargs["checkpoint_id"] = resume_checkpoint_id

        try:
            async with asyncio.timeout(self._request_timeout_seconds):
                stream, finalize = await self._adapter.create_stream(
                    query_text,
                    session_record=session_record,
                    session_telemetry=runtime_telemetry,
                    **stream_kwargs,
                )
                if on_progress is not None:
                    await on_progress(_ROUTING_STATUS_MESSAGE)
                await _drain_stream(stream, on_progress)
                result = await finalize()
        except TimeoutError:
            if session_record is not None:
                await self._save_checkpoint_after_interruption(session_record)
            raise

        compaction_events = 0
        if session_record is not None:
            diagnostics = self._session_store.append_turn(
                session_record,
                user_text=text,
                assistant_text=result.answer,
            )
            compaction_events = diagnostics.compacted_groups
            # Clear any pending workflow run on successful completion.
            session_record.active_workflow_run = None

        routed_workflow, classifier_status, fallback_reason = _extract_router_metadata(result)

        return RouterChatReply(
            answer=result.answer,
            routed_workflow=routed_workflow,
            classifier_status=classifier_status,
            fallback_reason=fallback_reason,
            total_elapsed_seconds=result.total_elapsed_seconds,
            session_id=session_id,
            turn_index=turn_index,
            memory_hits=memory_hits,
            compaction_events=compaction_events,
            resumed_from_checkpoint=resume_checkpoint_id is not None,
            checkpoint_id_used=resume_checkpoint_id,
        )

    async def _resolve_resume_checkpoint(self, run: ActiveWorkflowRun) -> str | None:
        """Validate a stored checkpoint and return its ID for resume, or None if stale/incompatible."""
        if self._checkpoint_storage is None:
            return None
        try:
            loaded = await self._checkpoint_storage.load(run.checkpoint_id)
            # Reject if the checkpoint was saved for a different workflow type.
            if loaded.workflow_name != run.workflow_type:
                logger.debug(
                    "Checkpoint %s incompatible (workflow %s != %s); discarding",
                    run.checkpoint_id,
                    loaded.workflow_name,
                    run.workflow_type,
                )
                return None
            logger.info("Resuming from checkpoint %s (workflow=%s)", run.checkpoint_id, run.workflow_type)
            return run.checkpoint_id
        except WorkflowCheckpointException:
            logger.debug("Checkpoint %s is stale; discarding", run.checkpoint_id)
            return None

    async def _save_checkpoint_after_interruption(self, session_record: SessionRecord) -> None:
        """Capture the latest superstep checkpoint into the session after a timeout."""
        if self._checkpoint_storage is None:
            return
        for workflow_type in ("sequential", "concurrent", "handoff"):
            checkpoint = await self._checkpoint_storage.get_latest(workflow_name=workflow_type)
            if checkpoint is not None:
                session_record.active_workflow_run = ActiveWorkflowRun(
                    workflow_run_id=str(uuid.uuid4()),
                    checkpoint_id=checkpoint.checkpoint_id,
                    workflow_type=workflow_type,
                )
                logger.info(
                    "Captured checkpoint %s after timeout (workflow=%s)",
                    checkpoint.checkpoint_id,
                    workflow_type,
                )
                return

    @staticmethod
    def _build_session_aware_query(text: str, session_record: SessionRecord) -> str:
        """Build a bounded history prompt to preserve multi-turn context."""

        if not session_record.history_groups:
            return text

        history_lines: list[str] = []
        for group in session_record.history_groups:
            user_text = group.get("user", "")
            assistant_text = group.get("assistant", "")
            if user_text:
                history_lines.append(f"User: {user_text}")
            if assistant_text:
                history_lines.append(f"Assistant: {assistant_text}")

        if not history_lines:
            return text

        history_block = "\n".join(history_lines)
        return f"Conversation context (latest turns):\n{history_block}\n\nCurrent user message:\n{text}"


@dataclass(slots=True)
class RouterChatReply:
    """Structured chatbot reply plus router metadata for diagnostics."""

    answer: str
    routed_workflow: str | None = None
    classifier_status: str | None = None
    fallback_reason: str | None = None
    total_elapsed_seconds: float | None = None
    session_id: str | None = None
    turn_index: int | None = None
    memory_hits: int | None = None
    compaction_events: int | None = None
    lock_wait_ms: float | None = None
    lock_hold_ms: float | None = None
    resumed_from_checkpoint: bool = False
    checkpoint_id_used: str | None = None


def _copy_activity_context(request_activity: Mapping[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    """Populate a Bot Framework-like response with the request's routing context."""
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


def _emit_lock_span_diagnostics(lock_wait_ms: float, lock_hold_ms: float) -> None:
    """Emit lock timing attributes/events to the active request span."""

    span = trace.get_current_span()
    if not span.get_span_context().is_valid:
        return

    span.set_attribute("router.lock_wait_ms", lock_wait_ms)
    span.set_attribute("router.lock_hold_ms", lock_hold_ms)

    if lock_wait_ms > _LOCK_CONTENTION_WARN_MS:
        span.add_event(
            "router.session_lock_contention",
            {
                "router.lock_wait_ms": lock_wait_ms,
                "router.lock_hold_ms": lock_hold_ms,
                "router.warn_threshold_ms": _LOCK_CONTENTION_WARN_MS,
            },
        )


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
        updated_workflow = _update_routed_workflow(data, routed_workflow)
        stage_message = _status_text_for_stage(data, updated_workflow)
        if stage_message is not None:
            return stage_message, updated_workflow

    if event_type in {"executor_invoked", "executor_completed"}:
        return _status_text_for_executor(event, updated_workflow)

    return None, updated_workflow


def _update_routed_workflow(data: Mapping[str, Any], routed_workflow: str | None) -> str | None:
    routed = _normalize_routed_workflow(data.get("routed_workflow"))
    return routed if routed is not None else routed_workflow


def _status_text_for_stage(data: Mapping[str, Any], routed_workflow: str | None) -> str | None:
    stage = data.get("stage")
    if isinstance(stage, str):
        stage_message = _STAGE_PROGRESS_MESSAGES.get(stage)
        if stage_message is not None:
            return stage_message

    if routed_workflow == "sequential":
        return "Running sequential reasoning..."
    if routed_workflow == "concurrent":
        return "Running parallel retrieval..."
    if routed_workflow == "handoff":
        return "Coordinating specialist handoff..."
    if routed_workflow == "out_of_context":
        return _GUIDANCE_STATUS_MESSAGE
    return None


def _status_text_for_executor(event: Any, routed_workflow: str | None) -> tuple[str | None, str | None]:
    executor_id = getattr(event, "executor_id", None)
    if not isinstance(executor_id, str):
        return None, routed_workflow

    if routed_workflow is not None:
        workflow_messages = _WORKFLOW_EXECUTOR_PROGRESS_MESSAGES.get(routed_workflow, {})
        workflow_message = workflow_messages.get(executor_id)
        if workflow_message is not None:
            return workflow_message, routed_workflow

    generic_message = _EXECUTOR_PROGRESS_MESSAGES.get(executor_id)
    if generic_message is not None:
        return generic_message, routed_workflow
    return None, routed_workflow


async def _drain_stream(
    stream: Any,
    on_progress: Callable[[str], Awaitable[None]] | None,
) -> None:
    """Drain workflow stream events, forwarding progress messages when provided."""
    routed_workflow: str | None = None
    async for event in stream:
        if on_progress is None:
            continue
        status_text, routed_workflow = _status_text_from_event(event, routed_workflow=routed_workflow)
        if status_text is not None:
            await on_progress(status_text)


def _extract_router_metadata(result: Any) -> tuple[str | None, str | None, str | None]:
    """Extract routed_workflow, classifier_status, fallback_reason from the first step."""
    if not result.steps:
        return None, None, None
    metadata = result.steps[0].metadata
    routed = metadata.get("routed_workflow")
    status = metadata.get("classifier_status")
    fallback = metadata.get("fallback_reason")
    return (
        routed if isinstance(routed, str) else None,
        status if isinstance(status, str) else None,
        fallback if isinstance(fallback, str) else None,
    )


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


def _resolve_session_key(activity: Mapping[str, Any]) -> SessionKey:
    """Resolve a deterministic session key from channel, conversation, and user."""

    channel_id = activity.get("channelId")
    conversation_id = _conversation_id(activity)
    sender = activity.get("from")
    user_id = ""
    if isinstance(sender, Mapping):
        candidate = sender.get("id")
        if isinstance(candidate, str):
            user_id = candidate

    return SessionKey.create(
        channel_id=channel_id if isinstance(channel_id, str) else "",
        conversation_id=conversation_id,
        user_id=user_id,
    )


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


def _build_router_metadata(reply: RouterChatReply) -> dict[str, Any]:
    """Build the router section of channelData from reply fields."""
    metadata: dict[str, Any] = {}
    if reply.routed_workflow is not None:
        metadata["routed_workflow"] = reply.routed_workflow
    if reply.classifier_status is not None:
        metadata["classifier_status"] = reply.classifier_status
    if reply.fallback_reason is not None:
        metadata["fallback_reason"] = reply.fallback_reason
    if reply.total_elapsed_seconds is not None:
        metadata["elapsed_seconds"] = round(reply.total_elapsed_seconds, 3)
    return metadata


def _build_session_metadata(reply: RouterChatReply) -> dict[str, Any]:
    """Build the session section of channelData from reply fields."""
    metadata: dict[str, Any] = {}
    if reply.session_id is not None:
        metadata["session_id"] = reply.session_id
    if reply.turn_index is not None:
        metadata["turn_index"] = reply.turn_index
    if reply.memory_hits is not None:
        metadata["memory_hits"] = reply.memory_hits
    if reply.compaction_events is not None:
        metadata["compaction_events"] = reply.compaction_events
    if reply.lock_wait_ms is not None:
        metadata["lock_wait_ms"] = round(reply.lock_wait_ms, 3)
    if reply.lock_hold_ms is not None:
        metadata["lock_hold_ms"] = round(reply.lock_hold_ms, 3)
    if reply.resumed_from_checkpoint:
        metadata["resumed_from_checkpoint"] = True
    if reply.checkpoint_id_used is not None:
        metadata["checkpoint_id_used"] = reply.checkpoint_id_used
    return metadata


def build_reply_activity(request_activity: Mapping[str, Any], reply: RouterChatReply) -> dict[str, Any]:
    """Build a minimal reply activity compatible with local playground clients."""

    response: dict[str, Any] = {"type": "message", "text": reply.answer}

    router_metadata = _build_router_metadata(reply)
    if router_metadata:
        response["channelData"] = {"router": router_metadata}

    session_metadata = _build_session_metadata(reply)
    if session_metadata:
        response.setdefault("channelData", {})["session"] = session_metadata

    _copy_activity_context(request_activity, response)

    reply_to = request_activity.get("id")
    if isinstance(reply_to, str) and reply_to:
        response["replyToId"] = reply_to

    return response


def build_typing_activity(request_activity: Mapping[str, Any]) -> dict[str, Any]:
    """Build a typing activity compatible with Bot Framework channels."""

    response: dict[str, Any] = {
        "type": _TYPING_ACTIVITY_TYPE,
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
        "type": _MESSAGE_ACTIVITY_TYPE,
        "text": status_text,
        "channelData": {_ROUTER_CHANNEL_DATA_TYPE: {"status": "processing"}},
    }

    return _copy_activity_context(request_activity, response)


async def _messages_handler(request: Request) -> JSONResponse:
    """Handle incoming activity messages from local Agents Playground."""

    service: RouterChatService = request.app.state.router_chat_service
    config: RouterChatbotConfig = request.app.state.router_chatbot_config
    session_store: InMemorySessionStore = request.app.state.session_store
    welcomed_conversation_ids: set[str] = request.app.state.welcomed_conversation_ids
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return JSONResponse({"error": "Invalid JSON payload."}, status_code=400)

    if not isinstance(payload, dict):
        return JSONResponse({"error": "Activity payload must be a JSON object."}, status_code=400)

    incoming_headers = dict(request.headers.items())
    incoming_context = extract(incoming_headers)

    with _TRACER.start_as_current_span(
        "router_chatbot.handle_activity", context=incoming_context, kind=SpanKind.SERVER
    ):
        activity_type = payload.get("type")
        if activity_type in {_CONVERSATION_UPDATE_ACTIVITY_TYPE, _INSTALLATION_UPDATE_ACTIVITY_TYPE}:
            return await _handle_welcome_activity(payload, welcomed_conversation_ids, config, incoming_headers)

        if activity_type != _MESSAGE_ACTIVITY_TYPE:
            return _handle_unsupported_activity(payload)

        return await _handle_message_activity(payload, service, session_store, config, incoming_headers)


async def _handle_welcome_activity(
    payload: Mapping[str, Any],
    welcomed_conversation_ids: set[str],
    config: RouterChatbotConfig,
    incoming_headers: Mapping[str, str],
) -> JSONResponse:
    """Handle welcome-style activities for local playground sessions."""
    conversation_id = _conversation_id(payload)
    if conversation_id and conversation_id in welcomed_conversation_ids:
        _log_json(
            logging.INFO,
            "router_chatbot.welcome_skipped_duplicate",
            activity_type=str(payload.get("type")),
            conversation_id=conversation_id,
        )
        return JSONResponse({"status": "ignored", "reason": "welcome_already_sent"})

    if conversation_id:
        welcomed_conversation_ids.add(conversation_id)

    _log_json(logging.INFO, "router_chatbot.welcome", activity_type=str(payload.get("type")))
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


def _handle_unsupported_activity(payload: Mapping[str, Any]) -> JSONResponse:
    """Return a response for unsupported activity types."""
    _log_json(logging.INFO, "router_chatbot.unsupported_activity", activity_type=str(payload.get("type")))
    info_answer = "This endpoint only supports message activities in local development."
    response_headers: dict[str, str] = {}
    _inject_trace_headers(response_headers)
    return JSONResponse(build_reply_activity(payload, RouterChatReply(answer=info_answer)), headers=response_headers)


async def _handle_message_activity(
    payload: Mapping[str, Any],
    service: RouterChatService,
    session_store: InMemorySessionStore,
    config: RouterChatbotConfig,
    incoming_headers: Mapping[str, str],
) -> JSONResponse:
    """Process a user message using the router workflow and return the response."""
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

    session_key = _resolve_session_key(payload)
    session_record, _ = await session_store.get_or_create(session_key.session_id)

    typing_task: asyncio.Task[None] | None = None
    typing_stop_event: asyncio.Event | None = None
    status_message_sent = False
    last_progress_status = _DEFAULT_PROGRESS_STATUS
    processing_started_at = time.perf_counter()

    async def _on_progress(status_text: str) -> None:
        nonlocal last_progress_status, status_message_sent

        if not status_text.strip():
            return

        last_progress_status = status_text.strip()
        if not _should_emit_progress_status(incoming_headers, config, processing_started_at):
            return

        delivered = await _dispatch_progress_status_message(
            incoming_activity=payload,
            incoming_headers=incoming_headers,
            status_text=last_progress_status,
        )
        if delivered:
            status_message_sent = True
            _log_json(logging.INFO, "router_chatbot.progress_status_sent", status_text=last_progress_status)

    typing_stop_event, typing_task = await _start_playground_typing(payload, incoming_headers, config)

    started = time.perf_counter()
    lock_wait_started = time.perf_counter()
    lock_wait_ms = 0.0
    lock_hold_ms = 0.0

    try:
        async with session_record.lock:
            lock_wait_ms = (time.perf_counter() - lock_wait_started) * 1000
            lock_hold_started = time.perf_counter()
            try:
                reply = await service.answer(
                    text,
                    session_record=session_record,
                    on_progress=_on_progress,
                    lock_wait_ms=lock_wait_ms,
                )
            finally:
                # Measure hold time on both success and failure so contention is never
                # under-reported for the request that actually triggered the error.
                lock_hold_ms = (time.perf_counter() - lock_hold_started) * 1000
            reply.lock_wait_ms = lock_wait_ms
            reply.lock_hold_ms = lock_hold_ms
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
        reply.session_id = session_key.session_id
        reply.lock_wait_ms = lock_wait_ms
        reply.lock_hold_ms = lock_hold_ms
    finally:
        await _finalize_message_processing(
            payload=payload,
            incoming_headers=incoming_headers,
            config=config,
            processing_started_at=processing_started_at,
            last_progress_status=last_progress_status,
            status_message_sent=status_message_sent,
            typing_stop_event=typing_stop_event,
            typing_task=typing_task,
        )

    _emit_lock_span_diagnostics(lock_wait_ms=lock_wait_ms, lock_hold_ms=lock_hold_ms)

    elapsed_ms = (time.perf_counter() - started) * 1000
    _log_json(
        logging.INFO,
        "router_chatbot.message_processed",
        conversation_id=conversation_id,
        message_id=message_id_text,
        routed_workflow=reply.routed_workflow,
        classifier_status=reply.classifier_status,
        fallback_reason=reply.fallback_reason,
        session_id=reply.session_id,
        turn_index=reply.turn_index,
        memory_hits=reply.memory_hits,
        compaction_events=reply.compaction_events,
        resumed_from_checkpoint=reply.resumed_from_checkpoint or None,
        checkpoint_id_used=reply.checkpoint_id_used,
        lock_wait_ms=round(lock_wait_ms, 3),
        lock_hold_ms=round(lock_hold_ms, 3),
        active_sessions=session_store.metrics.active_sessions,
        session_evictions=session_store.metrics.evictions,
        session_ttl_expirations=session_store.metrics.ttl_expirations,
        session_cleanup_runs=session_store.metrics.cleanup_runs,
        elapsed_ms=round(elapsed_ms, 1),
    )

    response_payload = build_reply_activity(payload, reply)
    response_headers = _build_response_headers(reply)
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


async def _start_playground_typing(
    payload: Mapping[str, Any],
    incoming_headers: Mapping[str, str],
    config: RouterChatbotConfig,
) -> tuple[asyncio.Event | None, asyncio.Task[None] | None]:
    """Start typing and keepalive tasks for playground requests."""
    if not _is_playground_request(incoming_headers):
        return None, None

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
    return typing_stop_event, typing_task


async def _finalize_message_processing(
    *,
    payload: Mapping[str, Any],
    incoming_headers: Mapping[str, str],
    config: RouterChatbotConfig,
    processing_started_at: float,
    last_progress_status: str,
    status_message_sent: bool,
    typing_stop_event: asyncio.Event | None,
    typing_task: asyncio.Task[None] | None,
) -> None:
    """Send a fallback progress update and stop typing keepalive tasks."""
    if _is_playground_request(incoming_headers):
        elapsed = time.perf_counter() - processing_started_at
        if (
            not status_message_sent
            and config.progress_status_after_seconds > 0
            and elapsed >= config.progress_status_after_seconds
        ):
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


def _should_emit_progress_status(
    incoming_headers: Mapping[str, str],
    config: RouterChatbotConfig,
    processing_started_at: float,
) -> bool:
    """Return True when a progress update should be emitted for the current request."""
    if not _is_playground_request(incoming_headers):
        return False
    if config.progress_status_after_seconds <= 0:
        return False

    now = time.perf_counter()
    elapsed = now - processing_started_at
    if elapsed < config.progress_status_after_seconds:
        return False

    return True


def _build_response_headers(reply: RouterChatReply) -> dict[str, str]:
    """Build response headers for routed workflow and classifier metadata."""
    response_headers: dict[str, str] = {}
    if reply.routed_workflow:
        response_headers["x-router-routed-workflow"] = reply.routed_workflow
    if reply.classifier_status:
        response_headers["x-router-classifier-status"] = reply.classifier_status
    return response_headers


def _messages_health_handler(request: Request) -> JSONResponse:
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
    session_store = InMemorySessionStore(
        ttl_seconds=resolved.session_ttl_seconds,
        max_count=resolved.session_max_count,
        cleanup_interval_seconds=resolved.session_cleanup_interval_seconds,
        max_history_groups=resolved.session_max_history_groups,
    )
    checkpoint_storage = InMemoryCheckpointStorage()
    service = RouterChatService(
        mcp_url=resolved.mcp_url,
        request_timeout_seconds=resolved.request_timeout_seconds,
        session_store=session_store,
        checkpoint_storage=checkpoint_storage,
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
    app.state.session_store = session_store
    app.state.checkpoint_storage = checkpoint_storage
    app.state.welcomed_conversation_ids = set()
    return app
