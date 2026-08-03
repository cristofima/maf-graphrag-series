"""Unit tests for router eval routing-match helpers."""

from typing import Any

from evaluation.scripts.generate_router_eval_data import (
    _compute_route_match,
    _resolve_accepted_routed_workflows,
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
