"""
GraphRAG MCP Server

FastMCP server that exposes GraphRAG tools via HTTP/SSE for MCP-compatible clients.

Usage:
    # Development
    poetry run python -m mcp_server.server
    
    # Production (with uvicorn)
    poetry run uvicorn mcp_server.server:app --host 0.0.0.0 --port 8011
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP
from mcp_server.config import MCPConfig
from mcp_server.tools import local_search_tool, global_search_tool, entity_query_tool


# Initialize configuration
config = MCPConfig.from_env()

# Create FastMCP server (fastmcp 0.2.0 only accepts 'name' parameter)
mcp = FastMCP(name=config.server_name)


@mcp.tool()
async def search_knowledge_graph(
    query: str,
    search_type: str = "local",
    community_level: int = 2,
    response_type: str = "Multiple Paragraphs"
) -> dict:
    """
    Search the GraphRAG knowledge graph.
    
    This is the main entry point for GraphRAG queries. It routes to local or global search
    based on the search_type parameter.
    
    Args:
        query: The question to answer
        search_type: "local" for entity-focused or "global" for thematic search
        community_level: Community hierarchy level (0-2, higher = smaller communities)
        response_type: Format of response
    
    Returns:
        dict: Search results with answer, context, and sources
    """
    if search_type.lower() == "local":
        return await local_search_tool(
            query=query,
            community_level=community_level,
            response_type=response_type
        )
    elif search_type.lower() == "global":
        return await global_search_tool(
            query=query,
            community_level=community_level,
            response_type=response_type
        )
    else:
        return {
            "error": f"Invalid search_type: {search_type}. Must be 'local' or 'global'"
        }


@mcp.tool()
async def local_search(
    query: str,
    community_level: int = 2,
    response_type: str = "Multiple Paragraphs"
) -> dict:
    """
    Perform entity-focused search on the knowledge graph.
    
    Best for specific questions about entities and relationships:
    - "Who leads Project Alpha?"
    - "What technologies are used in Project Beta?"
    - "Who resolved the GraphRAG incident?"
    
    Args:
        query: The question to answer
        community_level: Community hierarchy level (0-2)
        response_type: Format of response
    
    Returns:
        dict: Search results with answer and context
    """
    return await local_search_tool(query, community_level, response_type)


@mcp.tool()
async def global_search(
    query: str,
    community_level: int = 2,
    response_type: str = "Multiple Paragraphs"
) -> dict:
    """
    Perform thematic search across the entire knowledge graph.
    
    Best for broad organizational questions:
    - "What are the main projects?"
    - "Summarize the organizational structure"
    - "What Azure services are used?"
    
    Args:
        query: The question to answer
        community_level: Community hierarchy level (0-2)
        response_type: Format of response
    
    Returns:
        dict: Search results with answer and context
    """
    return await global_search_tool(query, community_level, response_type, dynamic_community_selection=True)


@mcp.tool()
async def list_entities(
    entity_type: str = None,
    limit: int = 10
) -> dict:
    """
    List entities from the knowledge graph.
    
    Args:
        entity_type: Filter by type (e.g., "person", "organization", "project")
        limit: Maximum number of entities to return
    
    Returns:
        dict: List of entities with details
    """
    return await entity_query_tool(entity_type=entity_type, limit=limit)


@mcp.tool()
async def get_entity(entity_name: str) -> dict:
    """
    Get details about a specific entity.
    
    Args:
        entity_name: Name of the entity to look up
    
    Returns:
        dict: Entity details
    """
    return await entity_query_tool(entity_name=entity_name, limit=1)


def create_mcp_server() -> FastMCP:
    """Create and return configured MCP server instance"""
    return mcp


# Starlette app for deployment (SSE transport)
# sse_app() is a method that returns a Starlette app with /sse and /messages/ routes
app = mcp.sse_app()

# Add CORS middleware so MCP Inspector (browser) can connect cross-origin
from starlette.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    # Development server
    print(f"🚀 Starting GraphRAG MCP Server")
    print(f"   Server: {config.server_name} v{config.server_version}")
    print(f"   URL: {config.server_url}")
    print(f"   GraphRAG Root: {config.graphrag_root}")
    print(f"\n📋 Available Tools:")
    print(f"   - search_knowledge_graph(query, search_type='local|global')")
    print(f"   - local_search(query)")
    print(f"   - global_search(query)")
    print(f"   - list_entities(entity_type, limit)")
    print(f"   - get_entity(entity_name)")
    print(f"\n✨ Server ready for MCP Inspector or agent connections")
    print(f"\n🔗 Connect with MCP Inspector:")
    print(f"   Transport: SSE")
    print(f'   URL: {config.server_url}/sse')
    
    # Run with uvicorn
    import uvicorn
    uvicorn.run(app, host=config.host, port=config.port)
