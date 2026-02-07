"""
MCP Server for GraphRAG - Part 2 of MAF + GraphRAG Series

This module exposes GraphRAG functionality as MCP (Model Context Protocol) tools,
enabling AI agents and MCP clients to query knowledge graphs.

Usage:
    # Start MCP server
    poetry run python -m mcp_server.server
    
    # Or use convenience script
    poetry run python run_mcp_server.py
"""

from mcp_server.config import MCPConfig
from mcp_server.server import create_mcp_server

__all__ = ["MCPConfig", "create_mcp_server"]
