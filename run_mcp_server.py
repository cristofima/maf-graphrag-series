"""
Run MCP Server Convenience Script

Start the GraphRAG MCP Server for knowledge graph queries via HTTP/SSE.

Usage:
    uv run python run_mcp_server.py

Environment Variables:
    MCP_HOST - Server host (default: 127.0.0.1)
    MCP_PORT - Server port (default: 8011)
    GRAPHRAG_ROOT - Root directory for GraphRAG (default: .)
    APP_LOG_MAX_BYTES - Rotation size in bytes (default: 10485760)
    APP_LOG_BACKUP_COUNT - Number of rotated backups (default: 5)
"""

import logging
import sys
from pathlib import Path

# Add src/ to path for package imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

if __name__ == "__main__":
    # Import here to avoid loading before path is set
    import uvicorn

    from maf_graphrag.core.logging_config import LoggingConfig, configure_app_logging
    from maf_graphrag.mcp_server.server import app, config

    logging_config = LoggingConfig.from_env(default_app_log_level="INFO", default_noisy_log_level="WARNING")
    configure_app_logging(config=logging_config)
    uvicorn_log_level = "info"
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    print("🚀 Starting GraphRAG MCP Server")
    print(f"   Server: {config.server_name} v{config.server_version}")
    print(f"   URL: {config.server_url}")
    print(f"   GraphRAG Root: {config.graphrag_root}")
    print("\n✨ Press Ctrl+C to stop")
    logging.getLogger(__name__).info("Starting GraphRAG MCP Server on %s:%s", config.host, config.port)

    # ws="none" disables WebSocket protocol — not needed for Streamable HTTP/SSE
    # and avoids DeprecationWarnings from the websockets legacy API.
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level=uvicorn_log_level,
        ws="none",
        log_config=None,
    )
