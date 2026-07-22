"""Unit tests for workflows/concurrent.py — ParallelSearchWorkflow.run().

Agents are replaced with mocks whose ``.run()`` returns a canned response
object with a ``.text`` attribute, so these tests exercise the parallel
orchestration logic (asyncio.gather, step recording, synthesis) without
any real Azure OpenAI calls.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from workflows.base import WorkflowType
from workflows.concurrent import ParallelSearchWorkflow, _create_parallel_agents


def _agent_stub(text: str) -> MagicMock:
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(text=text))
    return agent


def _connected_workflow(
    entity_text: str = "entity findings",
    themes_text: str = "theme findings",
    synthesis_text: str = "final synthesis",
) -> ParallelSearchWorkflow:
    workflow = ParallelSearchWorkflow()
    workflow._entity_searcher = _agent_stub(entity_text)
    workflow._themes_searcher = _agent_stub(themes_text)
    workflow._answer_synthesizer = _agent_stub(synthesis_text)
    return workflow


class TestParallelSearchWorkflowRun:
    async def test_raises_if_not_connected(self):
        workflow = ParallelSearchWorkflow()

        with pytest.raises(RuntimeError, match="not connected"):
            await workflow.run("query")

    async def test_happy_path_returns_synthesizer_output_as_answer(self):
        workflow = _connected_workflow(synthesis_text="merged answer")

        result = await workflow.run("What are the main projects and who leads them?")

        assert result.answer == "merged answer"
        assert result.workflow_type == WorkflowType.CONCURRENT
        assert result.query == "What are the main projects and who leads them?"

    async def test_both_searchers_are_invoked(self):
        workflow = _connected_workflow()

        await workflow.run("query")

        workflow._entity_searcher.run.assert_awaited_once()
        workflow._themes_searcher.run.assert_awaited_once()
        workflow._answer_synthesizer.run.assert_awaited_once()

    async def test_records_entity_and_themes_steps_with_parallel_metadata(self):
        workflow = _connected_workflow(entity_text="entity findings", themes_text="theme findings")

        result = await workflow.run("query")

        entity_step, themes_step, synthesis_step = result.steps
        assert entity_step.agent_name == "EntitySearcher"
        assert entity_step.output == "entity findings"
        assert entity_step.metadata == {"parallel": True, "search_type": "local"}

        assert themes_step.agent_name == "ThemesSearcher"
        assert themes_step.output == "theme findings"
        assert themes_step.metadata == {"parallel": True, "search_type": "global"}

        assert synthesis_step.agent_name == "AnswerSynthesizer"

    async def test_synthesis_prompt_includes_both_findings(self):
        workflow = _connected_workflow(entity_text="entity findings XYZ", themes_text="theme findings ABC")

        await workflow.run("query")

        prompt = workflow._answer_synthesizer.run.await_args.args[0]
        assert "entity findings XYZ" in prompt
        assert "theme findings ABC" in prompt


class TestCreateParallelAgents:
    def test_creates_three_agents_with_correct_names(self, monkeypatch):
        mock_agent_cls = MagicMock()
        monkeypatch.setattr("agent_framework.Agent", mock_agent_cls)
        monkeypatch.setattr("workflows.concurrent.create_azure_client", MagicMock(return_value="client"))
        monkeypatch.setattr("workflows.concurrent.create_mcp_tool", lambda url: MagicMock())

        _create_parallel_agents()

        names = [call.kwargs["name"] for call in mock_agent_cls.call_args_list]
        assert names == ["entity_searcher", "themes_searcher", "answer_synthesizer"]

    def test_entity_and_themes_tools_get_distinct_prefixes(self, monkeypatch):
        created_tools: list[MagicMock] = []

        def _fake_create_mcp_tool(url):
            tool = MagicMock()
            created_tools.append(tool)
            return tool

        monkeypatch.setattr("agent_framework.Agent", MagicMock())
        monkeypatch.setattr("workflows.concurrent.create_azure_client", MagicMock(return_value="client"))
        monkeypatch.setattr("workflows.concurrent.create_mcp_tool", _fake_create_mcp_tool)

        _create_parallel_agents()

        assert created_tools[0].tool_name_prefix == "entity"
        assert created_tools[1].tool_name_prefix == "themes"

    def test_answer_synthesizer_has_no_tools(self, monkeypatch):
        mock_agent_cls = MagicMock()
        monkeypatch.setattr("agent_framework.Agent", mock_agent_cls)
        monkeypatch.setattr("workflows.concurrent.create_azure_client", MagicMock(return_value="client"))
        monkeypatch.setattr("workflows.concurrent.create_mcp_tool", lambda url: MagicMock())

        _create_parallel_agents()

        synthesizer_call = mock_agent_cls.call_args_list[2]
        assert synthesizer_call.kwargs["tools"] == []


def _mock_context_agent() -> MagicMock:
    agent = MagicMock()
    agent.__aenter__ = AsyncMock(return_value=agent)
    agent.__aexit__ = AsyncMock(return_value=False)
    return agent


class TestParallelSearchWorkflowLifecycle:
    async def test_aenter_creates_agents_and_connects_both_searchers(self, monkeypatch):
        entity_agent = _mock_context_agent()
        themes_agent = _mock_context_agent()
        synthesizer = MagicMock()
        monkeypatch.setattr(
            "workflows.concurrent._create_parallel_agents",
            lambda mcp_url=None: (entity_agent, themes_agent, synthesizer),
        )

        workflow = ParallelSearchWorkflow()
        result = await workflow.__aenter__()

        entity_agent.__aenter__.assert_awaited_once()
        themes_agent.__aenter__.assert_awaited_once()
        assert result is workflow
        assert workflow._answer_synthesizer is synthesizer

    async def test_aexit_closes_both_searcher_connections(self, monkeypatch):
        entity_agent = _mock_context_agent()
        themes_agent = _mock_context_agent()
        monkeypatch.setattr(
            "workflows.concurrent._create_parallel_agents",
            lambda mcp_url=None: (entity_agent, themes_agent, MagicMock()),
        )

        workflow = ParallelSearchWorkflow()
        await workflow.__aenter__()
        await workflow.__aexit__(None, None, None)

        entity_agent.__aexit__.assert_awaited_once()
        themes_agent.__aexit__.assert_awaited_once()

    async def test_aexit_without_prior_aenter_is_a_no_op(self):
        workflow = ParallelSearchWorkflow()
        await workflow.__aexit__(None, None, None)
