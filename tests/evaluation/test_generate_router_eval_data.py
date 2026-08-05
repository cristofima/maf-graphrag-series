"""Unit tests for router eval routing-match helpers."""

import json
from pathlib import Path
from typing import Any

import pytest

from evaluation.scripts.generate_router_eval_data import (
    _compute_route_match,
    _extract_router_metadata,
    _normalize_routed_workflow,
    _resolve_accepted_routed_workflows,
    generate_router_eval_data,
)


class TestResolveAcceptedRoutedWorkflows:
    def test_uses_explicit_accepted_routes_when_present(self) -> None:
        case: dict[str, Any] = {
            "expected_routed_workflow": "in_context",
            "accepted_routed_workflows": ["handoff", "sequential", "unknown"],
        }

        accepted = _resolve_accepted_routed_workflows(case)

        assert accepted == {"handoff", "sequential"}

    def test_falls_back_to_in_context_defaults(self) -> None:
        case: dict[str, Any] = {"expected_routed_workflow": "in_context"}

        accepted = _resolve_accepted_routed_workflows(case)

        assert accepted == {"sequential", "concurrent", "handoff"}

    def test_falls_back_to_out_of_context_default(self) -> None:
        case: dict[str, Any] = {"expected_routed_workflow": "out_of_context"}

        accepted = _resolve_accepted_routed_workflows(case)

        assert accepted == {"out_of_context"}


class TestComputeRouteMatch:
    def test_returns_true_when_routed_workflow_is_accepted(self) -> None:
        assert _compute_route_match("sequential", {"handoff", "sequential"}) is True

    def test_returns_false_when_routed_workflow_is_not_accepted(self) -> None:
        assert _compute_route_match("concurrent", {"handoff", "sequential"}) is False

    def test_returns_none_without_acceptance_rule(self) -> None:
        assert _compute_route_match("sequential", None) is None


class _FakeStep:
    def __init__(self, metadata: object) -> None:
        self.metadata = metadata


class _FakeResult:
    def __init__(self, steps: list[object]) -> None:
        self.steps = steps


class TestRouterMetadataHelpers:
    def test_extract_router_metadata_reads_first_step_dict(self) -> None:
        result = _FakeResult(
            [
                _FakeStep(
                    {
                        "routed_workflow": "sequential",
                        "classifier_status": "ok",
                        "fallback_reason": "none",
                    }
                )
            ]
        )

        metadata = _extract_router_metadata(result)

        assert metadata == {
            "routed_workflow": "sequential",
            "classifier_status": "ok",
            "fallback_reason": "none",
        }

    def test_extract_router_metadata_defaults_to_none_for_invalid_metadata(self) -> None:
        result = _FakeResult([_FakeStep("not-a-dict")])

        metadata = _extract_router_metadata(result)

        assert metadata == {
            "routed_workflow": None,
            "classifier_status": None,
            "fallback_reason": None,
        }

    def test_normalize_routed_workflow(self) -> None:
        assert _normalize_routed_workflow(" Sequential ") == "sequential"
        assert _normalize_routed_workflow("OUT_OF_CONTEXT") == "out_of_context"
        assert _normalize_routed_workflow("invalid") is None
        assert _normalize_routed_workflow(42) is None


class _FakeStepForRun:
    def __init__(self) -> None:
        self.metadata = {
            "routed_workflow": "sequential",
            "classifier_status": "ok",
            "fallback_reason": "none",
        }


class _FakeRunResult:
    def __init__(self) -> None:
        self.steps = [_FakeStepForRun()]
        self.answer = "final answer"


class _FakeWorkflow:
    async def run(self, query: str, include_status_events: bool = False):
        del query, include_status_events
        return _FakeRunResult()


class _FakeWorkflowContext:
    async def __aenter__(self):
        return _FakeWorkflow()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


@pytest.mark.asyncio
async def test_generate_router_eval_data_writes_records(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    input_path = tmp_path / "golden_router_questions.jsonl"
    output_path = tmp_path / "eval_router_data.jsonl"
    input_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "query": "Who leads Project Alpha?",
                        "ground_truth": "Dr. Emily Harrison",
                        "expected_routed_workflow": "in_context",
                    }
                ),
                json.dumps(
                    {
                        "query": "   ",
                        "ground_truth": "ignored",
                        "expected_routed_workflow": "out_of_context",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "evaluation.evaluators.builtin.GRAPHRAG_TOOL_DEFINITIONS",
        [{"name": "search_knowledge_graph"}],
        raising=False,
    )
    monkeypatch.setattr("workflows.router.create_router_workflow", lambda: _FakeWorkflowContext())

    count = await generate_router_eval_data(input_path=input_path, output_path=output_path)

    assert count == 1
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["routed_workflow"] == "sequential"
    assert rows[0]["route_match"] is True
