"""Unit tests for workflows/base.py — WorkflowStep, WorkflowResult, WorkflowType."""

import pytest

from workflows.base import WorkflowResult, WorkflowStep, WorkflowType


class TestWorkflowStep:
    def test_default_values(self):
        step = WorkflowStep(
            agent_name="TestAgent",
            input_summary="test input",
            output="test output",
        )
        assert step.agent_name == "TestAgent"
        assert step.input_summary == "test input"
        assert step.output == "test output"
        assert step.elapsed_seconds == 0.0
        assert step.metadata == {}

    def test_with_timing_and_metadata(self):
        step = WorkflowStep(
            agent_name="Searcher",
            input_summary="search query",
            output="results",
            elapsed_seconds=1.5,
            metadata={"search_type": "local"},
        )
        assert step.elapsed_seconds == 1.5
        assert step.metadata["search_type"] == "local"

    def test_metadata_is_not_shared(self):
        """Each step should have an independent metadata dict."""
        step1 = WorkflowStep("A", "in", "out")
        step2 = WorkflowStep("B", "in", "out")
        step1.metadata["key"] = "value"
        assert "key" not in step2.metadata


class TestWorkflowResult:
    def test_basic_construction(self):
        result = WorkflowResult(
            answer="final answer",
            workflow_type=WorkflowType.SEQUENTIAL,
        )
        assert result.answer == "final answer"
        assert result.workflow_type == WorkflowType.SEQUENTIAL
        assert result.steps == []
        assert result.total_elapsed_seconds == 0.0
        assert result.query == ""

    def test_with_steps(self):
        steps = [
            WorkflowStep("Agent1", "input1", "output1", elapsed_seconds=0.5),
            WorkflowStep("Agent2", "input2", "output2", elapsed_seconds=1.0),
        ]
        result = WorkflowResult(
            answer="answer",
            workflow_type=WorkflowType.CONCURRENT,
            steps=steps,
            total_elapsed_seconds=1.5,
            query="test query",
        )
        assert len(result.steps) == 2
        assert result.total_elapsed_seconds == 1.5
        assert result.query == "test query"

    def test_step_summary_format(self):
        steps = [
            WorkflowStep("QueryAnalyzer", "Decompose query", "plan", elapsed_seconds=0.3),
            WorkflowStep("Searcher", "Execute search", "results", elapsed_seconds=0.7),
        ]
        result = WorkflowResult(
            answer="done",
            workflow_type=WorkflowType.SEQUENTIAL,
            steps=steps,
            total_elapsed_seconds=1.0,
        )
        summary = result.step_summary()
        assert "sequential" in summary
        assert "1.0s" in summary
        assert "QueryAnalyzer" in summary
        assert "Searcher" in summary
        assert "Step 1" in summary
        assert "Step 2" in summary

    def test_steps_list_not_shared(self):
        """Each WorkflowResult should have its own steps list."""
        r1 = WorkflowResult(answer="a", workflow_type=WorkflowType.HANDOFF)
        r2 = WorkflowResult(answer="b", workflow_type=WorkflowType.HANDOFF)
        r1.steps.append(WorkflowStep("X", "in", "out"))
        assert len(r2.steps) == 0


class TestWorkflowType:
    def test_values(self):
        assert WorkflowType.SEQUENTIAL == "sequential"
        assert WorkflowType.CONCURRENT == "concurrent"
        assert WorkflowType.HANDOFF == "handoff"

    def test_is_str_enum(self):
        assert isinstance(WorkflowType.SEQUENTIAL, str)
