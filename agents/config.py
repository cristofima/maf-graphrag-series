"""
Agent Configuration

Configuration management for Microsoft Agent Framework agents with Azure OpenAI.
Validates required environment variables and provides typed configuration.
"""

import os
from dataclasses import dataclass, field
from typing import Literal

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class AgentConfig:
    """Configuration for Agent Framework agents with Azure OpenAI.
    
    Loads configuration from environment variables with validation.
    Required environment variables:
        - AZURE_OPENAI_ENDPOINT: Azure OpenAI service endpoint
        - AZURE_OPENAI_API_KEY: Azure OpenAI API key (optional if using Azure CLI credential)
        - AZURE_OPENAI_CHAT_DEPLOYMENT: Deployment name for chat model (default: gpt-4o)
    
    Optional environment variables:
        - MCP_SERVER_URL: GraphRAG MCP server URL (default: http://127.0.0.1:8011/mcp)
    
    Attributes:
        azure_endpoint: Azure OpenAI endpoint URL
        deployment_name: Chat model deployment name
        api_key: Azure OpenAI API key (empty string if using Azure CLI)
        api_version: Azure OpenAI API version
        mcp_server_url: GraphRAG MCP server URL
        auth_method: Authentication method ('api_key' or 'azure_cli')
    """
    
    azure_endpoint: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", ""))
    deployment_name: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o"))
    api_key: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", ""))
    api_version: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"))
    mcp_server_url: str = field(default_factory=lambda: os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8011/mcp"))
    auth_method: Literal["api_key", "azure_cli"] = field(default="api_key")
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.azure_endpoint:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT environment variable is required. "
                "Set it to your Azure OpenAI endpoint URL."
            )
        
        # Determine auth method based on API key availability
        if not self.api_key:
            self.auth_method = "azure_cli"
    
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create configuration from environment variables.
        
        Returns:
            AgentConfig: Validated configuration instance
            
        Raises:
            ValueError: If required environment variables are missing
        """
        return cls()
    
    @property
    def uses_azure_cli(self) -> bool:
        """Check if using Azure CLI credential for authentication."""
        return self.auth_method == "azure_cli"
    
    def validate_mcp_server(self) -> bool:
        """Check if MCP server URL is configured.
        
        Returns:
            bool: True if MCP server URL is set and valid
        """
        return bool(self.mcp_server_url) and self.mcp_server_url.startswith("http")


def get_agent_config() -> AgentConfig:
    """Get validated agent configuration from environment.
    
    This is the recommended entry point for loading configuration.
    
    Returns:
        AgentConfig: Validated configuration instance
        
    Raises:
        ValueError: If required environment variables are missing
    """
    return AgentConfig.from_env()
