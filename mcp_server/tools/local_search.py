"""
Local Search MCP Tool

Entity-focused search for specific questions about entities and relationships.
Best for: "Who leads Project Alpha?", "What technologies does X use?"
"""

from core import load_all, local_search


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
        
        return {
            "answer": response,
            "context": {
                "entities_used": len(context.entities) if hasattr(context, 'entities') else 0,
                "relationships_used": len(context.relationships) if hasattr(context, 'relationships') else 0,
                "reports_used": len(context.reports) if hasattr(context, 'reports') else 0,
            },
            "sources": context.sources if hasattr(context, 'sources') else [],
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
