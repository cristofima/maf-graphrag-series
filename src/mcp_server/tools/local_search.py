"""
Local Search MCP Tool

Entity-focused search for specific questions about entities and relationships.
Best for: "Who leads Project Alpha?", "What technologies does X use?"
"""

from core import local_search

from mcp_server.tools._data_cache import get_graph_data

from mcp_server.tools.source_resolver import get_unique_documents, resolve_sources
from mcp_server.tools.types import SearchResult, ToolError, handle_tool_errors, validate_community_level, validate_query


@handle_tool_errors("Local search")
async def local_search_tool(
    query: str,
    community_level: int | None = None,
    response_type: str | None = None
) -> SearchResult | ToolError:
    """
    Search the knowledge graph for specific entities and relationships.

    This tool performs entity-focused search using vector similarity to find
    relevant entities, then traverses the graph to gather connected information.

    Args:
        query: The question to answer (e.g., "Who leads Project Alpha?")
        community_level: Community hierarchy level (0-2, higher = smaller communities)
        response_type: Format of response ("Multiple Paragraphs", "Single Paragraph", etc.)

    Returns:
        dict: Contains 'answer', 'context', and 'sources'

    Examples:
        - "Who leads Project Alpha?"
        - "What technologies are used in Project Beta?"
        - "What is the relationship between David Kumar and Sophia Lee?"
        - "Who resolved the GraphRAG incident?"
    """
    # Validate inputs at system boundary
    if err := validate_query(query):
        return err
    if err := validate_community_level(community_level):
        return err

    # Load knowledge graph (cached after first call)
    data = get_graph_data()

    # Perform local search
    response, context = await local_search(
        query=query,
        data=data,
        community_level=community_level or 2,
        response_type=response_type or "Multiple Paragraphs"
    )

    # GraphRAG 3.x returns context as dict[str, pd.DataFrame]
    ctx = context if isinstance(context, dict) else {}
    entities_df = ctx.get("entities")
    relationships_df = ctx.get("relationships")
    reports_df = ctx.get("reports")
    sources_df = ctx.get("sources")

    # Resolve sources to document titles and text previews
    resolved_sources = resolve_sources(sources_df, data)

    return {
        "answer": response,
        "context": {
            "entities_used": len(entities_df) if entities_df is not None else 0,
            "relationships_used": len(relationships_df) if relationships_df is not None else 0,
            "reports_used": len(reports_df) if reports_df is not None else 0,
            "documents": get_unique_documents(resolved_sources),
        },
        "sources": resolved_sources,
        "search_type": "local"
    }
