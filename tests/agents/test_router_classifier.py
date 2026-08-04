"""Tests for the Foundry-backed RouterClassifier."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest
from agent_framework.exceptions import ChatClientException

from agents.config import AgentConfig
from agents.router_classifier import RouterClassifier, RouterClassifierError
from workflows.base import WorkflowType


class _ErrorResponse:
    def __init__(self, status: int, body: Mapping[str, Any]) -> None:
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)

    def json(self) -> Mapping[str, Any]:
        return self._body


class _RouterAPIError(Exception):
    def __init__(self, status: int, body: Mapping[str, Any]) -> None:
        message = body.get("error", {}).get("message") if isinstance(body.get("error"), Mapping) else body.get("error")
        super().__init__(message or "router error")
        self.status_code = status
        self.response = _ErrorResponse(status, body)


class _AFClientError(ChatClientException):
    def __init__(self, inner_exception: Exception) -> None:
        super().__init__(str(inner_exception), inner_exception=inner_exception)
        self.inner_exception = inner_exception


class _StubAFResponse:
    def __init__(
        self,
        *,
        text: str,
        model: str,
        usage_details: Mapping[str, int] | None = None,
        additional_properties: Mapping[str, Any] | None = None,
    ) -> None:
        self.text = text
        self.model = model
        self.usage_details = usage_details or {}
        self.additional_properties = additional_properties or {}


class _StubAFClient:
    def __init__(self, responses: list[_StubAFResponse | Exception]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    async def get_response(self, **kwargs: Any) -> _StubAFResponse:
        self.calls.append(kwargs)
        if not self._responses:
            raise RuntimeError("unexpected get_response call")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def foundry_config() -> AgentConfig:
    return AgentConfig(
        azure_endpoint="https://stub.openai.azure.com",
        deployment_name="knowledge-captain",
        router_deployment="router-deployment",
        api_key="stub-key",
        api_version="2025-11-18",
        mcp_server_url="http://127.0.0.1:8011/mcp",
        router_subset="",
    )


class TestRouterClassifier:
    async def test_classify_parses_router_response(self, foundry_config: AgentConfig) -> None:
        af_response = _StubAFResponse(
            text='{"workflow": "handoff", "confidence_score": 92, "reason": "Entity experts answer faster."}',
            model="router-deployment",
            additional_properties={"router": {"mode": "balanced"}},
        )
        client = _StubAFClient([af_response])

        classifier = RouterClassifier(config=foundry_config, client=client)
        async with classifier:
            classification = await classifier.classify("Who leads Project Alpha?")

        assert classification.workflow is WorkflowType.HANDOFF
        assert classification.confidence_score == 92
        assert classification.reason == "Entity experts answer faster."
        assert classification.model_name == "router-deployment"
        assert classification.router_mode == "balanced"
        assert classification.router_subset == ""
        assert len(client.calls) == 1
        call_args = client.calls[0]
        assert call_args["options"]["model"] == "router-deployment"
        assert call_args["options"]["temperature"] == 0.0

    async def test_metadata_overrides_defaults(self, foundry_config: AgentConfig) -> None:
        af_response = _StubAFResponse(
            text='{"workflow": "sequential", "confidence_score": 75}',
            model="router-prod",
            additional_properties={"router": {"mode": "production", "subset": "tier-a"}},
        )
        client = _StubAFClient([af_response])

        classifier = RouterClassifier(config=foundry_config, client=client)
        async with classifier:
            classification = await classifier.classify("Give me a full research report")

        assert classification.workflow is WorkflowType.SEQUENTIAL
        assert classification.confidence_score == 75
        assert classification.model_name == "router-prod"
        assert classification.router_mode == "production"
        assert classification.router_subset == "tier-a"

    async def test_classic_endpoint_still_sends_router_model(self, foundry_config: AgentConfig) -> None:
        legacy_config = foundry_config.model_copy(
            update={
                "azure_endpoint": "https://legacy.openai.azure.com",
                "router_endpoint": "https://legacy.openai.azure.com",
            }
        )
        af_response = _StubAFResponse(text='{"workflow": "handoff"}', model="router-deployment")
        client = _StubAFClient([af_response])
        classifier = RouterClassifier(config=legacy_config, client=client)

        async with classifier:
            await classifier.classify("Who leads Project Alpha?")

        assert client.calls[0]["options"]["model"] == "router-deployment"

    async def test_classify_parses_out_of_context_label(self, foundry_config: AgentConfig) -> None:
        af_response = _StubAFResponse(
            text='{"workflow": "out_of_context", "confidence_score": 97, "reason": "Greeting and meta chat request."}',
            model="router-deployment",
        )
        client = _StubAFClient([af_response])
        classifier = RouterClassifier(config=foundry_config, client=client)

        async with classifier:
            classification = await classifier.classify("Hello, who are you?")

        assert classification.workflow is WorkflowType.SEQUENTIAL
        assert classification.workflow_label == "out_of_context"
        assert classification.confidence_score == 97

    async def test_classify_with_agent_framework_client(self, foundry_config: AgentConfig) -> None:
        af_response = _StubAFResponse(
            text='{"workflow": "concurrent", "confidence_score": 88, "reason": "Need parallel entity and theme signals."}',
            model="router-deployment",
            usage_details={
                "input_token_count": 31,
                "output_token_count": 17,
                "total_token_count": 48,
            },
            additional_properties={
                "router": {"mode": "balanced", "subset": "tier-a"},
            },
        )
        client = _StubAFClient([af_response])
        classifier = RouterClassifier(config=foundry_config, client=client)

        async with classifier:
            classification = await classifier.classify("Compare initiatives and owners")

        assert classification.workflow is WorkflowType.CONCURRENT
        assert classification.confidence_score == 88
        assert classification.reason == "Need parallel entity and theme signals."
        assert classification.model_name == "router-deployment"
        assert classification.router_mode == "balanced"
        assert classification.router_subset == "tier-a"
        assert len(client.calls) == 1
        assert client.calls[0]["options"]["model"] == "router-deployment"

    async def test_raises_error_when_router_unavailable(self, foundry_config: AgentConfig) -> None:
        failing_body = {"error": {"message": "router offline"}}
        client = _StubAFClient([_AFClientError(_RouterAPIError(500, failing_body))])
        classifier = RouterClassifier(config=foundry_config, client=client)

        async with classifier:
            with pytest.raises(
                RouterClassifierError, match=r"Router classification via chat failed: router HTTP error 500"
            ):
                await classifier.classify("Who leads Project Alpha?")

    async def test_raises_error_when_router_reports_version_issue(self, foundry_config: AgentConfig) -> None:
        version_body = {"error": {"message": "API version not supported"}}
        client = _StubAFClient([_AFClientError(_RouterAPIError(400, version_body))])
        classifier = RouterClassifier(config=foundry_config, client=client)

        async with classifier:
            with pytest.raises(RouterClassifierError, match=r"API version not supported"):
                await classifier.classify("Who leads Project Alpha?")

        assert len(client.calls) == 1
