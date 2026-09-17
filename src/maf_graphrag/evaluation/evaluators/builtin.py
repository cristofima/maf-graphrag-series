"""
GraphRAG tool definitions shared by Foundry tool-aware evaluators.

``GRAPHRAG_TOOL_DEFINITIONS`` is consumed by ``generate_eval_data.py`` as the
fallback tool schema (name/description/parameters) for tool-focused evaluators
(``tool_call_accuracy``, ``tool_selection``, etc.) run through
``agent_framework_foundry.FoundryEvals``.
"""

from __future__ import annotations

from typing import Any

_QUERY_DESC = "The question to answer"
_COMMUNITY_LEVEL_DESC = "Community hierarchy level (0-2)"
_RESPONSE_TYPE_DESC = "Format of response"

# MCP tool definitions for the GraphRAG server
# Used by tool-focused evaluators (ToolCallAccuracy, ToolSelection, etc.)
GRAPHRAG_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "search_knowledge_graph",
        "description": "Search the GraphRAG knowledge graph. Routes to local or global search.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": _QUERY_DESC},
                "search_type": {
                    "type": "string",
                    "description": "local for entity-focused or global for thematic search",
                    "enum": ["local", "global"],
                },
                "community_level": {"type": "integer", "description": _COMMUNITY_LEVEL_DESC},
                "response_type": {"type": "string", "description": _RESPONSE_TYPE_DESC},
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
                "query": {"type": "string", "description": _QUERY_DESC},
                "community_level": {"type": "integer", "description": _COMMUNITY_LEVEL_DESC},
                "response_type": {"type": "string", "description": _RESPONSE_TYPE_DESC},
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
                "query": {"type": "string", "description": _QUERY_DESC},
                "community_level": {"type": "integer", "description": _COMMUNITY_LEVEL_DESC},
                "response_type": {"type": "string", "description": _RESPONSE_TYPE_DESC},
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
