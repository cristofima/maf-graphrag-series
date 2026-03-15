"""
Entity Query MCP Tool

Direct entity lookup for quick facts about specific entities.
Best for: "List all entities", "Get details about X"
"""

from core.data_loader import list_entity_types

from mcp_server.tools._data_cache import get_graph_data
from mcp_server.tools.types import (
    EntityInfo,
    EntityQueryResult,
    ToolError,
    handle_tool_errors,
    validate_entity_name,
    validate_limit,
)


@handle_tool_errors("Entity query")
async def entity_query_tool(
    entity_name: str | None = None, entity_type: str | None = None, limit: int = 10
) -> EntityQueryResult | ToolError:
    """
    Query entities directly from the knowledge graph.

    This tool provides direct access to entity information without complex reasoning.
    Useful for quick lookups and exploration.

    Args:
        entity_name: Name of specific entity to look up (case-insensitive)
        entity_type: Filter by entity type (e.g., "person", "organization", "project")
        limit: Maximum number of entities to return

    Returns:
        dict: Contains 'entities' list with entity details

    Examples:
        - entity_name="Dr. Emily Harrison" - Get details about specific person
        - entity_type="project" - List all projects
        - No filters - List all entities (limited to 10)
    """
    # Validate inputs at system boundary
    if err := validate_entity_name(entity_name):
        return err
    if err := validate_limit(limit):
        return err

    # Load knowledge graph (cached after first call)
    data = get_graph_data()
    entities_df = data.entities

    # Filter by name if provided
    if entity_name:
        mask = entities_df["title"].str.contains(entity_name, case=False, na=False)
        filtered = entities_df[mask]
    # Filter by type if provided
    elif entity_type:
        mask = entities_df["type"].str.lower() == entity_type.lower()
        filtered = entities_df[mask]
    else:
        filtered = entities_df

    # Limit results
    result_entities = filtered.head(limit)

    # Build response
    entities_list: list[EntityInfo] = []
    for _, row in result_entities.iterrows():
        entities_list.append(
            EntityInfo(
                name=str(row["title"]),
                type=str(row.get("type", "unknown")),
                description=str(row.get("description", "No description available")),
                community_ids=list(row.get("community_ids", [])),
            )
        )

    return {
        "entities": entities_list,
        "total_found": len(filtered),
        "returned": len(entities_list),
        "available_types": list(list_entity_types(data)),
        "query_type": "entity_lookup",
    }
