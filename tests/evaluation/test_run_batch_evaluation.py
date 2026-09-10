"""Unit tests for evaluation/scripts/run_batch_evaluation.py helpers."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from maf_graphrag.evaluation.config import EvalConfig
from maf_graphrag.evaluation.scripts import run_batch_evaluation as module
from maf_graphrag.evaluation.scripts.run_batch_evaluation import (
    DATASETS_DIR,
    _build_expected_route_lines,
    _build_route_accuracy_lines,
    _build_route_summary_lines,
    _coerce_route_summary_row,
    _collect_foundry_metrics,
    _compute_route_summary,
    _determine_foundry_evaluators,
    _evaluate_locally,
    _evaluate_with_foundry,
    _extract_response_text,
    _extract_text_from_content,
    _load_eval_items,
    _resolve_cli_data_path,
    _resolve_parquet_path,
    _summarize_foundry_run,
    _update_route_summary_counts,
    _write_report,
    run_batch_evaluation,
)


@pytest.fixture(autouse=True)
def stub_agent_framework(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a lightweight agent_framework shim for tests."""

    eval_module = types.ModuleType("agent_framework")

    class EvalItem:  # pragma: no cover - lightweight shim
        def __init__(
            self,
            *,
            conversation: list[Any],
            tools: list[Any] | None,
            expected_output: str | None,
            response: str | None = None,
            expected_tool_calls: list[Any] | None = None,
        ) -> None:
            self.conversation = conversation
            self.tools = tools
            self.expected_output = expected_output
            self.response = response
            self.expected_tool_calls = expected_tool_calls

    class FunctionTool:  # pragma: no cover - lightweight shim
        def __init__(self, name: str | None) -> None:
            self.name = name

        @classmethod
        def from_dict(cls, data: dict[str, Any]) -> FunctionTool:
            return cls(data.get("name"))

    eval_module.EvalItem = EvalItem
    eval_module.FunctionTool = FunctionTool

    class ExpectedToolCall:  # pragma: no cover - lightweight shim
        def __init__(self, name: str, arguments: dict[str, Any] | None = None) -> None:
            self.name = name
            self.arguments = arguments

    eval_module.ExpectedToolCall = ExpectedToolCall

    types_module = types.ModuleType("agent_framework._types")

    class Message:  # pragma: no cover - lightweight shim
        def __init__(self, role: str, content: Any, *, text: str | None = None) -> None:
            self.role = role
            self.content = content
            self.contents = content if isinstance(content, list) else None
            self.text = text or (content if isinstance(content, str) else "")

        @classmethod
        def from_dict(cls, data: dict[str, Any]) -> Message:
            role = str(data.get("role", ""))
            contents = data.get("contents")
            if isinstance(contents, list):
                text_chunks: list[str] = []
                for item in contents:
                    if isinstance(item, str):
                        text_chunks.append(item)
                    elif isinstance(item, dict) and isinstance(item.get("text"), str):
                        text_chunks.append(item["text"])
                return cls(role, contents, text="\n".join(text_chunks))

            content = data.get("content")
            text_value = content if isinstance(content, str) else ""
            return cls(role, content, text=text_value)

    types_module.Message = Message

    monkeypatch.setitem(sys.modules, "agent_framework", eval_module)
    monkeypatch.setitem(sys.modules, "agent_framework._types", types_module)


class TestResolveCliDataPath:
    def test_keeps_default_dataset_path_inside_datasets_dir(self) -> None:
        resolved = _resolve_cli_data_path("eval_data.jsonl")

        assert resolved == (DATASETS_DIR / "eval_data.jsonl").resolve()

    def test_accepts_absolute_path_within_datasets_dir(self) -> None:
        resolved = _resolve_cli_data_path(DATASETS_DIR / "eval_data.jsonl")

        assert resolved == (DATASETS_DIR / "eval_data.jsonl").resolve()

    def test_rejects_path_traversal_outside_datasets_dir(self) -> None:
        invalid_path = Path("..") / ".." / "secrets.jsonl"

        with pytest.raises(ValueError, match="must stay within"):
            _resolve_cli_data_path(invalid_path)

    def test_rejects_non_jsonl_files(self) -> None:
        with pytest.raises(ValueError, match=r"must point to a \.jsonl file"):
            _resolve_cli_data_path("eval_data.json")


class TestResponseExtractionHelpers:
    def test_extract_text_from_content_handles_list_payloads(self) -> None:
        content = [
            "plain",
            {"type": "text", "text": "hello"},
            {"type": "output_text", "text": "world"},
            {"tool_result": "tool-output"},
            {"type": "ignored", "text": "nope"},
        ]

        result = _extract_text_from_content(content)

        assert result == "plain\nhello\nworld\ntool-output"

    def test_extract_response_text_prefers_latest_assistant_message(self) -> None:
        response: list[object] = [
            {"role": "user", "content": "input"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "final answer"},
                ],
            },
        ]

        assert _extract_response_text(response) == "final answer"

    def test_extract_response_text_falls_back_to_json_for_unstructured_list(self) -> None:
        response: list[object] = ["a", 1]

        assert _extract_response_text(response) == '["a", 1]'


class TestLoadEvalItems:
    def test_loads_items_and_preserves_ground_truth(self, tmp_path: Path) -> None:
        data_path = tmp_path / "eval_data.jsonl"
        row = {
            "query": "what is alpha",
            "conversation": [
                {"role": "assistant", "contents": [{"type": "text", "text": "answer"}]},
            ],
            "ground_truth": "alpha",
            "tool_definitions": [{"name": "search"}],
        }
        data_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

        items, rows_for_custom = _load_eval_items(data_path)

        assert len(items) == 1
        assert items[0].expected_output == "alpha"
        assert rows_for_custom[0]["response_text"] == "answer"

    def test_raises_when_no_rows_are_valid(self, tmp_path: Path) -> None:
        data_path = tmp_path / "eval_data.jsonl"
        data_path.write_text(json.dumps({"query": " ", "response": "x"}) + "\n", encoding="utf-8")

        with pytest.raises(ValueError, match="No evaluation rows were loaded"):
            _load_eval_items(data_path)

    def test_loads_plain_string_response_rows(self, tmp_path: Path) -> None:
        """Router-style rows (eval_router_data.jsonl) carry a plain-string ``response``
        with no ``conversation`` field; this must not be skipped as empty."""
        data_path = tmp_path / "eval_router_data.jsonl"
        row = {
            "query": "Hi there",
            "response": "I can help with questions about the knowledge base.",
            "tool_definitions": [{"name": "search_knowledge_graph"}],
        }
        data_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

        items, rows_for_custom = _load_eval_items(data_path)

        assert len(items) == 1
        conversation = items[0].conversation
        assert [getattr(m, "role", None) for m in conversation] == ["user", "assistant"]
        assert rows_for_custom[0]["response_text"] == "I can help with questions about the knowledge base."

    def test_injects_query_message_when_missing(self, tmp_path: Path) -> None:
        data_path = tmp_path / "eval_data.jsonl"
        row = {
            "query": "who leads alpha",
            "conversation": [
                {
                    "role": "assistant",
                    "contents": [
                        {"type": "text", "text": "alpha overview"},
                    ],
                }
            ],
        }
        data_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

        items, _ = _load_eval_items(data_path)

        first_message = items[0].conversation[0]

        assert first_message.role == "user"
        assert getattr(first_message, "text", "") == "who leads alpha"

    def test_converts_expected_tools_into_expected_tool_calls(self, tmp_path: Path) -> None:
        data_path = tmp_path / "eval_data.jsonl"
        row = {
            "query": "list key projects",
            "conversation": [
                {
                    "role": "assistant",
                    "contents": [
                        {
                            "type": "text",
                            "text": "Project Alpha focus",
                        }
                    ],
                }
            ],
            "expected_tools": ["global_search"],
        }
        data_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

        items, _ = _load_eval_items(data_path)

        expected_calls = items[0].expected_tool_calls

        assert expected_calls is not None
        assert len(expected_calls) == 1
        assert expected_calls[0].name == "global_search"

    def test_derives_expected_tool_calls_from_tool_calls(self, tmp_path: Path) -> None:
        data_path = tmp_path / "eval_data.jsonl"
        row = {
            "query": "find strategic themes",
            "conversation": [
                {
                    "role": "assistant",
                    "contents": [
                        {
                            "type": "text",
                            "text": "Themes overview",
                        }
                    ],
                }
            ],
            "tool_calls": [
                {
                    "name": "global_search",
                    "arguments": {
                        "query": "find strategic themes",
                        "community_level": 2,
                    },
                }
            ],
        }
        data_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

        items, _ = _load_eval_items(data_path)

        expected_calls = items[0].expected_tool_calls

        assert expected_calls is not None
        assert len(expected_calls) == 1
        assert expected_calls[0].name == "global_search"
        assert expected_calls[0].arguments == {
            "query": "find strategic themes",
            "community_level": 2,
        }

    def test_derives_expected_tool_calls_from_conversation_chunks(self, tmp_path: Path) -> None:
        data_path = tmp_path / "eval_data.jsonl"
        row = {
            "query": "detail major themes",
            "conversation": [
                {
                    "role": "assistant",
                    "contents": [
                        {
                            "type": "tool_call",
                            "name": "global_search",
                            "arguments": {
                                "query": "detail major themes",
                                "response_type": "Multiple Paragraphs",
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "contents": [
                        {
                            "type": "tool_result",
                            "tool_result": "Themes response",
                        }
                    ],
                },
                {
                    "role": "assistant",
                    "contents": [
                        {
                            "type": "text",
                            "text": "Themes summary",
                        }
                    ],
                },
            ],
        }
        data_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

        items, _ = _load_eval_items(data_path)

        expected_calls = items[0].expected_tool_calls

        assert expected_calls is not None
        assert len(expected_calls) == 1
        assert expected_calls[0].name == "global_search"
        assert expected_calls[0].arguments == {
            "query": "detail major themes",
            "response_type": "Multiple Paragraphs",
        }

    def test_normalizes_tool_messages_for_agent_framework(self, tmp_path: Path) -> None:
        data_path = tmp_path / "eval_data.jsonl"
        row = {
            "query": "show tool call metadata",
            "conversation": [
                {
                    "role": "assistant",
                    "contents": [
                        {
                            "type": "tool_call",
                            "tool_call_id": "call_123",
                            "name": "global_search",
                            "arguments": {"query": "alpha", "response_type": "Summary"},
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "call_123",
                    "contents": [
                        {
                            "type": "tool_result",
                            "tool_result": {"text": "alpha response"},
                        }
                    ],
                },
            ],
        }
        data_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

        items, _ = _load_eval_items(data_path)

        conversation = items[0].conversation
        call_chunks = conversation[1].contents
        result_chunks = conversation[2].contents

        assert isinstance(call_chunks, list)
        assert call_chunks[0]["call_id"] == "call_123"
        assert call_chunks[0]["type"] == "function_call"
        assert "tool_call_id" not in call_chunks[0]
        assert call_chunks[0]["tool_name"] == "global_search"

        assert isinstance(result_chunks, list)
        assert result_chunks[0]["call_id"] == "call_123"
        assert result_chunks[0]["type"] == "function_result"
        assert result_chunks[0]["result"] == {"text": "alpha response"}
        assert "tool_result" not in result_chunks[0]


class TestComputeRouteSummary:
    def test_returns_none_when_route_fields_are_missing(self, tmp_path: Path) -> None:
        data_path = tmp_path / "eval_data.jsonl"
        data_path.write_text(
            json.dumps({"query": "q1", "response": "r1"}) + "\n",
            encoding="utf-8",
        )

        assert _compute_route_summary(data_path) is None

    def test_computes_route_accuracy_and_breakdown(self, tmp_path: Path) -> None:
        data_path = tmp_path / "eval_router_data.jsonl"
        rows: list[dict[str, Any]] = [
            {
                "query": "a",
                "route_match": True,
                "expected_routed_workflow": "out_of_context",
                "accepted_routed_workflows": ["out_of_context"],
            },
            {
                "query": "b",
                "route_match": False,
                "expected_routed_workflow": "out_of_context",
                "accepted_routed_workflows": ["out_of_context"],
            },
            {
                "query": "c",
                "route_match": True,
                "expected_routed_workflow": "in_context",
                "accepted_routed_workflows": ["handoff", "sequential"],
            },
            {"query": "d", "route_match": None, "expected_routed_workflow": "in_context"},
        ]
        data_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

        summary = _compute_route_summary(data_path)

        assert summary is not None
        summary_dict = cast(dict[str, Any], summary)
        assert summary_dict["total_cases"] == 4
        assert summary_dict["decided_cases"] == 3
        assert summary_dict["matched_cases"] == 2
        assert summary_dict["route_accuracy"] == pytest.approx(2 / 3)
        assert summary_dict["flexible_cases"] == 1
        assert summary_dict["flexible_matched_cases"] == 1
        assert summary_dict["flexible_accuracy"] == pytest.approx(1.0)

        by_expected = cast(dict[str, dict[str, Any]], summary_dict["by_expected_route"])
        assert by_expected["out_of_context"]["cases"] == 2
        assert by_expected["out_of_context"]["matched"] == 1
        assert by_expected["out_of_context"]["accuracy"] == pytest.approx(0.5)
        assert by_expected["in_context"]["cases"] == 2
        assert by_expected["in_context"]["matched"] == 1
        assert by_expected["in_context"]["accuracy"] == pytest.approx(0.5)


class TestRouteSummaryHelpers:
    def test_coerce_route_summary_row(self) -> None:
        assert _coerce_route_summary_row("\n") is None
        assert _coerce_route_summary_row(json.dumps([1, 2])) is None
        assert _coerce_route_summary_row(json.dumps({"route_match": True})) == {"route_match": True}

    def test_update_route_summary_counts_with_flexible_case(self) -> None:
        by_expected: dict[str, dict[str, int]] = {}

        counts = _update_route_summary_counts(
            route_match=True,
            accepted_routes=["sequential", "handoff"],
            expected_route="in_context",
            by_expected_route=by_expected,
            counts=(1, 0, 0, 0, 0),
        )

        assert counts == (1, 1, 1, 1, 1)
        assert by_expected["in_context"] == {"cases": 1, "matched": 1}


class TestReportAndFormattingHelpers:
    def test_build_route_accuracy_lines_formats_percentages(self) -> None:
        lines = _build_route_accuracy_lines(
            {
                "total_cases": 10,
                "decided_cases": 8,
                "matched_cases": 6,
                "route_accuracy": 0.75,
                "flexible_cases": 2,
                "flexible_matched_cases": 1,
                "flexible_accuracy": 0.5,
            }
        )

        assert "- Total cases: 10" in lines
        assert "- Route accuracy: 0.750 (75.0%)" in lines
        assert "- Flexible accuracy: 0.500 (50.0%)" in lines

    def test_build_expected_route_lines_handles_stats(self) -> None:
        lines = _build_expected_route_lines(
            {
                "in_context": {"cases": 3, "matched": 2, "accuracy": 2 / 3},
                "out_of_context": {"cases": 2, "matched": 2, "accuracy": 1.0},
            }
        )

        assert lines[0].startswith("| Expected Route")
        assert any("| in_context | 3 | 2 | 0.667 |" in line for line in lines)
        assert any("| out_of_context | 2 | 2 | 1.000 |" in line for line in lines)

    def test_build_route_summary_lines_empty_when_invalid_payload(self) -> None:
        assert _build_route_summary_lines(None) == []

    def test_write_report_includes_foundry_section(self, tmp_path: Path) -> None:
        output_path = tmp_path / "evaluation_report.md"
        result = {
            "metrics": {"coherence": 0.8},
            "route_summary": {
                "total_cases": 1,
                "decided_cases": 1,
                "matched_cases": 1,
                "route_accuracy": 1.0,
                "by_expected_route": {"in_context": {"cases": 1, "matched": 1, "accuracy": 1.0}},
            },
            "studio_url": "https://ai.azure.com/report",
        }

        _write_report(result, output_path)

        report_text = output_path.read_text(encoding="utf-8")
        assert "## Summary Metrics" in report_text
        assert "## Router Route Accuracy" in report_text
        assert "## Azure AI Foundry Dashboard" in report_text


class TestParquetPathResolution:
    def test_prefers_existing_path(self, tmp_path: Path) -> None:
        preferred = tmp_path / "create_final_entities.parquet"
        preferred.write_text("x", encoding="utf-8")

        resolved = _resolve_parquet_path(preferred, fallback_name="entities.parquet")

        assert resolved == preferred

    def test_uses_fallback_when_preferred_is_missing(self, tmp_path: Path) -> None:
        preferred = tmp_path / "create_final_entities.parquet"
        fallback = tmp_path / "entities.parquet"
        fallback.write_text("x", encoding="utf-8")

        resolved = _resolve_parquet_path(preferred, fallback_name="entities.parquet")

        assert resolved == fallback


class TestRunBatchEvaluation:
    @staticmethod
    def _make_config() -> EvalConfig:
        return EvalConfig(
            azure_endpoint="https://example.openai.azure.com/",
            api_key="test-key",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o-eval",
            redteam_chat_deployment="gpt-4o-redteam",
            api_version="2024-08-01-preview",
            entities_parquet_path="missing/entities.parquet",
            relationships_parquet_path="missing/relationships.parquet",
        )

    @staticmethod
    def _write_eval_row(data_path: Path) -> None:
        data_path.write_text(
            json.dumps(
                {
                    "query": "What is Project Alpha?",
                    "response": [
                        {
                            "role": "assistant",
                            "content": [
                                {"type": "text", "text": "Project Alpha is..."},
                            ],
                        }
                    ],
                    "ground_truth": "Project Alpha is...",
                    "tool_definitions": [{"name": "global_search"}],
                    "expected_tools": ["global_search"],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_runs_foundry_evaluation_and_merges_metrics(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        data_path = tmp_path / "eval_data.jsonl"
        self._write_eval_row(data_path)
        monkeypatch.setattr(module, "DATASETS_DIR", tmp_path)
        output_dir = tmp_path / "results"
        monkeypatch.setattr(module, "RESULTS_DIR", output_dir)

        monkeypatch.setattr(
            "maf_graphrag.evaluation.config.EvalConfig.from_env",
            lambda: self._make_config(),
        )

        class DummyResult:
            def __init__(self) -> None:
                self.items = [
                    SimpleNamespace(
                        scores=[
                            SimpleNamespace(name="coherence", score=0.8),
                            SimpleNamespace(name="coherence", score=1.0),
                        ]
                    )
                ]
                self.provider = "foundry"
                self.status = "succeeded"
                self.passed = 1
                self.failed = 0
                self.total = 1
                self.per_evaluator = {"coherence": {"passed": 1, "failed": 0}}
                self.report_url = "https://studio"
                self.eval_id = "eval-123"
                self.run_id = "run-123"
                self.error = None

        dummy_result = DummyResult()

        async def fake_foundry_eval(
            items: list[Any],
            config: EvalConfig,
            eval_name: str,
            evaluators: list[str],
        ) -> DummyResult:
            assert len(items) == 1
            assert eval_name.startswith("graphrag-batch-workflow-")
            assert evaluators == module._DEFAULT_FOUNDRY_EVALUATORS
            return dummy_result

        monkeypatch.setattr(module, "_evaluate_with_foundry", fake_foundry_eval)
        monkeypatch.setattr(module, "_run_custom_evaluators", lambda rows, config: {"entity_accuracy": 0.5})

        result = run_batch_evaluation(data_path=data_path, output_dir=output_dir, use_foundry=True)

        assert result["metrics"] == {"coherence": 0.9, "entity_accuracy": 0.5}
        assert result["studio_url"] == "https://studio"
        assert (output_dir / "evaluation_results.json").exists()
        assert (output_dir / "evaluation_report.md").exists()

    def test_router_eval_type_uses_distinct_eval_name_and_evaluator_subset(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Router and workflow batches must never share a Foundry Eval object: evaluators
        (testing_criteria) are bound to the Eval at creation time, not per run, so mixing
        them would force a union set and report NA/blank scores for inapplicable evaluators."""
        data_path = tmp_path / "eval_router_data.jsonl"
        data_path.write_text(
            json.dumps({"query": "Hi there", "response": "I can help.", "tool_definitions": []}) + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(module, "DATASETS_DIR", tmp_path)
        output_dir = tmp_path / "results"
        monkeypatch.setattr(module, "RESULTS_DIR", output_dir)
        monkeypatch.setattr(
            "maf_graphrag.evaluation.config.EvalConfig.from_env",
            lambda: self._make_config(),
        )

        class DummyResult:
            def __init__(self) -> None:
                self.items = [SimpleNamespace(scores=[SimpleNamespace(name="coherence", score=0.9)])]
                self.provider = "foundry"
                self.status = "succeeded"
                self.passed = 1
                self.failed = 0
                self.total = 1
                self.per_evaluator = {"coherence": {"passed": 1, "failed": 0}}
                self.report_url = None
                self.eval_id = "eval-router"
                self.run_id = "run-router"
                self.error = None

        async def fake_foundry_eval(
            items: list[Any],
            config: EvalConfig,
            eval_name: str,
            evaluators: list[str],
        ) -> DummyResult:
            assert eval_name.startswith("graphrag-batch-router-")
            assert evaluators == module._ROUTER_FOUNDRY_EVALUATORS
            return DummyResult()

        monkeypatch.setattr(module, "_evaluate_with_foundry", fake_foundry_eval)

        run_batch_evaluation(data_path=data_path, output_dir=output_dir, include_custom=False, eval_type="router")


class TestFoundryHelpers:
    def test_collect_foundry_metrics_averages_scores(self) -> None:
        result = SimpleNamespace(
            items=[
                SimpleNamespace(scores=[SimpleNamespace(name="coherence", score=0.8)]),
                SimpleNamespace(scores=[SimpleNamespace(name="coherence", score=0.6)]),
            ],
            per_evaluator={},
        )

        metrics = _collect_foundry_metrics(result)

        assert metrics == {"coherence": 0.7}

    def test_summarize_foundry_run_includes_metadata(self) -> None:
        result = SimpleNamespace(
            provider="foundry",
            status="succeeded",
            passed=1,
            failed=0,
            total=1,
            per_evaluator={"coherence": {"passed": 1, "failed": 0}},
            eval_id="eval-123",
            run_id="run-456",
            report_url="https://studio",
            error=None,
        )

        summary = _summarize_foundry_run(result)

        assert summary["provider"] == "foundry"
        assert summary["eval_id"] == "eval-123"
        assert summary["per_evaluator"]["coherence"]["passed"] == 1


class TestDetermineFoundryEvaluators:
    def test_router_eval_type_uses_router_subset(self) -> None:
        evaluators = _determine_foundry_evaluators(
            "router",
            [SimpleNamespace(expected_tool_calls=None)],
        )

        assert evaluators == module._ROUTER_FOUNDRY_EVALUATORS

    def test_strips_tool_metrics_when_no_expected_calls_present(self) -> None:
        evaluators = _determine_foundry_evaluators(
            "workflow",
            [SimpleNamespace(expected_tool_calls=None)],
        )

        assert evaluators == [
            name for name in module._DEFAULT_FOUNDRY_EVALUATORS if not name.startswith(module._TOOL_EVALUATOR_PREFIX)
        ]

    def test_keeps_tool_metrics_when_expected_calls_present(self) -> None:
        evaluators = _determine_foundry_evaluators(
            "workflow",
            [SimpleNamespace(expected_tool_calls=[object()])],
        )

        assert evaluators == module._DEFAULT_FOUNDRY_EVALUATORS


class TestEvaluateWithFoundry:
    @staticmethod
    def _make_config() -> EvalConfig:
        return EvalConfig(
            azure_endpoint="https://example.openai.azure.com/",
            api_key="test-key",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o-eval",
            redteam_chat_deployment="gpt-4o-redteam",
            api_version="2024-08-01-preview",
        )

    async def test_requests_tool_selection_alongside_default_evaluators(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured_kwargs: dict[str, Any] = {}

        class FakeFoundryEvals:
            def __init__(self, **kwargs: Any) -> None:
                captured_kwargs.update(kwargs)

            async def evaluate(self, items: Any, *, eval_name: str) -> str:
                return "result"

        fake_module = types.ModuleType("agent_framework_foundry")
        fake_module.FoundryChatClient = SimpleNamespace  # type: ignore[attr-defined]
        fake_module.FoundryEvals = FakeFoundryEvals  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "agent_framework_foundry", fake_module)

        result = await _evaluate_with_foundry(
            [],
            self._make_config(),
            "graphrag-batch-test",
            module._DEFAULT_FOUNDRY_EVALUATORS,
        )

        assert result == "result"
        assert captured_kwargs["evaluators"] == module._DEFAULT_FOUNDRY_EVALUATORS
        assert captured_kwargs["timeout"] == 600.0
        assert "client" not in captured_kwargs


class TestEvaluateLocally:
    async def test_uses_native_local_evaluator_with_tool_call_checks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Local-only path must use agent_framework's own LocalEvaluator/checks —
        no Foundry client, no network calls — so cost-sensitive profiles stay free."""
        captured: dict[str, Any] = {}

        class FakeLocalEvaluator:
            def __init__(self, *checks: Any) -> None:
                captured["checks"] = checks

            async def evaluate(self, items: Any, *, eval_name: str) -> str:
                captured["items"] = items
                captured["eval_name"] = eval_name
                return "local-result"

        def fake_tool_calls_present() -> None:  # pragma: no cover - identity marker only
            raise AssertionError("should not be invoked directly in this test")

        def fake_tool_call_args_match() -> None:  # pragma: no cover - identity marker only
            raise AssertionError("should not be invoked directly in this test")

        agent_framework_module = sys.modules["agent_framework"]
        monkeypatch.setattr(agent_framework_module, "LocalEvaluator", FakeLocalEvaluator, raising=False)
        monkeypatch.setattr(agent_framework_module, "tool_calls_present", fake_tool_calls_present, raising=False)
        monkeypatch.setattr(agent_framework_module, "tool_call_args_match", fake_tool_call_args_match, raising=False)

        result = await _evaluate_locally([], "graphrag-batch-local-test")

        assert result == "local-result"
        assert captured["checks"] == (fake_tool_calls_present, fake_tool_call_args_match)
        assert captured["eval_name"] == "graphrag-batch-local-test"
