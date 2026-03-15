"""
MCP Server Configuration

Loads GraphRAG configuration and MCP server settings.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MCPConfig:
    """Configuration for GraphRAG MCP Server"""

    # Server settings
    host: str = "127.0.0.1"
    port: int = 8011
    server_name: str = "graphrag-mcp"
    server_version: str = "1.0.0"

    # GraphRAG settings
    graphrag_root: Path | None = None
    output_dir: Path | None = None

    # Search defaults
    default_community_level: int = 2
    default_response_type: str = "Multiple Paragraphs"

    # CORS settings
    cors_origins: list[str] | None = None
    cors_methods: list[str] | None = None
    cors_headers: list[str] | None = None

    @classmethod
    def from_env(cls) -> "MCPConfig":
        """Load configuration from environment variables.

        Reads MCP_HOST, MCP_PORT, and GRAPHRAG_ROOT from the environment,
        falling back to sensible defaults for local development.

        Returns:
            MCPConfig: Configured instance.
        """
        root = Path(os.getenv("GRAPHRAG_ROOT", "."))

        cors_origins_raw = os.getenv("MCP_CORS_ORIGINS", "http://127.0.0.1:8011")
        cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]

        return cls(
            host=os.getenv("MCP_HOST", "127.0.0.1"),
            port=int(os.getenv("MCP_PORT", "8011")),
            graphrag_root=root,
            output_dir=root / "output",
            cors_origins=cors_origins,
            cors_methods=["GET", "POST", "DELETE", "OPTIONS"],
            cors_headers=["Content-Type", "Authorization"],
        )

    @property
    def server_url(self) -> str:
        """Full server URL."""
        return f"http://{self.host}:{self.port}"
