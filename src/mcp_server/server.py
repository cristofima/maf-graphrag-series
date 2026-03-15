"""
GraphRAG MCP Server

FastMCP server that exposes GraphRAG tools via HTTP/SSE for MCP-compatible clients.

Usage:
    # Development
    poetry run python -m mcp_server.server

    # Production (with uvicorn)
    poetry run uvicorn mcp_server.server:app --host 0.0.0.0 --port 8011
"""

import logging

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from mcp_server.config import MCPConfig
from mcp_server.tools import entity_query_tool, global_search_tool, local_search_tool
from mcp_server.tools.types import EntityQueryResult, SearchResult, ToolError

# ---------------------------------------------------------------------------
# Suppress noisy INFO logs from LiteLLM and GraphRAG internals.
# LiteLLM logs every Azure OpenAI API call at INFO level; global search
# triggers 20+ parallel LLM calls producing massive terminal spam.
# WARNING level preserves actionable messages (e.g. token-limit warnings).
# uvicorn's own access/error logs remain at their configured level.
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.WARNING)
for _logger_name in ("litellm", "graphrag", "httpx", "httpcore", "openai"):
    logging.getLogger(_logger_name).setLevel(logging.WARNING)

# Initialize configuration
config = MCPConfig.from_env()

# Create FastMCP server
mcp = FastMCP(name=config.server_name)


@mcp.tool()
async def search_knowledge_graph(
    query: str, search_type: str = "local", community_level: int = 2, response_type: str = "Multiple Paragraphs"
) -> SearchResult | ToolError:
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
        return await local_search_tool(query=query, community_level=community_level, response_type=response_type)
    elif search_type.lower() == "global":
        return await global_search_tool(query=query, community_level=community_level, response_type=response_type)
    else:
        return ToolError(error=f"Invalid search_type: {search_type}. Must be 'local' or 'global'")


@mcp.tool()
async def local_search(
    query: str, community_level: int = 2, response_type: str = "Multiple Paragraphs"
) -> SearchResult | ToolError:
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
    query: str, community_level: int = 2, response_type: str = "Multiple Paragraphs"
) -> SearchResult | ToolError:
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
async def list_entities(entity_type: str | None = None, limit: int = 10) -> EntityQueryResult | ToolError:
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
async def get_entity(entity_name: str) -> EntityQueryResult | ToolError:
    """
    Get details about a specific entity.

    Args:
        entity_name: Name of the entity to look up

    Returns:
        dict: Entity details
    """
    return await entity_query_tool(entity_name=entity_name, limit=1)


def create_mcp_server() -> FastMCP:
    """Create and return configured MCP server instance."""
    return mcp


# CORS middleware for browser-based and MCP Inspector clients
_cors_middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins or ["http://127.0.0.1:8011"],
        allow_methods=config.cors_methods or ["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=(config.cors_headers or ["Content-Type", "Authorization"])
        + ["mcp-protocol-version", "mcp-session-id"],
        expose_headers=["mcp-session-id"],
    )
]

# ASGI app: Streamable HTTP (for MCPStreamableHTTPTool & MCP Inspector)
app = mcp.http_app(middleware=_cors_middleware)


if __name__ == "__main__":
    # Development server
    print("🚀 Starting GraphRAG MCP Server")
    print(f"   Server: {config.server_name} v{config.server_version}")
    print(f"   URL: {config.server_url}")
    print(f"   GraphRAG Root: {config.graphrag_root}")
    print("\n📋 Available Tools:")
    print("   - search_knowledge_graph(query, search_type='local|global')")
    print("   - local_search(query)")
    print("   - global_search(query)")
    print("   - list_entities(entity_type, limit)")
    print("   - get_entity(entity_name)")
    print("\n✨ Server ready for Agent Framework or MCP clients")
    print("\n🔗 Connect:")
    print(f"   Agent Framework: {config.server_url}/mcp")
    print(f"   MCP Inspector: Transport=Streamable HTTP, URL={config.server_url}/mcp")

    # Run with uvicorn
    import uvicorn

    uvicorn.run(app, host=config.host, port=config.port)
