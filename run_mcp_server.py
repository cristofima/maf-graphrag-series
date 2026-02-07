"""
Run MCP Server Convenience Script

Start the GraphRAG MCP Server for knowledge graph queries via HTTP/SSE.

Usage:
    poetry run python run_mcp_server.py
    
Environment Variables:
    MCP_HOST - Server host (default: 127.0.0.1)
    MCP_PORT - Server port (default: 8011)
    GRAPHRAG_ROOT - Root directory for GraphRAG (default: .)
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    # Import here to avoid loading before path is set
    from mcp_server.server import app, config
    import uvicorn
    
    print(f"🚀 Starting GraphRAG MCP Server")
    print(f"   Server: {config.server_name} v{config.server_version}")
    print(f"   URL: {config.server_url}")
    print(f"   GraphRAG Root: {config.graphrag_root}")
    print(f"\n✨ Press Ctrl+C to stop\\n")
    
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")
