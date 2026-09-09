"""Unit tests for evaluation/scripts/generate_eval_data.py — generate_eval_data().

RouterWorkflowAgentAdapter and file I/O are fully mocked; no credentials needed.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from maf_graphrag.evaluation.scripts.generate_eval_data import generate_eval_data

STUB_CONVERSATION = [
    {
        "role": "user",
        "contents": [
            {"type": "text", "text": "Who leads Project Alpha?"},
        ],
    },
    {
        "role": "assistant",
        "contents": [
            {"type": "text", "text": "Dr. Harrison leads it"},
        ],
    },
]

STUB_AGENT_TURNS = [{"executor_id": "router", "conversation": STUB_CONVERSATION}]
STUB_TOOL_DEFINITIONS = [{"name": "search", "description": "", "parameters": {}}]
STUB_TOOL_CALLS = [
    {
        "executor_id": "router",
        "tool_call_id": "call-1",
        "name": "search",
        "arguments": {"query": "Project Alpha"},
    }
]


def _stub_adapter(answer: str = "stub answer") -> object:
    result = SimpleNamespace(
        answer=answer,
        raw_result=None,
        workflow_graph=None,
        steps=[],
        workflow_type=SimpleNamespace(value="sequential"),
        query="",
    )
    adapter = SimpleNamespace()
    adapter.run = AsyncMock(return_value=result)
    return adapter


def _write_golden_questions(path, cases: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(case) + "\n")


class TestGenerateEvalDataValidation:
    async def test_raises_when_input_file_is_missing(self, tmp_path):
        missing_input = tmp_path / "golden_questions.jsonl"
        output_path = tmp_path / "eval_data.jsonl"

        with pytest.raises(FileNotFoundError, match="Golden questions file not found"):
            await generate_eval_data(input_path=missing_input, output_path=output_path)


class TestGenerateEvalDataHappyPath:
    async def test_writes_one_record_per_test_case(self, tmp_path):
        input_path = tmp_path / "golden_questions.jsonl"
        output_path = tmp_path / "eval_data.jsonl"
        _write_golden_questions(
            input_path,
            [
                {"query": "Who leads Project Alpha?", "ground_truth": "Dr. Harrison"},
                {"query": "What are the main themes?"},
            ],
        )

        with (
            patch(
                "maf_graphrag.workflows.router_agent.RouterWorkflowAgentAdapter", return_value=_stub_adapter("answer")
            ),
            patch(
                "maf_graphrag.evaluation.scripts.generate_eval_data._extract_agent_turn_payloads",
                return_value=(STUB_AGENT_TURNS, STUB_TOOL_DEFINITIONS, STUB_TOOL_CALLS),
            ),
        ):
            count = await generate_eval_data(input_path=input_path, output_path=output_path)

        assert count == 2
        lines = output_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    async def test_record_contains_query_response_and_ground_truth(self, tmp_path):
        input_path = tmp_path / "golden_questions.jsonl"
        output_path = tmp_path / "eval_data.jsonl"
        _write_golden_questions(input_path, [{"query": "Who leads Project Alpha?", "ground_truth": "Dr. Harrison"}])

        with (
            patch(
                "maf_graphrag.workflows.router_agent.RouterWorkflowAgentAdapter",
                return_value=_stub_adapter("Dr. Harrison leads it"),
            ),
            patch(
                "maf_graphrag.evaluation.scripts.generate_eval_data._extract_agent_turn_payloads",
                return_value=(STUB_AGENT_TURNS, STUB_TOOL_DEFINITIONS, STUB_TOOL_CALLS),
            ),
        ):
            await generate_eval_data(input_path=input_path, output_path=output_path)

        record = json.loads(output_path.read_text(encoding="utf-8").strip())
        assert record["query"] == "Who leads Project Alpha?"
        assert record["ground_truth"] == "Dr. Harrison"
        assert record["response_text"] == "Dr. Harrison leads it"
        assert record["conversation"] == STUB_CONVERSATION
        assert record["response"] == "Dr. Harrison leads it"
        assert record["agent_turns"] == STUB_AGENT_TURNS
        assert record["tool_definitions"] == STUB_TOOL_DEFINITIONS
        assert record["tool_calls"] == STUB_TOOL_CALLS
        assert record["route_metadata"]["routed_workflow"] == "sequential"

    async def test_missing_ground_truth_defaults_to_empty_string(self, tmp_path):
        input_path = tmp_path / "golden_questions.jsonl"
        output_path = tmp_path / "eval_data.jsonl"
        _write_golden_questions(input_path, [{"query": "What are the main themes?"}])

        with (
            patch("maf_graphrag.workflows.router_agent.RouterWorkflowAgentAdapter", return_value=_stub_adapter()),
            patch(
                "maf_graphrag.evaluation.scripts.generate_eval_data._extract_agent_turn_payloads",
                return_value=(STUB_AGENT_TURNS, STUB_TOOL_DEFINITIONS, STUB_TOOL_CALLS),
            ),
        ):
            await generate_eval_data(input_path=input_path, output_path=output_path)

        record = json.loads(output_path.read_text(encoding="utf-8").strip())
        assert record["ground_truth"] == ""

    async def test_blank_lines_in_input_are_skipped(self, tmp_path):
        input_path = tmp_path / "golden_questions.jsonl"
        output_path = tmp_path / "eval_data.jsonl"
        input_path.write_text(
            '{"query": "Who leads Project Alpha?"}\n\n   \n{"query": "What are the main themes?"}\n',
            encoding="utf-8",
        )

        with (
            patch("maf_graphrag.workflows.router_agent.RouterWorkflowAgentAdapter", return_value=_stub_adapter()),
            patch(
                "maf_graphrag.evaluation.scripts.generate_eval_data._extract_agent_turn_payloads",
                return_value=(STUB_AGENT_TURNS, STUB_TOOL_DEFINITIONS, STUB_TOOL_CALLS),
            ),
        ):
            count = await generate_eval_data(input_path=input_path, output_path=output_path)

        assert count == 2
