"""Generate evaluation data by running the router workflow on golden questions."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from maf_graphrag.evaluation.evaluators.builtin import GRAPHRAG_TOOL_DEFINITIONS
from maf_graphrag.workflows.base import WorkflowResult

load_dotenv()

# Ensure src/ is importable when invoked as a module script
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

logger = logging.getLogger(__name__)


# Paths
DATASETS_DIR = Path(__file__).resolve().parent.parent / "datasets"
GOLDEN_QUESTIONS_PATH = DATASETS_DIR / "golden_questions.jsonl"
EVAL_DATA_PATH = DATASETS_DIR / "eval_data.jsonl"


def _extract_router_metadata(result: WorkflowResult) -> dict[str, object]:
    """Return router metadata from the first workflow step when available."""

    if not result.steps:
        return {
            "routed_workflow": result.workflow_type.value,
            "classified_workflow": result.workflow_type.value,
            "query": result.query,
        }

    router_step = result.steps[0]
    metadata = dict(router_step.metadata)
    metadata.setdefault("routed_workflow", result.workflow_type.value)
    metadata.setdefault("classified_workflow", metadata.get("routed_workflow", result.workflow_type.value))
    metadata.setdefault("query", result.query)
    return metadata


def _extract_agent_turn_payloads(
    result: WorkflowResult,
    converter: Any,
    eval_extractor: Any,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    """Return serialized conversations, tool definitions, and tool calls."""

    agent_data: list[dict[str, Any]] = []
    if result.raw_result is not None:
        try:
            agent_data = eval_extractor(result.raw_result, result.workflow_graph)
        except Exception as exc:  # pragma: no cover - defensive guard for eval extraction issues
            logger.warning("Failed to extract agent evaluation data: %s", exc)
            agent_data = []

    fallback_data = _extract_agent_data_from_workflow(result, converter)

    if not agent_data:
        agent_data = fallback_data
        fallback_map: dict[str, dict[str, object]] = {}
    else:
        fallback_map = {
            str(entry.get("executor_id") or ""): entry
            for entry in fallback_data
            if entry.get("executor_id") is not None
        }

    if not agent_data:
        return [], list(GRAPHRAG_TOOL_DEFINITIONS), []

    agent_turns: list[dict[str, object]] = []
    tool_calls: list[dict[str, object]] = []
    tool_definitions: list[dict[str, object]] = []
    seen_tool_names: set[str] = set()

    for data in agent_data:
        executor_id = str(data.get("executor_id") or "")
        fallback_entry = fallback_map.get(executor_id) if fallback_map else None

        conversation: list[dict[str, object]] | None = None
        resolved_tools: list[dict[str, object]] = []
        tool_names_source: list[str] | None = None
        tool_calls_for_turn: list[dict[str, object]] | None = None

        if data.get("conversation") is not None:
            conversation = _normalize_conversation_messages(data.get("conversation") or [])
            raw_names = data.get("tool_names") or []
            tool_names_source = list(raw_names)
            extra_definitions = data.get("tool_definitions")
            if isinstance(extra_definitions, list):
                resolved_tools.extend(extra_definitions)
            tool_calls_for_turn = data.get("tool_calls")
        else:
            try:
                eval_item = converter.to_eval_item(
                    query=data.get("query") or result.query,
                    response=data.get("response"),
                    agent=data.get("agent"),
                )
            except Exception as exc:  # pragma: no cover - defensive guard for malformed eval payloads
                logger.debug("Falling back to workflow data for executor %s: %s", executor_id, exc)
                if fallback_entry and fallback_entry.get("conversation") is not None:
                    conversation = _normalize_conversation_messages(fallback_entry.get("conversation") or [])
                    raw_names = fallback_entry.get("tool_names") or []
                    tool_names_source = list(raw_names)
                    tool_calls_for_turn = fallback_entry.get("tool_calls")
                else:
                    continue
            else:
                conversation = _normalize_conversation_messages(converter.convert_messages(eval_item.conversation))
                agent_ref = data.get("agent")
                if agent_ref is not None:
                    resolved_tools.extend(converter.extract_tools(agent_ref))
                if eval_item.tools:
                    resolved_tools.extend(_tool_objects_to_dicts(eval_item.tools))
                tool_calls_for_turn = _extract_tool_calls_from_conversation(conversation, executor_id)

        if conversation is None:
            continue

        if not resolved_tools and tool_names_source:
            for name in tool_names_source:
                if not name:
                    continue
                resolved_tools.append(
                    {
                        "name": name,
                        "description": "",
                        "parameters": {},
                    }
                )

        agent_turns.append(
            {
                "executor_id": executor_id,
                "conversation": conversation,
            }
        )

        _merge_tool_definitions(tool_definitions, seen_tool_names, resolved_tools)

        if tool_calls_for_turn:
            tool_calls.extend(tool_calls_for_turn)
        else:
            tool_calls.extend(_extract_tool_calls_from_conversation(conversation, executor_id))

    if not tool_definitions:
        tool_definitions = list(GRAPHRAG_TOOL_DEFINITIONS)

    return agent_turns, tool_definitions, tool_calls


def _merge_tool_definitions(
    store: list[dict[str, object]],
    seen: set[str],
    candidates: Iterable[dict[str, Any]],
) -> None:
    for candidate in candidates:
        name = str(candidate.get("name", "")).strip()
        if not name or name in seen:
            continue
        store.append(
            {
                "name": name,
                "description": candidate.get("description", ""),
                "parameters": candidate.get("parameters", {}),
            }
        )
        seen.add(name)


def _tool_objects_to_dicts(tools: Iterable[Any]) -> list[dict[str, object]]:
    definitions: list[dict[str, object]] = []
    for tool in tools:
        name = getattr(tool, "name", None)
        if not isinstance(name, str) or not name:
            continue
        try:
            parameters = tool.parameters()
        except Exception:  # pragma: no cover - defensive guard for tool serialization
            parameters = {}
        definitions.append(
            {
                "name": name,
                "description": getattr(tool, "description", "") or "",
                "parameters": parameters,
            }
        )
    return definitions


def _normalize_conversation_messages(messages: Iterable[object]) -> list[dict[str, object]]:
    """Normalize message payloads to the Agent Framework ``Message`` schema."""

    normalized: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, Mapping):
            continue

        entry = dict(message)
        contents = entry.pop("contents", None)
        if contents is None and "content" in entry:
            contents = entry.pop("content")

        entry["contents"] = _coerce_content_list(contents)
        normalized.append(entry)

    return normalized


def _coerce_content_list(value: object) -> list[object]:
    if isinstance(value, list):
        coerced: list[object] = []
        for item in value:
            if isinstance(item, Mapping):
                coerced.append(dict(item))
            else:
                coerced.append(item)
        return coerced
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    return [value]


def _extract_tool_calls_from_conversation(
    conversation: Iterable[object],
    executor_id: str,
) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []
    results_by_id: dict[str, list[object]] = {}

    for message in conversation:
        if not isinstance(message, Mapping):
            continue
        role = str(message.get("role", ""))
        contents = message.get("contents")
        if contents is None:
            contents = message.get("content")

        if role.lower() == "tool":
            call_id = str(message.get("tool_call_id", ""))
            payloads = []
            if isinstance(contents, list):
                for item in contents:
                    if isinstance(item, Mapping) and item.get("type") == "tool_result":
                        payloads.append(item.get("tool_result"))
            results_by_id.setdefault(call_id, []).extend(payloads or [None])

        if not isinstance(contents, list):
            continue

        for item in contents:
            if not isinstance(item, Mapping) or item.get("type") != "tool_call":
                continue
            call_id = str(item.get("tool_call_id", ""))
            calls.append(
                {
                    "executor_id": executor_id,
                    "tool_call_id": call_id,
                    "name": item.get("name", ""),
                    "arguments": item.get("arguments", {}),
                }
            )

    for call in calls:
        call_id = call.get("tool_call_id", "")
        if call_id in results_by_id:
            call["results"] = results_by_id[call_id]

    return calls


def _extract_agent_data_from_workflow(
    result: WorkflowResult,
    converter: Any,
) -> list[dict[str, object]]:
    """Fallback extractor that reconstructs evaluator payloads from workflow events."""

    raw_result = result.raw_result
    if raw_result is None or not isinstance(raw_result, Iterable):
        return []

    extracted: list[dict[str, object]] = []
    for event in raw_result:
        if getattr(event, "type", None) != "executor_completed":
            continue

        executor_id = str(getattr(event, "executor_id", "") or "")
        payload = getattr(event, "data", None)
        if not isinstance(payload, list):
            continue

        for item in payload:
            messages = getattr(item, "messages", None)
            if not messages:
                continue

            try:
                conversation = _normalize_conversation_messages(converter.convert_messages(list(messages)))
            except Exception as exc:  # pragma: no cover - defensive guard for conversion issues
                logger.debug("Failed to convert workflow messages for executor %s: %s", executor_id, exc)
                conversation = []

            tool_names = list(getattr(item, "tool_names", ()) or ())
            tool_calls = _extract_tool_calls_from_conversation(conversation, executor_id) if conversation else []
            extracted.append(
                {
                    "executor_id": executor_id,
                    "conversation": conversation,
                    "tool_names": tool_names,
                    "tool_calls": tool_calls,
                }
            )

    return extracted


async def generate_eval_data(
    input_path: str | Path = GOLDEN_QUESTIONS_PATH,
    output_path: str | Path = EVAL_DATA_PATH,
) -> int:
    """Run agent on golden questions and write evaluation data."""

    from agent_framework import AgentEvalConverter
    from agent_framework._evaluation import _extract_agent_eval_data  # type: ignore[attr-defined]

    from maf_graphrag.workflows.router_agent import RouterWorkflowAgentAdapter

    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Golden questions file not found: {input_path}")

    # Load test cases using a thread so the async event loop is not blocked
    def _read_jsonl(path: Path) -> list[dict]:
        with open(path, encoding="utf-8") as fh:
            return [json.loads(line.strip()) for line in fh if line.strip()]

    test_cases: list[dict] = await asyncio.to_thread(_read_jsonl, input_path)
    logger.info("Loaded %d test cases from %s", len(test_cases), input_path)

    records: list[str] = []
    adapter = RouterWorkflowAgentAdapter()
    for index, case in enumerate(test_cases, 1):
        query = case["query"]
        logger.info("[%d/%d] Processing: %s", index, len(test_cases), query)

        result = await adapter.run(query)

        router_metadata = _extract_router_metadata(result)
        agent_turns, tool_definitions, tool_calls = _extract_agent_turn_payloads(
            result,
            AgentEvalConverter,
            _extract_agent_eval_data,
        )

        conversation = agent_turns[-1]["conversation"] if agent_turns else []

        eval_record = {
            "query": query,
            "response_text": result.answer,
            "conversation": conversation,
            "response": result.answer,
            "agent_turns": agent_turns,
            "ground_truth": case.get("ground_truth", ""),
            "tool_definitions": tool_definitions,
            "tool_calls": tool_calls,
            "expected_tools": case.get("expected_tools", []),
            "routed_workflow": router_metadata.get("routed_workflow"),
            "classified_workflow": router_metadata.get("classified_workflow"),
            "route_metadata": router_metadata,
        }

        records.append(json.dumps(eval_record, ensure_ascii=False) + "\n")

    processed = len(records)

    def _write_jsonl(path: Path, lines: list[str]) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(lines)

    await asyncio.to_thread(_write_jsonl, output_path, records)

    logger.info("Wrote %d evaluation records to %s", processed, output_path)
    return processed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    # Suppress noisy loggers
    for name in ("litellm", "httpx", "httpcore", "openai", "azure", "mcp", "agent_framework", "asyncio"):
        logging.getLogger(name).setLevel(logging.ERROR)

    count = asyncio.run(generate_eval_data())
    print(f"\nGenerated {count} evaluation records in {EVAL_DATA_PATH}")
