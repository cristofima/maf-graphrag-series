"""Unit tests for workflows/sequential.py — ResearchPipelineWorkflow.run().

Agents are replaced with mocks whose ``.run()`` returns a canned response
object with a ``.text`` attribute, so these tests exercise the pipeline's
orchestration logic (prompt building, step recording, timing) without any
real Azure OpenAI calls.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from maf_graphrag.workflows.base import WorkflowType
from maf_graphrag.workflows.sequential import ResearchPipelineWorkflow, _create_sequential_agents


def _agent_stub(text: str) -> MagicMock:
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(text=text))
    return agent


def _connected_workflow(
    analyzer_text: str = "plan",
    searcher_text: str = "findings",
    writer_text: str = "report",
) -> ResearchPipelineWorkflow:
    workflow = ResearchPipelineWorkflow()
    workflow._mcp_tool = MagicMock()
    workflow._query_analyzer = _agent_stub(analyzer_text)
    workflow._knowledge_searcher = _agent_stub(searcher_text)
    workflow._report_writer = _agent_stub(writer_text)
    return workflow


class TestResearchPipelineWorkflowRun:
    async def test_raises_if_not_connected(self):
        workflow = ResearchPipelineWorkflow()

        with pytest.raises(RuntimeError, match="not connected"):
            await workflow.run("query")

    async def test_happy_path_returns_report_writer_output_as_answer(self):
        workflow = _connected_workflow(writer_text="final report")

        result = await workflow.run("What are the key projects?")

        assert result.answer == "final report"
        assert result.workflow_type == WorkflowType.SEQUENTIAL
        assert result.query == "What are the key projects?"

    async def test_records_all_three_steps_in_order(self):
        workflow = _connected_workflow()

        result = await workflow.run("query")

        assert [step.agent_name for step in result.steps] == [
            "QueryAnalyzer",
            "KnowledgeSearcher",
            "ReportWriter",
        ]
        assert [step.output for step in result.steps] == ["plan", "findings", "report"]

    async def test_research_plan_is_passed_to_knowledge_searcher(self):
        workflow = _connected_workflow(analyzer_text="structured plan XYZ")

        await workflow.run("query")

        prompt = workflow._knowledge_searcher.run.await_args.args[0]
        assert "structured plan XYZ" in prompt

    async def test_findings_are_passed_to_report_writer(self):
        workflow = _connected_workflow(searcher_text="raw findings ABC")

        await workflow.run("query")

        prompt = workflow._report_writer.run.await_args.args[0]
        assert "raw findings ABC" in prompt


class TestCreateSequentialAgents:
    def test_creates_three_agents_with_correct_names(self, monkeypatch):
        mock_agent_cls = MagicMock()
        monkeypatch.setattr("agent_framework.Agent", mock_agent_cls)
        monkeypatch.setattr("maf_graphrag.workflows.sequential.create_azure_client", MagicMock(return_value="client"))

        _create_sequential_agents(MagicMock())

        names = [call.kwargs["name"] for call in mock_agent_cls.call_args_list]
        assert names == ["query_analyzer", "knowledge_searcher", "report_writer"]

    def test_only_knowledge_searcher_receives_the_mcp_tool(self, monkeypatch):
        mock_agent_cls = MagicMock()
        monkeypatch.setattr("agent_framework.Agent", mock_agent_cls)
        monkeypatch.setattr("maf_graphrag.workflows.sequential.create_azure_client", MagicMock(return_value="client"))
        mcp_tool = MagicMock()

        _create_sequential_agents(mcp_tool)

        analyzer_call, searcher_call, writer_call = mock_agent_cls.call_args_list
        assert analyzer_call.kwargs["tools"] == []
        assert searcher_call.kwargs["tools"] == [mcp_tool]
        assert writer_call.kwargs["tools"] == []


class TestResearchPipelineWorkflowCreateAgents:
    def test_delegates_to_create_sequential_agents(self, monkeypatch):
        stub_agents = (MagicMock(), MagicMock(), MagicMock())
        monkeypatch.setattr("maf_graphrag.workflows.sequential._create_sequential_agents", lambda mcp_tool: stub_agents)

        workflow = ResearchPipelineWorkflow()
        workflow._create_agents(MagicMock())

        assert workflow._query_analyzer is stub_agents[0]
        assert workflow._knowledge_searcher is stub_agents[1]
        assert workflow._report_writer is stub_agents[2]
