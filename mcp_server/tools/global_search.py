"""
Global Search MCP Tool

Community-focused search for broad, thematic questions.
Best for: "What are the main projects?", "Summarize the organization"

Note: Global search uses map-reduce over community reports, not individual
text units. It never receives text_units, so source-level document traceability
is not available (by design in GraphRAG).
"""

from core import load_all, global_search


async def global_search_tool(
    query: str,
    community_level: int | None = None,
    response_type: str | None = None,
    dynamic_community_selection: bool = True
) -> dict:
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
    try:
        # Load knowledge graph
        data = load_all()
        
        # Perform global search
        response, context = await global_search(
            query=query,
            data=data,
            community_level=community_level or 2,
            response_type=response_type or "Multiple Paragraphs",
            dynamic_community_selection=dynamic_community_selection
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
            "search_type": "global"
        }
    
    except FileNotFoundError as e:
        return {
            "error": f"Knowledge graph not found. Run indexing first: poetry run python -m core.index",
            "details": str(e)
        }
    except Exception as e:
        return {
            "error": f"Global search failed: {str(e)}",
            "query": query
        }
