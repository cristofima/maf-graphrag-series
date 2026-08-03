"""Workflow router classifier powered by the Foundry Model Router deployment."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, NoReturn, cast

from agent_framework.exceptions import ChatClientException
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

try:  # pragma: no cover - optional runtime dependency guard
    from opentelemetry import trace
except ImportError:  # pragma: no cover - fallback when otel isn't installed
    trace = None  # type: ignore[assignment]

from agents.config import AgentConfig, get_agent_config
from core.classification_utils import normalize_confidence_score
from workflows.base import WorkflowType

logger = logging.getLogger(__name__)
_TRACER = trace.get_tracer(__name__) if trace is not None else None

# Regex helpers for stripping markdown code fences
_JSON_FENCE = re.compile(r"```json(.*?)```", re.DOTALL | re.IGNORECASE)
_GENERIC_FENCE = re.compile(r"```(.*?)```", re.DOTALL)

_ROUTER_SYSTEM_PROMPT = """You are a workflow router for the GraphRAG tutorial series.
Classify each question into the workflow that will produce the most
useful answer.

Workflows:
- sequential: Decompose complex questions, run a research plan, then write a structured report.
- concurrent: Run entity and thematic searches in parallel before synthesizing the answer.
- handoff: Route to a specialist (entity or themes) when the query is straightforward.

Return a compact JSON object with these fields:
{
  "workflow": "sequential" | "concurrent" | "handoff",
    "confidence_score": integer from 0 to 100,
  "reason": "short explanation (<=40 words)"
}
Do not include additional text or formatting outside the JSON object."""


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
            safe_attributes[key] = _clip(str(value))
    typed_span.add_event(name, attributes=safe_attributes)


_CLASSIFIER_TIMEOUT_SECONDS = 45.0


class RouterClassifierError(RuntimeError):
    """Raised when the router classifier cannot obtain a workflow decision."""


@dataclass(slots=True)
class RouterClassification:
    """Structured classification result."""

    workflow: WorkflowType
    raw_response: str
    reason: str | None = None
    confidence_score: int | None = None
    elapsed_seconds: float = 0.0
    model_name: str = ""
    router_mode: str = ""
    router_subset: str = ""


def _strip_fences(payload: str) -> str:
    """Best-effort extraction of the JSON payload from LLM output."""
    payload = payload.strip()
    fenced = _JSON_FENCE.search(payload)
    if fenced:
        return fenced.group(1).strip()
    fallback = _GENERIC_FENCE.search(payload)
    if fallback:
        return fallback.group(1).strip()
    return payload


def _parse_workflow(value: Any) -> WorkflowType:
    if not isinstance(value, str):
        return WorkflowType.SEQUENTIAL
    workflow_map = {
        "sequential": WorkflowType.SEQUENTIAL,
        "concurrent": WorkflowType.CONCURRENT,
        "handoff": WorkflowType.HANDOFF,
    }
    return workflow_map.get(value.strip().lower(), WorkflowType.SEQUENTIAL)


def _map_http_error_reason(status: int | None) -> str:
    if status == 404:
        return "router endpoint returned 404; verify AZURE_OPENAI_ROUTER_DEPLOYMENT, router endpoint, and API version"
    if status == 401:
        return "router request unauthorized; check credentials or Azure CLI login"
    if status == 429:
        return "router request throttled; retry after reducing frequency"
    if status:
        return f"router HTTP error {status}"
    return "classification error"


def _is_version_not_supported(error: BaseException) -> bool:
    """Return True when the router rejected the request due to API version."""

    message = str(error) if error else ""
    lowered = message.lower()
    if "api version not supported" in lowered or "unsupported api version" in lowered:
        return True

    detail = _extract_response_error_detail(getattr(error, "response", None))
    if detail is None:
        return False
    return "api version not supported" in detail.lower() or "unsupported api version" in detail.lower()


def _extract_response_error_detail(response: object | None) -> str | None:
    if response is None:
        return None

    payload = _safe_response_json(response)
    if isinstance(payload, Mapping):
        error_body = payload.get("error")
        if isinstance(error_body, Mapping):
            candidate = error_body.get("message") or error_body.get("detail")
            if isinstance(candidate, str):
                return candidate

    return _safe_response_text(response)


def _safe_response_json(response: object) -> Mapping[str, Any] | None:
    if not hasattr(response, "json"):
        return None
    try:
        payload = response.json()
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _safe_response_text(response: object) -> str | None:
    if not hasattr(response, "text"):
        return None
    try:
        text_value = getattr(response, "text", None)
    except AttributeError:  # pragma: no cover - defensive
        return None
    return text_value if isinstance(text_value, str) else None


def _extract_router_metadata(
    result: object | None,
    default_model: str,
    default_mode: str,
    default_subset: str,
) -> tuple[str, str, str]:
    """Return router metadata from agent result when available.

    Args:
        result: Agent run result object which may expose metadata on itself or on
            ``result.response``.
        default_model: Fallback model name from configuration.
        default_mode: Fallback routing mode from configuration.
        default_subset: Fallback routing subset from configuration.

    Returns:
        Tuple of ``(model_name, router_mode, router_subset)`` combining runtime
        metadata (if present) with configuration defaults.
    """

    metadata = _lookup_router_metadata(result)

    model_name = default_model
    router_mode = default_mode
    router_subset = default_subset

    if metadata:
        model_name = _coalesce_non_empty_str(
            metadata.get("model"), metadata.get("deployedModelName"), fallback=model_name
        )
        router_mode, router_subset = _extract_routing_fields(metadata, router_mode, router_subset)

    return model_name, router_mode, router_subset


def _coerce_mapping(candidate: object) -> Mapping[str, Any] | None:
    if isinstance(candidate, Mapping):
        return candidate
    return None


def _lookup_router_metadata(obj: object | None) -> Mapping[str, Any] | None:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        # Foundry responses expose metadata at the top level.
        candidate = obj.get("metadata") if "metadata" in obj else obj
        return _coerce_mapping(candidate)

    for attr in ("metadata", "extra_metadata", "response_metadata"):
        mapping = _coerce_mapping(getattr(obj, attr, None))
        if mapping is not None:
            return mapping

    response = getattr(obj, "response", None)
    return _lookup_router_metadata(response) if response is not None else None


def _coalesce_non_empty_str(first: object, second: object, *, fallback: str) -> str:
    for candidate in (first, second):
        if isinstance(candidate, str) and candidate:
            return candidate
    return fallback


def _extract_routing_fields(metadata: Mapping[str, Any], default_mode: str, default_subset: str) -> tuple[str, str]:
    router_mode = default_mode
    router_subset = default_subset
    router_info = metadata.get("router") or metadata.get("routing") or metadata.get("route")

    if isinstance(router_info, Mapping):
        mode_value = _coalesce_non_empty_str(
            _mapping_str_value(router_info, "mode"),
            _mapping_str_value(router_info, "policy"),
            fallback="",
        )
        subset_value = _coalesce_non_empty_str(
            _mapping_str_value(router_info, "subset"),
            _mapping_str_value(router_info, "profile"),
            fallback="",
        )
    else:
        mode_value = _mapping_str_value(metadata, "mode") or ""
        subset_value = _mapping_str_value(metadata, "subset") or ""

    if mode_value:
        router_mode = mode_value
    if subset_value:
        router_subset = subset_value
    return router_mode, router_subset


def _mapping_str_value(mapping: Mapping[str, Any], key: str) -> str | None:
    value = mapping.get(key)
    return value if isinstance(value, str) else None


class RouterClassifier:
    """Async classifier that calls the Foundry model router deployment directly."""

    def __init__(
        self,
        *,
        config: AgentConfig | None = None,
        client: object | None = None,
    ) -> None:
        self._config = config or get_agent_config()
        self._credential: DefaultAzureCredential | None = None
        self._client = client or self._create_client()
        self._owns_client = client is None
        self._entered = False

    async def __aenter__(self) -> RouterClassifier:
        self._entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if self._owns_client and hasattr(self._client, "close"):
            close_callable = self._client.close
            result = close_callable()
            if hasattr(result, "__await__"):
                await result
        self._entered = False
        if self._credential is not None and hasattr(self._credential, "close"):
            self._credential.close()
            self._credential = None

    async def classify(self, query: str) -> RouterClassification:
        if not self._entered:
            raise RuntimeError("RouterClassifier must be used inside an async context manager")

        prompt = f"Question: {query}\nReturn JSON response only."
        start = time.perf_counter()

        if _TRACER is None:
            return await self._classify_impl(prompt=prompt, start=start)

        with _TRACER.start_as_current_span("router.classifier.classify") as span:
            _span_set_if_present(span, "router.classifier.deployment", self._config.router_deployment)
            _span_set_if_present(span, "router.classification.prompt", _clip(prompt))
            try:
                result = await self._classify_impl(prompt=prompt, start=start)
            except RouterClassifierError as error:
                _span_set_if_present(span, "router.classification.error", str(error).strip())
                raise

            _span_set_if_present(span, "router.classification.workflow", result.workflow.value)
            _span_set_if_present(span, "router.classification.confidence_score", result.confidence_score)
            _span_set_if_present(span, "router.classification.reason", result.reason)
            _span_set_if_present(span, "router.classification.raw_response", _clip(result.raw_response))
            _span_set_if_present(span, "router.classification.elapsed_seconds", result.elapsed_seconds)
            _span_add_event(
                span,
                "router.classifier.result",
                {
                    "router.classification.workflow": result.workflow.value,
                    "router.classification.confidence_score": result.confidence_score,
                    "router.classification.reason": result.reason,
                },
            )
            return result

    async def _classify_impl(self, *, prompt: str, start: float) -> RouterClassification:
        logger.info(
            "Router classifier invoking chat completions on deployment '%s'",
            self._config.router_deployment,
        )
        try:
            body = await self._call_chat_with_agent_client(prompt)
        except (ChatClientException, RuntimeError, TimeoutError, ValueError) as chat_error:
            self._handle_chat_error(chat_error)

        raw_text = _extract_chat_response_text(body)
        metadata_source: Mapping[str, Any] | None = body

        elapsed = time.perf_counter() - start
        logger.info("Router classifier received response in %.2fs", elapsed)
        workflow, reason, confidence_score = _parse_router_payload(raw_text)

        model_name, router_mode, router_subset = _extract_router_metadata(
            metadata_source,
            default_model=self._config.router_model,
            default_mode="",
            default_subset=self._config.router_subset or "",
        )

        return RouterClassification(
            workflow=workflow,
            raw_response=raw_text,
            reason=reason,
            confidence_score=confidence_score,
            elapsed_seconds=elapsed,
            model_name=model_name,
            router_mode=router_mode,
            router_subset=router_subset,
        )

    def _handle_chat_error(self, chat_error: BaseException) -> NoReturn:
        provider_error = _unwrap_inner_exception(chat_error)
        if _is_version_not_supported(provider_error):
            snippet = _get_error_body_snippet(provider_error)
            if snippet:
                logger.error(
                    "Router chat request rejected due to API version mismatch: %s",
                    snippet,
                )
            else:
                logger.error("Router chat request rejected due to API version mismatch.")
        else:
            self._log_api_error("chat", provider_error)
        self._raise_classifier_error("chat", provider_error)

    def _create_client(self) -> object:
        from agent_framework.openai import OpenAIChatCompletionClient

        base_url = f"{self._config.router_base_url}/openai/v1"
        if self._config.uses_azure_cli:
            self._credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
            scope = "https://cognitiveservices.azure.com/.default"
            if "services.ai.azure.com" in self._config.router_base_url:
                scope = "https://ai.azure.com/.default"
            token_provider = get_bearer_token_provider(self._credential, scope)
            return OpenAIChatCompletionClient(
                model=self._config.router_deployment,
                base_url=base_url,
                api_key=token_provider,
                api_version=self._config.api_version,
            )
        return OpenAIChatCompletionClient(
            model=self._config.router_deployment,
            base_url=base_url,
            api_key=self._config.api_key,
            api_version=self._config.api_version,
        )

    async def _call_chat_with_agent_client(self, prompt: str) -> Mapping[str, Any]:
        from agent_framework import Message

        messages: list[Message] = [
            Message("system", [_ROUTER_SYSTEM_PROMPT]),
            Message("user", [prompt]),
        ]
        options: dict[str, Any] = {
            "model": self._config.router_deployment,
            "temperature": 0.0,
        }

        try:
            async with asyncio.timeout(_CLASSIFIER_TIMEOUT_SECONDS):
                response = await cast(Any, self._client).get_response(messages=messages, options=options)
        except TimeoutError as exc:
            raise TimeoutError("Router chat request timed out") from exc

        response_model = _extract_response_model(response)
        payload: dict[str, Any] = {
            "choices": [
                {
                    "message": {
                        "content": getattr(response, "text", "") or "",
                    }
                }
            ],
            "model": response_model,
        }

        usage_payload = _build_usage_payload(response)
        if usage_payload:
            payload["usage"] = usage_payload

        metadata_payload = _build_metadata_payload(response, response_model=response_model)
        if metadata_payload:
            payload["metadata"] = metadata_payload
        return payload

    def _raise_classifier_error(self, stage: str, error: BaseException) -> NoReturn:
        status = _get_status_code(error)
        reason = _map_http_error_reason(status)
        detail = str(error).strip()
        if detail and detail.lower() not in reason.lower():
            reason = f"{reason}: {detail}"
        raise RouterClassifierError(f"Router classification via {stage} failed: {reason}") from error

    def _log_api_error(self, stage: str, error: BaseException) -> None:
        status = _get_status_code(error)
        body_snippet = _get_error_body_snippet(error)
        if body_snippet:
            logger.error(
                "Router %s request failed (status=%s): %s",
                stage,
                status if status is not None else "unknown",
                body_snippet,
            )
            return

        logger.error(
            "Router %s request failed (status=%s): %s",
            stage,
            status if status is not None else "unknown",
            str(error).strip() or "unknown error",
        )


def _extract_chat_response_text(body: object) -> str:
    first_choice = _first_choice_mapping(body)
    if first_choice is not None:
        content = _extract_choice_content(first_choice)
        if content is not None:
            return content
    return str(body)


def _first_choice_mapping(body: object) -> Mapping[str, Any] | None:
    if not isinstance(body, Mapping):
        return None
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    return first if isinstance(first, Mapping) else None


def _extract_choice_content(choice: Mapping[str, Any]) -> str | None:
    message = choice.get("message")
    if not isinstance(message, Mapping):
        return None
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    return None


def _unwrap_inner_exception(error: BaseException) -> BaseException:
    """Return the deepest provider exception exposed by wrapper clients."""

    current: BaseException = error
    while True:
        candidate = getattr(current, "inner_exception", None)
        if not isinstance(candidate, BaseException):
            return current
        current = candidate


def _get_status_code(error: BaseException) -> int | None:
    status = getattr(error, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(error, "response", None)
    if response is not None:
        response_status = getattr(response, "status_code", None)
        if isinstance(response_status, int):
            return response_status
    return None


def _get_error_body_snippet(error: BaseException) -> str:
    response = getattr(error, "response", None)
    if response is None:
        return ""

    text_value = _safe_response_text(response)
    if text_value is None:
        payload = _safe_response_json(response)
        text_value = json.dumps(payload)[:200] if payload is not None else None
    if text_value is None:
        text_value = _safe_response_body_text(response)
    if text_value is None:
        return ""
    return text_value.strip().replace("\n", " ")[:200]


def _safe_response_body_text(response: object) -> str | None:
    body = getattr(response, "body", None)
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="ignore")
    if isinstance(body, str):
        return body
    return None


def _parse_router_payload(raw_text: str) -> tuple[WorkflowType, str | None, int | None]:
    workflow = WorkflowType.SEQUENTIAL
    reason: str | None = None
    confidence_score: int | None = None
    payload = _strip_fences(raw_text)

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:  # pragma: no cover - tolerate malformed JSON
        logger.debug("Router classifier returned unparseable payload: %s", raw_text)
        return workflow, reason, confidence_score

    if isinstance(parsed, Mapping):
        workflow = _parse_workflow(parsed.get("workflow"))
        reason = _normalize_optional_reason(parsed.get("reason"))
        confidence_score = normalize_confidence_score(parsed.get("confidence_score"))
        if confidence_score is None:
            confidence_score = normalize_confidence_score(parsed.get("confidence"))

    return workflow, reason, confidence_score


def _normalize_optional_reason(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _extract_response_model(response: object) -> str:
    response_model = getattr(response, "model", None)
    if isinstance(response_model, str):
        return response_model
    return ""


def _build_usage_payload(response: object) -> dict[str, int] | None:
    usage = getattr(response, "usage_details", None)
    if not isinstance(usage, Mapping):
        return None

    token_mapping = {
        "prompt_tokens": usage.get("input_token_count"),
        "completion_tokens": usage.get("output_token_count"),
        "total_tokens": usage.get("total_token_count"),
    }
    normalized = {key: value for key, value in token_mapping.items() if isinstance(value, int)}
    return normalized or None


def _build_metadata_payload(response: object, *, response_model: str) -> dict[str, Any] | None:
    metadata_payload: dict[str, Any] = {}
    additional_properties = getattr(response, "additional_properties", None)
    if isinstance(additional_properties, Mapping):
        metadata_payload.update({key: value for key, value in additional_properties.items() if value is not None})

    if response_model:
        metadata_payload.setdefault("model", response_model)

    return metadata_payload or None


def _clip(value: str, limit: int = 800) -> str:
    """Return a bounded string for span attributes/events."""

    if len(value) <= limit:
        return value
    return f"{value[: max(0, limit - 3)]}..."


def _span_set_if_present(span: object | None, key: str, value: object | None) -> None:
    """Set span attribute when a span exists and value is representable."""

    if span is None or value is None:
        return
    typed_span = cast(Any, span)

    if isinstance(value, (str, bool, int, float)):
        typed_span.set_attribute(key, value)
        return

    typed_span.set_attribute(key, _clip(str(value)))
