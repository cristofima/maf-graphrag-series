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
    graphrag_root: Path | None
    output_dir: Path | None = None
    
    # Search defaults
    default_community_level: int = 2
    default_response_type: str = "Multiple Paragraphs"
    
    @classmethod
    def from_env(cls) -> "MCPConfig":
        """Load configuration from environment variables"""
        root = Path(os.getenv("GRAPHRAG_ROOT", "."))
        
        return cls(
            host=os.getenv("MCP_HOST", "127.0.0.1"),
            port=int(os.getenv("MCP_PORT", "8011")),
            graphrag_root=root,
            output_dir=root / "output",
        )
    
    @property
    def server_url(self) -> str:
        """Full server URL"""
        return f"http://{self.host}:{self.port}"
