"""Unit tests for evaluation/scripts/generate_eval_data.py — generate_eval_data().

RouterWorkflowAgentAdapter and file I/O are fully mocked; no credentials needed.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from evaluation.scripts.generate_eval_data import generate_eval_data


def _stub_adapter(answer: str = "stub answer") -> MagicMock:
    result = MagicMock()
    result.answer = answer
    adapter = MagicMock()
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

        with patch("workflows.router_agent.RouterWorkflowAgentAdapter", return_value=_stub_adapter("answer")):
            count = await generate_eval_data(input_path=input_path, output_path=output_path)

        assert count == 2
        lines = output_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    async def test_record_contains_query_response_and_ground_truth(self, tmp_path):
        input_path = tmp_path / "golden_questions.jsonl"
        output_path = tmp_path / "eval_data.jsonl"
        _write_golden_questions(input_path, [{"query": "Who leads Project Alpha?", "ground_truth": "Dr. Harrison"}])

        with patch(
            "workflows.router_agent.RouterWorkflowAgentAdapter",
            return_value=_stub_adapter("Dr. Harrison leads it"),
        ):
            await generate_eval_data(input_path=input_path, output_path=output_path)

        record = json.loads(output_path.read_text(encoding="utf-8").strip())
        assert record["query"] == "Who leads Project Alpha?"
        assert record["ground_truth"] == "Dr. Harrison"
        assert record["response"] == [
            {"role": "user", "content": "Who leads Project Alpha?"},
            {"role": "assistant", "content": "Dr. Harrison leads it"},
        ]
        assert isinstance(record["tool_definitions"], list)

    async def test_missing_ground_truth_defaults_to_empty_string(self, tmp_path):
        input_path = tmp_path / "golden_questions.jsonl"
        output_path = tmp_path / "eval_data.jsonl"
        _write_golden_questions(input_path, [{"query": "What are the main themes?"}])

        with patch("workflows.router_agent.RouterWorkflowAgentAdapter", return_value=_stub_adapter()):
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

        with patch("workflows.router_agent.RouterWorkflowAgentAdapter", return_value=_stub_adapter()):
            count = await generate_eval_data(input_path=input_path, output_path=output_path)

        assert count == 2
