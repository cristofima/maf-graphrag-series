"""
MCP Server for GraphRAG - Part 2 of MAF + GraphRAG Series

This module exposes GraphRAG functionality as MCP (Model Context Protocol) tools,
enabling AI agents and MCP clients to query knowledge graphs.

Usage:
    # Start MCP server
    uv run python -m maf_graphrag.mcp_server.server

    # Or use convenience script
    uv run python run_mcp_server.py
"""

from maf_graphrag.mcp_server.config import MCPConfig
from maf_graphrag.mcp_server.server import create_mcp_server

__all__ = ["MCPConfig", "create_mcp_server"]
