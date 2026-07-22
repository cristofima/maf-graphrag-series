"""Unit tests for workflows/handoff.py — _parse_route and ExpertHandoffWorkflow.run().

Agents are replaced with mocks whose ``.run()`` returns a canned response
object with a ``.text`` attribute, so these tests exercise the routing and
orchestration logic without any real Azure OpenAI calls.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from workflows.base import WorkflowType
from workflows.handoff import ExpertHandoffWorkflow, _parse_route


class TestParseRoute:
    def test_entity_only(self):
        assert _parse_route("entity") == "entity"

    def test_themes_only(self):
        assert _parse_route("Themes") == "themes"

    def test_both_explicit(self):
        assert _parse_route("both") == "both"

    def test_trailing_punctuation_is_stripped(self):
        assert _parse_route("entity.") == "entity"

    def test_ambiguous_mix_defaults_to_both(self):
        assert _parse_route("entity and themes") == "both"

    def test_unrecognized_output_defaults_to_both(self):
        assert _parse_route("I'm not sure") == "both"


def _agent_stub(text: str) -> MagicMock:
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(text=text))
    return agent


def _connected_workflow(
    router_text: str = "entity",
    entity_text: str = "entity answer",
    themes_text: str = "themes answer",
) -> ExpertHandoffWorkflow:
    workflow = ExpertHandoffWorkflow()
    workflow._mcp_tool = MagicMock()
    workflow._router = _agent_stub(router_text)
    workflow._entity_expert = _agent_stub(entity_text)
    workflow._themes_expert = _agent_stub(themes_text)
    return workflow


class TestExpertHandoffWorkflowRun:
    async def test_raises_if_not_connected(self):
        workflow = ExpertHandoffWorkflow()

        with pytest.raises(RuntimeError, match="not connected"):
            await workflow.run("query")

    async def test_entity_route_only_calls_entity_expert(self):
        workflow = _connected_workflow(router_text="entity", entity_text="entity answer")

        result = await workflow.run("Who leads Project Alpha?")

        assert result.answer == "entity answer"
        assert result.workflow_type == WorkflowType.HANDOFF
        workflow._entity_expert.run.assert_awaited_once()
        workflow._themes_expert.run.assert_not_called()

    async def test_themes_route_only_calls_themes_expert(self):
        workflow = _connected_workflow(router_text="themes", themes_text="themes answer")

        result = await workflow.run("What are the strategic initiatives?")

        assert result.answer == "themes answer"
        workflow._themes_expert.run.assert_awaited_once()
        workflow._entity_expert.run.assert_not_called()

    async def test_both_route_calls_both_experts_and_combines_answers(self):
        workflow = _connected_workflow(router_text="both", entity_text="entity answer", themes_text="themes answer")

        result = await workflow.run("Describe leadership and strategy")

        workflow._entity_expert.run.assert_awaited_once()
        workflow._themes_expert.run.assert_awaited_once()
        assert "Entity Details" in result.answer
        assert "entity answer" in result.answer
        assert "Organizational Themes" in result.answer
        assert "themes answer" in result.answer

    async def test_router_step_is_recorded_first_with_route_metadata(self):
        workflow = _connected_workflow(router_text="entity")

        result = await workflow.run("query")

        router_step = result.steps[0]
        assert router_step.agent_name == "Router"
        assert router_step.metadata == {"route": "entity"}
