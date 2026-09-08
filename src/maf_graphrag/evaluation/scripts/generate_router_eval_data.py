"""
Generate router-focused evaluation data using RouterWorkflow.

This script evaluates routing behavior (including out_of_context) and writes
JSONL records consumable by run_batch_evaluation.py.

Usage:
    uv run python -m maf_graphrag.evaluation.scripts.generate_router_eval_data
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

logger = logging.getLogger(__name__)

DATASETS_DIR = Path(__file__).resolve().parent.parent / "datasets"
GOLDEN_ROUTER_QUESTIONS_PATH = DATASETS_DIR / "golden_router_questions.jsonl"
EVAL_ROUTER_DATA_PATH = DATASETS_DIR / "eval_router_data.jsonl"
ROUTED_WORKFLOW_LABELS = {"sequential", "concurrent", "handoff", "out_of_context"}
IN_CONTEXT_ROUTED_WORKFLOW_LABELS = {"sequential", "concurrent", "handoff"}


def _extract_router_metadata(result: object) -> dict[str, str | None]:
    """Extract router metadata from first step in WorkflowResult."""
    routed_workflow: str | None = None
    classifier_status: str | None = None
    fallback_reason: str | None = None

    steps = getattr(result, "steps", [])
    if steps:
        metadata = getattr(steps[0], "metadata", {})
        if isinstance(metadata, dict):
            routed = metadata.get("routed_workflow")
            status = metadata.get("classifier_status")
            fallback = metadata.get("fallback_reason")
            routed_workflow = routed if isinstance(routed, str) else None
            classifier_status = status if isinstance(status, str) else None
            fallback_reason = fallback if isinstance(fallback, str) else None

    return {
        "routed_workflow": routed_workflow,
        "classifier_status": classifier_status,
        "fallback_reason": fallback_reason,
    }


def _normalize_routed_workflow(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in ROUTED_WORKFLOW_LABELS:
        return normalized
    return None


def _resolve_accepted_routed_workflows(case: dict[str, object]) -> set[str] | None:
    accepted = case.get("accepted_routed_workflows")
    if isinstance(accepted, list):
        normalized = {
            workflow for workflow in (_normalize_routed_workflow(value) for value in accepted) if workflow is not None
        }
        if normalized:
            return normalized

    expected_route = case.get("expected_routed_workflow")
    if not isinstance(expected_route, str):
        return None

    expected_route = expected_route.strip().lower()
    if expected_route == "in_context":
        return set(IN_CONTEXT_ROUTED_WORKFLOW_LABELS)
    if expected_route == "out_of_context":
        return {"out_of_context"}

    normalized_expected = _normalize_routed_workflow(expected_route)
    if normalized_expected is None:
        return None
    return {normalized_expected}


def _compute_route_match(routed_workflow: object, accepted_routed_workflows: set[str] | None) -> bool | None:
    if accepted_routed_workflows is None:
        return None

    normalized_routed_workflow = _normalize_routed_workflow(routed_workflow)
    if normalized_routed_workflow is None:
        return False

    return normalized_routed_workflow in accepted_routed_workflows


async def generate_router_eval_data(
    input_path: str | Path = GOLDEN_ROUTER_QUESTIONS_PATH,
    output_path: str | Path = EVAL_ROUTER_DATA_PATH,
) -> int:
    """Run RouterWorkflow on golden router questions and write eval JSONL."""
    from maf_graphrag.evaluation.evaluators.builtin import GRAPHRAG_TOOL_DEFINITIONS
    from maf_graphrag.workflows.router import create_router_workflow

    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Golden router questions file not found: {input_path}")

    def _read_jsonl(path: Path) -> list[dict[str, object]]:
        with open(path, encoding="utf-8") as fh:
            return [json.loads(line.strip()) for line in fh if line.strip()]

    test_cases = await asyncio.to_thread(_read_jsonl, input_path)
    logger.info("Loaded %d router test cases from %s", len(test_cases), input_path)

    records: list[str] = []
    async with create_router_workflow() as workflow:
        for index, case in enumerate(test_cases, 1):
            query = str(case.get("query", "")).strip()
            if not query:
                continue

            logger.info("[%d/%d] Processing: %s", index, len(test_cases), query)
            result = await workflow.run(query, include_status_events=False)
            metadata = _extract_router_metadata(result)

            expected_route = case.get("expected_routed_workflow")
            expected_routed_workflow = expected_route if isinstance(expected_route, str) else ""
            accepted_routed_workflows = _resolve_accepted_routed_workflows(case)
            routed_workflow = metadata.get("routed_workflow")
            normalized_routed_workflow = _normalize_routed_workflow(routed_workflow)
            is_route_match = _compute_route_match(normalized_routed_workflow, accepted_routed_workflows)

            eval_record = {
                "query": query,
                "response": result.answer,
                "ground_truth": str(case.get("ground_truth", "")),
                "tool_definitions": GRAPHRAG_TOOL_DEFINITIONS,
                "routed_workflow": routed_workflow,
                "classifier_status": metadata.get("classifier_status"),
                "fallback_reason": metadata.get("fallback_reason"),
                "expected_routed_workflow": expected_routed_workflow,
                "accepted_routed_workflows": sorted(accepted_routed_workflows) if accepted_routed_workflows else [],
                "route_match": is_route_match,
            }
            records.append(json.dumps(eval_record, ensure_ascii=False) + "\n")

    def _write_jsonl(path: Path, lines: list[str]) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(lines)

    await asyncio.to_thread(_write_jsonl, output_path, records)
    logger.info("Wrote %d router evaluation records to %s", len(records), output_path)
    return len(records)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    for name in ("litellm", "httpx", "httpcore", "openai", "azure", "mcp", "agent_framework", "asyncio"):
        logging.getLogger(name).setLevel(logging.ERROR)

    count = asyncio.run(generate_router_eval_data())
    print(f"\nGenerated {count} router evaluation records in {EVAL_ROUTER_DATA_PATH}")
