"""Unit tests for workflows/handoff.py — _parse_route and ExpertHandoffWorkflow.run().

Agents are replaced with mocks whose ``.run()`` returns a canned response
object with a ``.text`` attribute, so these tests exercise the routing and
orchestration logic without any real Azure OpenAI calls.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from workflows.base import WorkflowType
from workflows.handoff import (
    ExpertHandoffWorkflow,
    _create_router_and_experts,
    _parse_route,
    _parse_route_classification,
)


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


class TestParseRouteClassification:
    def test_parses_structured_json_output(self):
        result = _parse_route_classification('{"route": "themes", "confidence_score": 84, "reason": "Broad strategy"}')

        assert result.decision == "themes"
        assert result.confidence_score == 84
        assert result.reason == "Broad strategy"

    def test_falls_back_to_legacy_route_word(self):
        result = _parse_route_classification("entity")

        assert result.decision == "entity"
        assert result.confidence_score is None
        assert result.reason is None


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

    async def test_structured_route_metadata_is_recorded(self):
        workflow = _connected_workflow(
            router_text='{"route": "both", "confidence_score": 81, "reason": "Need both detail and themes"}',
        )

        result = await workflow.run("query")

        router_step = result.steps[0]
        assert router_step.metadata["route"] == "both"
        assert router_step.metadata["route_confidence_score"] == 81
        assert router_step.metadata["route_reason"] == "Need both detail and themes"

    async def test_router_normalizes_dict_payload_input(self):
        workflow = _connected_workflow(router_text="entity", entity_text="entity answer")

        result = await workflow.run({"input": "Who leads Project Alpha?"})

        assert result.query == "Who leads Project Alpha?"
        router_prompt = workflow._router.run.await_args.args[0]
        assert "{'input':" not in router_prompt
        assert "Who leads Project Alpha?" in router_prompt


class TestCreateRouterAndExperts:
    def test_creates_three_agents_with_correct_names(self, monkeypatch):
        mock_agent_cls = MagicMock()
        monkeypatch.setattr("agent_framework.Agent", mock_agent_cls)
        monkeypatch.setattr("workflows.handoff.create_azure_client", MagicMock(return_value="client"))

        _create_router_and_experts(MagicMock())

        names = [call.kwargs["name"] for call in mock_agent_cls.call_args_list]
        assert names == ["router", "entity_expert", "themes_expert"]

    def test_router_has_no_tools_experts_share_the_mcp_tool(self, monkeypatch):
        mock_agent_cls = MagicMock()
        monkeypatch.setattr("agent_framework.Agent", mock_agent_cls)
        monkeypatch.setattr("workflows.handoff.create_azure_client", MagicMock(return_value="client"))
        mcp_tool = MagicMock()

        _create_router_and_experts(mcp_tool)

        router_call, entity_call, themes_call = mock_agent_cls.call_args_list
        assert router_call.kwargs["tools"] == []
        assert entity_call.kwargs["tools"] == [mcp_tool]
        assert themes_call.kwargs["tools"] == [mcp_tool]


class TestExpertHandoffWorkflowCreateAgents:
    def test_delegates_to_create_router_and_experts(self, monkeypatch):
        stub_agents = (MagicMock(), MagicMock(), MagicMock())
        monkeypatch.setattr("workflows.handoff._create_router_and_experts", lambda mcp_tool: stub_agents)

        workflow = ExpertHandoffWorkflow()
        workflow._create_agents(MagicMock())

        assert workflow._router is stub_agents[0]
        assert workflow._entity_expert is stub_agents[1]
        assert workflow._themes_expert is stub_agents[2]
