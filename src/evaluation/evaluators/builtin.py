"""
Built-in Agent Evaluator Wrappers.

Provides message conversion utilities and wrapper functions for
Azure AI Evaluation SDK built-in agent evaluators.

The key challenge is that MAF uses ``function_call``/``function_result``
internally, but Azure AI Evaluation expects OpenAI-style
``tool_call``/``tool_result`` message schema. The ``convert_to_evaluator_messages``
function handles this remapping.
"""

from __future__ import annotations

from typing import Any

# MCP tool definitions for the GraphRAG server
# Used by tool-focused evaluators (ToolCallAccuracy, ToolSelection, etc.)
GRAPHRAG_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "search_knowledge_graph",
        "description": "Search the GraphRAG knowledge graph. Routes to local or global search.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The question to answer"},
                "search_type": {
                    "type": "string",
                    "description": "local for entity-focused or global for thematic search",
                    "enum": ["local", "global"],
                },
                "community_level": {"type": "integer", "description": "Community hierarchy level (0-2)"},
                "response_type": {"type": "string", "description": "Format of response"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "local_search",
        "description": "Entity-focused search on the knowledge graph. Best for specific entity/relationship questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The question to answer"},
                "community_level": {"type": "integer", "description": "Community hierarchy level (0-2)"},
                "response_type": {"type": "string", "description": "Format of response"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "global_search",
        "description": "Thematic search across the entire knowledge graph. Best for broad organizational questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The question to answer"},
                "community_level": {"type": "integer", "description": "Community hierarchy level (0-2)"},
                "response_type": {"type": "string", "description": "Format of response"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_entities",
        "description": "List entities from the knowledge graph.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {"type": "string", "description": "Filter by type (person, organization, project)"},
                "limit": {"type": "integer", "description": "Maximum number of entities to return"},
            },
        },
    },
    {
        "name": "get_entity",
        "description": "Get details about a specific entity.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_name": {"type": "string", "description": "Name of the entity to look up"},
            },
            "required": ["entity_name"],
        },
    },
]


def convert_to_evaluator_messages(messages: list[Any]) -> list[dict[str, Any]]:
    """Convert MAF agent thread messages to OpenAI-style evaluator message schema.

    The Azure AI Evaluation SDK expects messages in the OpenAI tool_call/tool_result
    format, while MAF uses function_call/function_result internally.

    Args:
        messages: List of MAF message objects from an AgentThread.

    Returns:
        List of dicts in OpenAI-style message format suitable for evaluation.
    """
    evaluator_messages: list[dict[str, Any]] = []

    for msg in messages:
        role = getattr(msg, "role", None)
        if role is None:
            continue

        role_str = str(role).lower().replace("messagerole.", "")

        if role_str == "user":
            text = _extract_text(msg)
            evaluator_messages.append({"role": "user", "content": text})

        elif role_str == "assistant":
            content_items = _extract_assistant_content(msg)
            if content_items:
                evaluator_messages.append({"role": "assistant", "content": content_items})

        elif role_str == "tool":
            tool_call_id = getattr(msg, "tool_call_id", None) or "unknown"
            text = _extract_text(msg)
            evaluator_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": [{"type": "tool_result", "tool_result": text}],
                }
            )

    return evaluator_messages


def _extract_text(msg: Any) -> str:
    """Extract text content from a MAF message."""
    # Try .text attribute first (rc5+)
    if hasattr(msg, "text") and msg.text:
        return str(msg.text)

    # Try .content attribute
    if hasattr(msg, "content"):
        content = msg.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, str):
                    texts.append(item)
                elif hasattr(item, "text"):
                    texts.append(str(item.text))
            return " ".join(texts) if texts else ""

    return ""


def _extract_assistant_content(msg: Any) -> list[dict[str, Any]]:
    """Extract assistant content including tool calls from a MAF message."""
    items: list[dict[str, Any]] = []

    # Check for items/content list (may contain tool calls)
    content = getattr(msg, "content", None) or getattr(msg, "items", None) or []
    if isinstance(content, str):
        return [{"type": "text", "text": content}]

    for item in content if isinstance(content, list) else []:
        item_type = getattr(item, "type", None)

        if item_type == "function_call" or hasattr(item, "call_id"):
            # MAF function_call → OpenAI tool_call
            call_id = getattr(item, "call_id", None) or getattr(item, "id", "")
            name = getattr(item, "name", "")
            arguments = getattr(item, "arguments", {})
            items.append(
                {
                    "type": "tool_call",
                    "tool_call": {
                        "id": str(call_id),
                        "type": "function",
                        "function": {"name": str(name), "arguments": arguments if isinstance(arguments, dict) else {}},
                    },
                }
            )
        elif hasattr(item, "text"):
            items.append({"type": "text", "text": str(item.text)})

    # If no items extracted, try plain text
    if not items:
        text = _extract_text(msg)
        if text:
            items.append({"type": "text", "text": text})

    return items


def create_quality_evaluators(model_config: dict[str, str]) -> dict[str, Any]:
    """Create a dict of quality evaluators for batch evaluation.

    Uses Azure OpenAI as LLM-judge — no Azure AI Foundry project required.

    Args:
        model_config: Dict with azure_endpoint, api_key, azure_deployment.

    Returns:
        Dict mapping evaluator names to evaluator instances.
    """
    from azure.ai.evaluation import (
        CoherenceEvaluator,
        IntentResolutionEvaluator,
        RelevanceEvaluator,
        ResponseCompletenessEvaluator,
        TaskAdherenceEvaluator,
        ToolCallAccuracyEvaluator,
    )

    return {
        "task_adherence": TaskAdherenceEvaluator(model_config=model_config),
        "intent_resolution": IntentResolutionEvaluator(model_config=model_config),
        "relevance": RelevanceEvaluator(model_config=model_config),
        "coherence": CoherenceEvaluator(model_config=model_config),
        "response_completeness": ResponseCompletenessEvaluator(model_config=model_config),
        "tool_call_accuracy": ToolCallAccuracyEvaluator(model_config=model_config),
    }


def run_single_evaluation(
    evaluator: Any,
    *,
    query: str,
    response: str | list[dict[str, Any]],
    tool_definitions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run a single evaluator on one query-response pair.

    Args:
        evaluator: An initialized evaluator instance.
        query: The user query.
        response: The agent response (string or conversation array).
        tool_definitions: Optional tool definitions for tool-focused evaluators.

    Returns:
        Dict with evaluation scores and details.
    """
    kwargs: dict[str, Any] = {"query": query, "response": response}
    if tool_definitions is not None:
        kwargs["tool_definitions"] = tool_definitions
    return evaluator(**kwargs)
