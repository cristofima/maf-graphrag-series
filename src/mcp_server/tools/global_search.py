"""
Global Search MCP Tool

Community-focused search for broad, thematic questions.
Best for: "What are the main projects?", "Summarize the organization"

Note: Global search uses map-reduce over community reports, not individual
text units. It never receives text_units, so source-level document traceability
is not available (by design in GraphRAG).
"""

from core import global_search

from mcp_server.tools._data_cache import get_graph_data
from mcp_server.tools.types import SearchResult, ToolError, handle_tool_errors, validate_community_level, validate_query


@handle_tool_errors("Global search")
async def global_search_tool(
    query: str,
    community_level: int | None = None,
    response_type: str | None = None,
    dynamic_community_selection: bool = True,
) -> SearchResult | ToolError:
    """
    Search the knowledge graph for broad themes and organizational insights.

    This tool analyzes community reports (summaries of graph communities) to
    provide high-level overviews and thematic insights across the entire organization.

    Args:
        query: The question to answer (e.g., "What are the main projects?")
        community_level: Community hierarchy level (0-2, higher = smaller communities)
        response_type: Format of response ("Multi-Page Report", "Multiple Paragraphs", etc.)
        dynamic_community_selection: Enable dynamic community selection

    Returns:
        dict: Contains 'answer', 'context', and 'search_type'.
              Unlike local search, global search does not return document-level
              sources because it synthesizes from community reports (aggregated summaries).

    Examples:
        - "What are the main projects and teams?"
        - "Summarize the organizational structure"
        - "What engineering processes are used?"
        - "What Azure services are used across the organization?"
    """
    # Validate inputs at system boundary
    if err := validate_query(query):
        return err
    if err := validate_community_level(community_level):
        return err

    # Load knowledge graph (cached after first call)
    data = get_graph_data()

    # Perform global search
    response, context = await global_search(
        query=query,
        data=data,
        community_level=community_level or 2,
        response_type=response_type or "Multiple Paragraphs",
        dynamic_community_selection=dynamic_community_selection,
    )

    # GraphRAG 3.x returns context as dict[str, pd.DataFrame]
    # Global search only returns 'reports' (community reports used)
    ctx = context if isinstance(context, dict) else {}
    reports_df = ctx.get("reports")

    return {
        "answer": response,
        "context": {
            "communities_analyzed": len(reports_df) if reports_df is not None else 0,
        },
        "search_type": "global",
    }
