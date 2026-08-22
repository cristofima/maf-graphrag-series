"""Tests for the PR1 router-agent adapter surface."""

from __future__ import annotations

from typing import Any

import pytest
from agent_framework import InMemoryCheckpointStorage

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
        assert kwargs["session_telemetry"] == {"session_id": "session-1", "turn_index": 1}
        assert isinstance(kwargs["checkpoint_storage"], InMemoryCheckpointStorage)
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


@pytest.mark.asyncio
async def test_router_agent_adapter_delegates_without_changing_router_contract() -> None:
    adapter = RouterWorkflowAgentAdapter(
        workflow_factory=lambda _mcp_url: _StubRouterWorkflow(),
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
