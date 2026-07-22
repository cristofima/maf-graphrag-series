"""Unit tests for workflows/sequential.py — ResearchPipelineWorkflow.run().

Agents are replaced with mocks whose ``.run()`` returns a canned response
object with a ``.text`` attribute, so these tests exercise the pipeline's
orchestration logic (prompt building, step recording, timing) without any
real Azure OpenAI calls.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from workflows.base import WorkflowType
from workflows.sequential import ResearchPipelineWorkflow


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
