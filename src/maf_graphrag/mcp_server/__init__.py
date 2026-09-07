"""FastMCP server integration for the MAF + GraphRAG series.

Exports the validated MCP configuration and factory used by runtime entry
points to start the Streamable HTTP server.
"""

from maf_graphrag.mcp_server.config import MCPConfig
from maf_graphrag.mcp_server.server import app, create_mcp_server

__all__ = ["MCPConfig", "create_mcp_server", "app"]
