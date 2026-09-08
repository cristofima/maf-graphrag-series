"""Unit tests for evaluation/scripts/run_batch_evaluation.py helpers."""

import json
from pathlib import Path
from typing import Any, cast

import pytest

from maf_graphrag.evaluation.config import EvalConfig
from maf_graphrag.evaluation.scripts.run_batch_evaluation import (
    DATASETS_DIR,
    _build_evaluator_config,
    _build_expected_route_lines,
    _build_new_foundry_testing_criteria,
    _build_route_accuracy_lines,
    _build_route_summary_lines,
    _coerce_route_summary_row,
    _compute_route_summary,
    _extract_response_text,
    _extract_text_from_content,
    _extract_tool_calls,
    _load_new_foundry_rows,
    _resolve_cli_data_path,
    _resolve_parquet_path,
    _select_foundry_evaluator_names,
    _update_route_summary_counts,
    _write_report,
    run_batch_evaluation,
)


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


class TestSelectFoundryEvaluatorNames:
    def test_selects_supported_foundry_evaluators(self) -> None:
        selected = _select_foundry_evaluator_names(
            {
                "task_adherence": object(),
                "intent_resolution": object(),
                "coherence": object(),
                "response_completeness": object(),
                "tool_call_accuracy": object(),
                "entity_accuracy": object(),
            }
        )

        assert selected == {
            "task_adherence",
            "intent_resolution",
            "coherence",
            "response_completeness",
            "tool_call_accuracy",
        }

    def test_ignores_unknown_or_disabled_evaluators(self) -> None:
        selected = _select_foundry_evaluator_names({"entity_accuracy": object(), "foo": object()})

        assert selected == set()


class TestBuildNewFoundryTestingCriteria:
    def test_maps_tool_definitions_for_task_and_intent(self) -> None:
        criteria = _build_new_foundry_testing_criteria(
            {"task_adherence", "intent_resolution"},
            model_deployment="graphrag-main-eval",
            has_structured_tool_calls=False,
        )

        by_name = {item["name"]: item for item in criteria}

        task_mapping = cast(dict[str, str], by_name["task_adherence"]["data_mapping"])
        intent_mapping = cast(dict[str, str], by_name["intent_resolution"]["data_mapping"])

        assert task_mapping["tool_definitions"] == "{{item.tool_definitions}}"
        assert intent_mapping["tool_definitions"] == "{{item.tool_definitions}}"


class TestBuildEvaluatorConfig:
    def test_includes_and_excludes_optional_mappings(self) -> None:
        config = _build_evaluator_config(
            {
                "task_adherence": object(),
                "tool_call_accuracy": object(),
                "response_completeness": object(),
                "entity_accuracy": object(),
            }
        )

        assert "task_adherence" in config
        assert "tool_call_accuracy" in config
        assert "intent_resolution" not in config
        assert config["tool_call_accuracy"]["column_mapping"] == {
            "query": "${data.query}",
            "response": "${data.response}",
            "tool_definitions": "${data.tool_definitions}",
        }
        assert config["response_completeness"]["column_mapping"] == {
            "ground_truth": "${data.ground_truth}",
            "response": "${data.response}",
        }


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

    def test_extract_tool_calls_collects_tool_call_items(self) -> None:
        response: list[object] = [
            {
                "content": [
                    {"type": "tool_call", "tool_call": {"name": "search", "arguments": "{}"}},
                    {"type": "text", "text": "ignored"},
                ]
            }
        ]

        assert _extract_tool_calls(response) == [{"name": "search", "arguments": "{}"}]


class TestLoadNewFoundryRows:
    def test_loads_rows_and_detects_structured_tool_calls(self, tmp_path: Path) -> None:
        data_path = tmp_path / "eval_data.jsonl"
        row = {
            "query": "what is alpha",
            "response": [
                {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_call", "tool_call": {"name": "local_search", "arguments": "{}"}},
                        {"type": "text", "text": "answer"},
                    ],
                }
            ],
            "ground_truth": "answer",
            "tool_definitions": [{"name": "local_search"}],
        }
        data_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

        rows, has_tool_calls = _load_new_foundry_rows(data_path)

        assert has_tool_calls is True
        assert rows[0]["query"] == "what is alpha"
        assert rows[0]["response"] == "answer"
        assert rows[0]["tool_calls"] == [{"name": "local_search", "arguments": "{}"}]

    def test_raises_when_no_valid_rows_are_loaded(self, tmp_path: Path) -> None:
        data_path = tmp_path / "eval_data.jsonl"
        data_path.write_text(json.dumps({"query": " ", "response": "x"}) + "\n", encoding="utf-8")

        with pytest.raises(ValueError, match="No evaluation rows were loaded"):
            _load_new_foundry_rows(data_path)


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
                    "response": "Project Alpha is...",
                    "ground_truth": "Project Alpha is...",
                    "tool_definitions": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_runs_local_evaluation_without_foundry(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        data_path = tmp_path / "eval_data.jsonl"
        self._write_eval_row(data_path)
        monkeypatch.setattr("maf_graphrag.evaluation.scripts.run_batch_evaluation.DATASETS_DIR", tmp_path)

        monkeypatch.setattr("maf_graphrag.evaluation.config.EvalConfig.from_env", lambda: self._make_config())
        monkeypatch.setattr(
            "maf_graphrag.evaluation.evaluators.builtin.create_quality_evaluators",
            lambda _: {
                "task_adherence": object(),
                "intent_resolution": object(),
                "tool_call_accuracy": object(),
            },
        )
        monkeypatch.setattr(
            "maf_graphrag.evaluation.scripts.run_batch_evaluation._supports_legacy_max_tokens", lambda _: False
        )
        monkeypatch.setattr(
            "maf_graphrag.evaluation.scripts.run_batch_evaluation._add_custom_evaluators",
            lambda evaluators, config, include_custom: None,
        )
        monkeypatch.setattr(
            "azure.ai.evaluation.evaluate",
            lambda **_: {
                "metrics": {"task_adherence": 0.9},
            },
            raising=False,
        )

        result = run_batch_evaluation(
            data_path="eval_data.jsonl",
            output_dir=tmp_path,
            use_foundry=False,
            include_custom=False,
        )

        assert result["metrics"] == {"task_adherence": 0.9}
        assert "new_foundry" not in result
        assert "foundry_publish_error" not in result
        assert (tmp_path / "evaluation_report.md").exists()

    def test_continues_when_foundry_publish_fails(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        data_path = tmp_path / "eval_data.jsonl"
        self._write_eval_row(data_path)
        monkeypatch.setattr("maf_graphrag.evaluation.scripts.run_batch_evaluation.DATASETS_DIR", tmp_path)

        monkeypatch.setattr("maf_graphrag.evaluation.config.EvalConfig.from_env", lambda: self._make_config())
        monkeypatch.setattr(
            "maf_graphrag.evaluation.evaluators.builtin.create_quality_evaluators",
            lambda _: {"task_adherence": object()},
        )
        monkeypatch.setattr(
            "maf_graphrag.evaluation.scripts.run_batch_evaluation._add_custom_evaluators",
            lambda evaluators, config, include_custom: None,
        )
        monkeypatch.setattr(
            "maf_graphrag.evaluation.scripts.run_batch_evaluation._publish_new_foundry_batch_run",
            lambda **_: (_ for _ in ()).throw(RuntimeError("publish failed")),
        )
        monkeypatch.setattr(
            "azure.ai.evaluation.evaluate",
            lambda **_: {"metrics": {"coherence": 0.8}},
            raising=False,
        )

        result = run_batch_evaluation(
            data_path="eval_data.jsonl",
            output_dir=tmp_path,
            use_foundry=True,
            include_custom=False,
        )

        assert result["metrics"] == {"coherence": 0.8}
        assert "foundry_publish_error" in result

    def test_sets_studio_url_when_foundry_publish_succeeds(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        data_path = tmp_path / "eval_data.jsonl"
        self._write_eval_row(data_path)
        monkeypatch.setattr("maf_graphrag.evaluation.scripts.run_batch_evaluation.DATASETS_DIR", tmp_path)

        monkeypatch.setattr("maf_graphrag.evaluation.config.EvalConfig.from_env", lambda: self._make_config())
        monkeypatch.setattr(
            "maf_graphrag.evaluation.evaluators.builtin.create_quality_evaluators",
            lambda _: {"task_adherence": object()},
        )
        monkeypatch.setattr(
            "maf_graphrag.evaluation.scripts.run_batch_evaluation._add_custom_evaluators",
            lambda evaluators, config, include_custom: None,
        )
        monkeypatch.setattr(
            "maf_graphrag.evaluation.scripts.run_batch_evaluation._publish_new_foundry_batch_run",
            lambda **_: {
                "eval_id": "eval_1",
                "run_id": "run_1",
                "status": "completed",
                "report_url": "https://ai.azure.com/report",
            },
        )
        monkeypatch.setattr(
            "azure.ai.evaluation.evaluate",
            lambda **_: {"metrics": {"coherence": 0.8}},
            raising=False,
        )

        result = run_batch_evaluation(
            data_path="eval_data.jsonl",
            output_dir=tmp_path,
            use_foundry=True,
            include_custom=False,
        )

        assert result["studio_url"] == "https://ai.azure.com/report"
        assert result["new_foundry"]["status"] == "completed"
