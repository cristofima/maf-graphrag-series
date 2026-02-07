"""
Local Search MCP Tool

Entity-focused search for specific questions about entities and relationships.
Best for: "Who leads Project Alpha?", "What technologies does X use?"
"""

from core import load_all, local_search
from mcp_server.tools.source_resolver import get_unique_documents, resolve_sources


async def local_search_tool(
    query: str,
    community_level: int | None = None,
    response_type: str | None = None
) -> dict:
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
    try:
        # Load knowledge graph
        data = load_all()
        
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
    
    except FileNotFoundError as e:
        return {
            "error": f"Knowledge graph not found. Run indexing first: poetry run python -m core.index",
            "details": str(e)
        }
    except Exception as e:
        return {
            "error": f"Local search failed: {str(e)}",
            "query": query
        }
