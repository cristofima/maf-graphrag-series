"""Unit tests for evaluation/scripts/run_batch_evaluation.py helpers."""

import json
from pathlib import Path
from typing import Any, cast

import pytest

from evaluation.scripts.run_batch_evaluation import (
    DATASETS_DIR,
    _compute_route_summary,
    _resolve_cli_data_path,
    _select_foundry_evaluator_names,
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
