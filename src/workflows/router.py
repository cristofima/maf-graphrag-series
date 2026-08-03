"""Workflow router that selects the optimal pattern per query."""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, cast

from agent_framework import WorkflowEvent
from agent_framework.exceptions import ChatClientException

from agents.router_classifier import RouterClassification, RouterClassifier

try:  # pragma: no cover - optional runtime dependency guard
    from opentelemetry import trace
except Exception:  # pragma: no cover - fallback when otel isn't installed
    trace = None  # type: ignore[assignment]

from workflows.base import (
    WorkflowResult,
    WorkflowStep,
    WorkflowType,
    create_concurrent_workflow,
    create_handoff_workflow,
    create_sequential_workflow,
    ensure_text,
)

logger = logging.getLogger(__name__)
_TRACER = trace.get_tracer(__name__) if trace is not None else None

WorkflowFactory = Callable[[str | None], Any]

_DEFAULT_FACTORIES: dict[WorkflowType, WorkflowFactory] = {
    WorkflowType.SEQUENTIAL: create_sequential_workflow,
    WorkflowType.CONCURRENT: create_concurrent_workflow,
    WorkflowType.HANDOFF: create_handoff_workflow,
}

_CLASSIFIER_MAX_ATTEMPTS = 3
_CLASSIFIER_RETRY_DELAY_SECONDS = 0.6
_CLASSIFIER_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_ROUTER_HTTP_STATUS = re.compile(r"router HTTP error\s+(\d{3})", re.IGNORECASE)
_LOW_CONFIDENCE_FALLBACK = WorkflowType.SEQUENTIAL
_MIN_ROUTING_CONFIDENCE_SCORE = 80
_OUT_OF_CONTEXT_ROUTE = "out_of_context"
_OUT_OF_CONTEXT_MESSAGE = (
    "I can help with questions about the indexed knowledge base (people, projects, teams, technologies, "
    "and relationships). Please ask a query related to that context."
)
_EVENT_PROGRESS = "progress"
_EVENT_EXECUTOR_INVOKED = "executor_invoked"
_EVENT_EXECUTOR_COMPLETED = "executor_completed"
_EVENT_OUTPUT = "output"
_ROUTER_ROUTED_WORKFLOW_EVENT_KEY = "router.routed_workflow"


def _supports_keyword_argument(callable_obj: Callable[..., Any], keyword: str) -> bool:
    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError):
        return False

    for parameter in signature.parameters.values():
        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
            return True
    return keyword in signature.parameters


@dataclass(slots=True)
class RouterOutcome:
    """Internal helper capturing router decision and classification timing."""

    classification: RouterClassification
    elapsed_seconds: float
    classifier_status: str = "success"
    classifier_attempts: int = 1
    fallback_reason: str | None = None
    classifier_error: str | None = None


class RouterWorkflow:
    """High-level workflow that delegates to a specialist pattern."""

    def __init__(
        self,
        mcp_url: str | None = None,
        *,
        classifier: RouterClassifier | None = None,
        workflow_factories: Mapping[WorkflowType, WorkflowFactory] | None = None,
    ) -> None:
        self._mcp_url = mcp_url
        self._classifier = classifier or RouterClassifier()
        self._workflow_factories = {**_DEFAULT_FACTORIES, **(workflow_factories or {})}
        self._entered = False
        self._last_query: str | None = None

    async def __aenter__(self) -> RouterWorkflow:
        await self._classifier.__aenter__()
        self._entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self._classifier.__aexit__(exc_type, exc_val, exc_tb)
        self._entered = False

    def prepare_run(self, query: object) -> str:
        """Normalize *query* and reset transient state for a new execution."""

        normalized = self._normalize_query_text(query)
        self._last_query = normalized
        return normalized

    @staticmethod
    def _normalize_query_text(value: object) -> str:
        """Return a clean query string from common payload shapes."""

        if isinstance(value, str):
            extracted = RouterWorkflow._extract_query_from_string_payload(value)
            if extracted is not None:
                return extracted
            return value

        if isinstance(value, dict):
            extracted = RouterWorkflow._extract_query_from_mapping(value)
            if extracted is not None:
                return extracted

        return ensure_text(value)

    @staticmethod
    def _extract_query_from_string_payload(value: str) -> str | None:
        stripped = value.strip()
        if not (stripped.startswith("{") and stripped.endswith("}")):
            return None

        for parser in (RouterWorkflow._parse_json_like_dict, RouterWorkflow._parse_python_like_dict):
            parsed = parser(stripped)
            if parsed is None:
                continue

            extracted = RouterWorkflow._extract_query_from_mapping(parsed)
            if extracted is not None:
                return extracted

        return None

    @staticmethod
    def _extract_query_from_mapping(payload: Mapping[str, object]) -> str | None:
        for key in ("input", "query", "question", "text"):
            candidate = payload.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        return None

    @staticmethod
    def _parse_json_like_dict(value: str) -> dict[str, object] | None:
        try:
            parsed = json.loads(value)
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _parse_python_like_dict(value: str) -> dict[str, object] | None:
        try:
            parsed = ast.literal_eval(value)
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _clip(value: str, limit: int = 800) -> str:
        if len(value) <= limit:
            return value
        return f"{value[: max(0, limit - 3)]}..."

    @staticmethod
    def _span_set_if_present(span: object | None, key: str, value: object | None) -> None:
        if span is None or value is None:
            return
        typed_span = cast(Any, span)
        if isinstance(value, (str, bool, int, float)):
            typed_span.set_attribute(key, value)
            return
        typed_span.set_attribute(key, RouterWorkflow._clip(str(value)))

    @staticmethod
    def _span_add_event(span: object | None, name: str, attributes: dict[str, object]) -> None:
        if span is None:
            return
        typed_span = cast(Any, span)
        safe_attributes: dict[str, object] = {}
        for key, value in attributes.items():
            if value is None:
                continue
            if isinstance(value, (str, bool, int, float)):
                safe_attributes[key] = value
            else:
                safe_attributes[key] = RouterWorkflow._clip(str(value))
        typed_span.add_event(name, attributes=safe_attributes)

    def _emit_routing_span(
        self,
        *,
        query: str,
        router_outcome: RouterOutcome,
        routed_workflow: str,
        response_output: str | None = None,
    ) -> None:
        """Emit explicit routing span attributes for observability dashboards."""

        if _TRACER is None:
            return

        classified_workflow = (
            router_outcome.classification.workflow_label or router_outcome.classification.workflow.value
        )

        with _TRACER.start_as_current_span("router.workflow.select") as span:
            self._span_set_if_present(span, "router.query", self._clip(query))
            self._span_set_if_present(span, "router.classified_workflow", classified_workflow)
            self._span_set_if_present(span, _ROUTER_ROUTED_WORKFLOW_EVENT_KEY, routed_workflow)
            self._span_set_if_present(span, "router.classifier_status", router_outcome.classifier_status)
            self._span_set_if_present(span, "router.classifier_attempts", router_outcome.classifier_attempts)
            self._span_set_if_present(span, "router.confidence_score", router_outcome.classification.confidence_score)
            self._span_set_if_present(span, "router.reason", router_outcome.classification.reason)
            self._span_set_if_present(span, "router.fallback_reason", router_outcome.fallback_reason)
            self._span_set_if_present(span, "router.classifier_error", router_outcome.classifier_error)
            self._span_set_if_present(
                span,
                "router.response_preview",
                self._clip(response_output) if response_output is not None else None,
            )
            self._span_set_if_present(
                span, "router.classification_raw", self._clip(router_outcome.classification.raw_response)
            )
            self._span_add_event(
                span,
                "router.workflow.decision",
                {
                    "router.classified_workflow": classified_workflow,
                    _ROUTER_ROUTED_WORKFLOW_EVENT_KEY: routed_workflow,
                    "router.confidence_score": router_outcome.classification.confidence_score,
                    "router.fallback_reason": router_outcome.fallback_reason,
                    "router.classifier_status": router_outcome.classifier_status,
                },
            )
            if response_output:
                self._span_add_event(
                    span,
                    "router.output.generated",
                    {
                        _ROUTER_ROUTED_WORKFLOW_EVENT_KEY: routed_workflow,
                        "router.response_preview": self._clip(response_output),
                    },
                )

    async def create_stream(
        self,
        normalized_query: str,
        *,
        include_status_events: bool = True,
        **run_kwargs: Any,
    ) -> tuple[Any, Callable[[], Awaitable[WorkflowResult]]]:
        """Return a stream adapter and finalize callback for DevUI streaming."""

        if not self._entered:
            raise RuntimeError("WorkflowRouter must be used inside an async context manager")

        router_outcome = await self._classify(normalized_query)
        if self._is_out_of_context_route(router_outcome.classification):
            self._emit_routing_span(
                query=normalized_query,
                router_outcome=router_outcome,
                routed_workflow=_OUT_OF_CONTEXT_ROUTE,
                response_output=_OUT_OF_CONTEXT_MESSAGE,
            )
            progress_payload = {
                "stage": "router_delegation",
                "classified_workflow": router_outcome.classification.workflow_label,
                "routed_workflow": _OUT_OF_CONTEXT_ROUTE,
                "confidence_score": router_outcome.classification.confidence_score,
                "classifier_status": router_outcome.classifier_status,
                "classifier_attempts": router_outcome.classifier_attempts,
                "fallback_reason": "out_of_context",
            }
            response_payload = {
                "stage": "out_of_context_response",
                "executor": "OutOfContextResponder",
                "response_type": "out_of_context",
                "output": _OUT_OF_CONTEXT_MESSAGE,
            }

            async def _stream_out_of_context() -> AsyncIterator[Any]:
                yield WorkflowEvent(type=cast(Any, _EVENT_PROGRESS), data=progress_payload)
                yield WorkflowEvent(
                    type=cast(Any, _EVENT_EXECUTOR_INVOKED),
                    executor_id="OutOfContextResponder",
                    data={"response_type": "out_of_context"},
                )
                yield WorkflowEvent(
                    type=cast(Any, _EVENT_OUTPUT),
                    executor_id="OutOfContextResponder",
                    data=_OUT_OF_CONTEXT_MESSAGE,
                )
                yield WorkflowEvent(
                    type=cast(Any, _EVENT_EXECUTOR_COMPLETED),
                    executor_id="OutOfContextResponder",
                    data={"response_type": "out_of_context"},
                )
                yield WorkflowEvent(type=cast(Any, _EVENT_PROGRESS), data=response_payload)

            return _stream_out_of_context(), self._build_out_of_context_finalize(
                normalized_query,
                router_outcome,
                include_status_events=include_status_events,
            )

        decision = self._resolve_workflow_decision(router_outcome)
        self._emit_routing_span(
            query=normalized_query,
            router_outcome=router_outcome,
            routed_workflow=decision.value,
        )
        factory = self._workflow_factories.get(decision) or create_sequential_workflow

        logger.info("Router selected '%s' workflow", decision.value)

        exit_stack = AsyncExitStack()
        workflow = await exit_stack.enter_async_context(factory(self._mcp_url))

        inner_normalized = workflow.prepare_run(normalized_query)
        stream_kwargs = dict(run_kwargs)
        if _supports_keyword_argument(workflow.create_stream, "include_status_events"):
            stream_kwargs["include_status_events"] = include_status_events
        stream, finalize_inner = workflow.create_stream(inner_normalized, **stream_kwargs)

        progress_payload = {
            "stage": "router_delegation",
            "classified_workflow": router_outcome.classification.workflow.value,
            "routed_workflow": decision.value,
            "confidence_score": router_outcome.classification.confidence_score,
            "classifier_status": router_outcome.classifier_status,
            "classifier_attempts": router_outcome.classifier_attempts,
            "fallback_reason": router_outcome.fallback_reason,
        }

        async def stream_with_router_progress() -> AsyncIterator[Any]:
            yield WorkflowEvent(type=cast(Any, _EVENT_PROGRESS), data=progress_payload)
            async for event in stream:
                yield event

        return stream_with_router_progress(), self._build_delegate_finalize(
            normalized_query=normalized_query,
            router_outcome=router_outcome,
            decision=decision,
            finalize_inner=finalize_inner,
            exit_stack=exit_stack,
        )

    async def run(
        self,
        query: str,
        *,
        include_status_events: bool = True,
        **run_kwargs: Any,
    ) -> WorkflowResult:
        if not self._entered:
            raise RuntimeError("WorkflowRouter must be used inside an async context manager")

        normalized_query = self.prepare_run(query)
        router_outcome = await self._classify(normalized_query)
        if self._is_out_of_context_route(router_outcome.classification):
            self._emit_routing_span(
                query=normalized_query,
                router_outcome=router_outcome,
                routed_workflow=_OUT_OF_CONTEXT_ROUTE,
                response_output=_OUT_OF_CONTEXT_MESSAGE,
            )
            return self._build_out_of_context_result(
                normalized_query,
                router_outcome,
                include_status_events=include_status_events,
            )

        decision = self._resolve_workflow_decision(router_outcome)
        self._emit_routing_span(
            query=normalized_query,
            router_outcome=router_outcome,
            routed_workflow=decision.value,
        )
        factory = self._workflow_factories.get(decision) or create_sequential_workflow

        logger.info("Router selected '%s' workflow", decision.value)

        async with factory(self._mcp_url) as workflow:
            delegated_kwargs = dict(run_kwargs)
            if _supports_keyword_argument(workflow.run, "include_status_events"):
                delegated_kwargs["include_status_events"] = include_status_events
            inner_result = await workflow.run(normalized_query, **delegated_kwargs)

        return self._combine_results(
            normalized_query=normalized_query,
            router_outcome=router_outcome,
            decision=decision,
            inner_result=inner_result,
        )

    async def _classify(self, query: str) -> RouterOutcome:
        start = time.perf_counter()
        last_error: Exception | None = None
        attempts_used = 1

        for attempt in range(1, _CLASSIFIER_MAX_ATTEMPTS + 1):
            attempts_used = attempt
            try:
                classification = await self._classifier.classify(query)
                elapsed = time.perf_counter() - start
                return RouterOutcome(
                    classification=classification,
                    elapsed_seconds=elapsed,
                    classifier_status="success",
                    classifier_attempts=attempt,
                )
            except (
                ChatClientException,
                RuntimeError,
                TimeoutError,
                ValueError,
            ) as exc:  # pragma: no cover - covered via fallback branch tests
                last_error = exc
                if attempt < _CLASSIFIER_MAX_ATTEMPTS and self._is_retryable_classifier_error(exc):
                    logger.warning(
                        "Router classifier attempt %d/%d failed (%s). Retrying in %.1fs.",
                        attempt,
                        _CLASSIFIER_MAX_ATTEMPTS,
                        type(exc).__name__,
                        _CLASSIFIER_RETRY_DELAY_SECONDS,
                    )
                    await asyncio.sleep(_CLASSIFIER_RETRY_DELAY_SECONDS)
                    continue

                logger.warning(
                    "Router classifier failed after %d attempt(s). Falling back to sequential workflow.",
                    attempt,
                )
                break

        elapsed = time.perf_counter() - start
        fallback_classification = RouterClassification(
            workflow=WorkflowType.SEQUENTIAL,
            raw_response="",
            reason="Classifier unavailable; defaulting to sequential workflow.",
            confidence_score=None,
            elapsed_seconds=elapsed,
            model_name="",
            router_mode="",
            router_subset="",
        )
        return RouterOutcome(
            classification=fallback_classification,
            elapsed_seconds=elapsed,
            classifier_status="fallback",
            classifier_attempts=attempts_used,
            fallback_reason="classifier_error",
            classifier_error=str(last_error).strip() if last_error else None,
        )

    def _resolve_workflow_decision(self, router_outcome: RouterOutcome) -> WorkflowType:
        decision = router_outcome.classification.workflow

        score = router_outcome.classification.confidence_score
        if score is None:
            router_outcome.fallback_reason = router_outcome.fallback_reason or "missing_confidence_score"
            return _LOW_CONFIDENCE_FALLBACK
        if score < _MIN_ROUTING_CONFIDENCE_SCORE:
            router_outcome.fallback_reason = router_outcome.fallback_reason or "low_confidence_score"
            return _LOW_CONFIDENCE_FALLBACK

        if decision in self._workflow_factories:
            return decision

        router_outcome.fallback_reason = router_outcome.fallback_reason or "unknown_workflow"
        return WorkflowType.SEQUENTIAL

    @staticmethod
    def _is_retryable_classifier_error(error: Exception) -> bool:
        if isinstance(error, TimeoutError):
            return True

        status = RouterWorkflow._extract_status_code(error)
        if status is not None:
            return status in _CLASSIFIER_RETRYABLE_STATUS_CODES

        message = str(error).lower()
        return "timed out" in message or "throttl" in message

    @staticmethod
    def _extract_status_code(error: Exception) -> int | None:
        direct_status = getattr(error, "status_code", None)
        if isinstance(direct_status, int):
            return direct_status

        response = getattr(error, "response", None)
        if response is not None:
            response_status = getattr(response, "status_code", None)
            if isinstance(response_status, int):
                return response_status

        message = str(error)
        match = _ROUTER_HTTP_STATUS.search(message)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    @staticmethod
    def _format_router_output(classification: RouterClassification) -> str:
        parts = [f"Workflow: {classification.workflow.value}"]
        if classification.reason:
            parts.append(f"Reason: {classification.reason}")
        if classification.confidence_score is not None:
            parts.append(f"Confidence score: {classification.confidence_score}")
        return " | ".join(parts)

    @staticmethod
    def _build_metadata(decision: WorkflowType, classification: RouterClassification) -> dict[str, object]:
        classified_workflow = classification.workflow_label or classification.workflow.value
        metadata: dict[str, object] = {
            "routed_workflow": decision.value,
            "classified_workflow": classified_workflow,
            "router_model": classification.model_name,
        }
        if classification.confidence_score is not None:
            metadata["confidence_score"] = classification.confidence_score
            metadata["min_routing_confidence_score"] = _MIN_ROUTING_CONFIDENCE_SCORE
        if classification.router_mode:
            metadata["router_mode"] = classification.router_mode
        if classification.router_subset:
            metadata["router_subset"] = classification.router_subset
        return metadata

    def _combine_results(
        self,
        *,
        normalized_query: str,
        router_outcome: RouterOutcome,
        decision: WorkflowType,
        inner_result: WorkflowResult,
    ) -> WorkflowResult:
        router_step = WorkflowStep(
            agent_name="WorkflowRouter",
            input_summary="Classify query",
            output=self._format_router_output(router_outcome.classification),
            elapsed_seconds=router_outcome.elapsed_seconds,
            metadata=self._build_metadata(decision, router_outcome.classification),
        )
        router_step.metadata["classifier_status"] = router_outcome.classifier_status
        router_step.metadata["classifier_attempts"] = router_outcome.classifier_attempts
        if router_outcome.fallback_reason:
            router_step.metadata["fallback_reason"] = router_outcome.fallback_reason
        if router_outcome.classifier_error:
            router_step.metadata["classifier_error"] = router_outcome.classifier_error

        combined_steps = [router_step, *inner_result.steps]
        total_elapsed = router_outcome.elapsed_seconds + inner_result.total_elapsed_seconds

        return WorkflowResult(
            answer=inner_result.answer,
            workflow_type=WorkflowType.ROUTER,
            steps=combined_steps,
            total_elapsed_seconds=total_elapsed,
            query=inner_result.query or normalized_query or self._last_query or "",
        )

    def _build_out_of_context_finalize(
        self,
        normalized_query: str,
        router_outcome: RouterOutcome,
        *,
        include_status_events: bool,
    ) -> Callable[[], Awaitable[WorkflowResult]]:
        def finalize() -> Awaitable[WorkflowResult]:
            result = self._build_out_of_context_result(
                normalized_query,
                router_outcome,
                include_status_events=include_status_events,
            )
            return asyncio.sleep(0, result=result)

        return finalize

    def _build_delegate_finalize(
        self,
        *,
        normalized_query: str,
        router_outcome: RouterOutcome,
        decision: WorkflowType,
        finalize_inner: Callable[[], Awaitable[WorkflowResult]],
        exit_stack: AsyncExitStack,
    ) -> Callable[[], Awaitable[WorkflowResult]]:
        def finalize() -> Awaitable[WorkflowResult]:
            async def _finalize() -> WorkflowResult:
                try:
                    inner_result = await finalize_inner()
                    return self._combine_results(
                        normalized_query=normalized_query,
                        router_outcome=router_outcome,
                        decision=decision,
                        inner_result=inner_result,
                    )
                finally:
                    await exit_stack.aclose()

            return _finalize()

        return finalize

    def _build_out_of_context_result(
        self,
        normalized_query: str,
        router_outcome: RouterOutcome,
        *,
        include_status_events: bool,
    ) -> WorkflowResult:
        classification = router_outcome.classification
        router_step = WorkflowStep(
            agent_name="WorkflowRouter",
            input_summary="Classify query",
            output=self._format_router_output(classification),
            elapsed_seconds=router_outcome.elapsed_seconds,
            metadata=self._build_metadata(WorkflowType.SEQUENTIAL, classification),
        )
        router_step.metadata["routed_workflow"] = _OUT_OF_CONTEXT_ROUTE
        router_step.metadata["classifier_status"] = router_outcome.classifier_status
        router_step.metadata["classifier_attempts"] = router_outcome.classifier_attempts
        router_step.metadata["fallback_reason"] = "out_of_context"
        if include_status_events:
            router_step.metadata["status"] = "completed"

        responder_step = WorkflowStep(
            agent_name="OutOfContextResponder",
            input_summary="Return guidance for out-of-context query",
            output=_OUT_OF_CONTEXT_MESSAGE,
            elapsed_seconds=0.0,
            metadata={"response_type": "out_of_context"},
        )
        if include_status_events:
            responder_step.metadata["status"] = "completed"

        return WorkflowResult(
            answer=_OUT_OF_CONTEXT_MESSAGE,
            workflow_type=WorkflowType.ROUTER,
            steps=[router_step, responder_step],
            total_elapsed_seconds=router_outcome.elapsed_seconds,
            query=normalized_query,
        )

    @staticmethod
    def _is_out_of_context_route(classification: RouterClassification) -> bool:
        return classification.workflow_label == _OUT_OF_CONTEXT_ROUTE


def create_router_workflow(mcp_url: str | None = None) -> RouterWorkflow:
    """Factory for CLI parity with other workflow helpers."""

    return RouterWorkflow(mcp_url=mcp_url)
