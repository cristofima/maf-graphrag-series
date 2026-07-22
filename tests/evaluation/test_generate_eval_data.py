"""Unit tests for evaluation/scripts/generate_eval_data.py — generate_eval_data().

The Knowledge Captain agent and its Azure OpenAI calls are fully mocked, so
these tests exercise only the file I/O, message merging, and JSONL writing
logic — no real agent runs, no credentials or API credits needed.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from evaluation.scripts.generate_eval_data import generate_eval_data


class _FakeSession:
    """Stand-in for agent_framework.AgentSession."""

    def __init__(self) -> None:
        self.state: dict = {"messages": []}


def _agent_stub(response_messages: list) -> MagicMock:
    agent = MagicMock()
    agent.__aenter__ = AsyncMock(return_value=agent)
    agent.__aexit__ = AsyncMock(return_value=False)
    agent.run = AsyncMock(return_value=MagicMock(messages=response_messages))
    return agent


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
            patch("agents.supervisor.create_knowledge_captain", return_value=_agent_stub([])),
            patch("agent_framework.AgentSession", side_effect=_FakeSession),
            patch(
                "evaluation.evaluators.builtin.convert_to_evaluator_messages",
                return_value=[{"role": "assistant", "content": "answer"}],
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
            patch("agents.supervisor.create_knowledge_captain", return_value=_agent_stub([])),
            patch("agent_framework.AgentSession", side_effect=_FakeSession),
            patch(
                "evaluation.evaluators.builtin.convert_to_evaluator_messages",
                return_value=[{"role": "assistant", "content": "Dr. Harrison leads it"}],
            ),
        ):
            await generate_eval_data(input_path=input_path, output_path=output_path)

        record = json.loads(output_path.read_text(encoding="utf-8").strip())
        assert record["query"] == "Who leads Project Alpha?"
        assert record["ground_truth"] == "Dr. Harrison"
        assert record["response"] == [{"role": "assistant", "content": "Dr. Harrison leads it"}]
        assert isinstance(record["tool_definitions"], list)

    async def test_missing_ground_truth_defaults_to_empty_string(self, tmp_path):
        input_path = tmp_path / "golden_questions.jsonl"
        output_path = tmp_path / "eval_data.jsonl"
        _write_golden_questions(input_path, [{"query": "What are the main themes?"}])

        with (
            patch("agents.supervisor.create_knowledge_captain", return_value=_agent_stub([])),
            patch("agent_framework.AgentSession", side_effect=_FakeSession),
            patch("evaluation.evaluators.builtin.convert_to_evaluator_messages", return_value=[]),
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
            patch("agents.supervisor.create_knowledge_captain", return_value=_agent_stub([])),
            patch("agent_framework.AgentSession", side_effect=_FakeSession),
            patch("evaluation.evaluators.builtin.convert_to_evaluator_messages", return_value=[]),
        ):
            count = await generate_eval_data(input_path=input_path, output_path=output_path)

        assert count == 2
