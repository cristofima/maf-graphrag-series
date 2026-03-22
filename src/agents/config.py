"""
Agent Configuration.

Configuration management for Microsoft Agent Framework agents.
Supports multiple LLM providers: Azure OpenAI, GitHub Models, OpenAI, and Ollama.
Validates required environment variables and provides typed configuration.
"""

import os
from dataclasses import dataclass, field
from typing import Literal

ApiHost = Literal["azure", "github", "openai", "ollama"]
"""Supported LLM provider backends."""

# Default base URLs per provider
_PROVIDER_BASE_URLS: dict[str, str] = {
    "github": "https://models.github.ai/inference",
    "ollama": "http://localhost:11434/v1/",
}


@dataclass
class AgentConfig:
    """Configuration for Agent Framework agents.

    Supports Azure OpenAI (default), GitHub Models, OpenAI, and Ollama.

    Loads configuration from environment variables with validation.
    Required environment variables (Azure — default):
        - AZURE_OPENAI_ENDPOINT: Azure OpenAI service endpoint
        - AZURE_OPENAI_API_KEY: Azure OpenAI API key (optional if using Azure CLI credential)
        - AZURE_OPENAI_CHAT_DEPLOYMENT: Deployment name for chat model (default: gpt-4o)

    Alternative provider env vars:
        - API_HOST: Provider name — 'azure' (default), 'github', 'openai', 'ollama'
        - GITHUB_TOKEN: GitHub personal access token (when API_HOST=github)
        - GITHUB_MODEL: Model ID for GitHub Models (default: openai/gpt-4.1-mini)
        - OPENAI_API_KEY: OpenAI API key (when API_HOST=openai)
        - OPENAI_MODEL: Model ID for OpenAI (default: gpt-4o)
        - OLLAMA_MODEL: Model ID for Ollama (default: llama3.2)

    Optional environment variables:
        - MCP_SERVER_URL: GraphRAG MCP server URL (default: http://127.0.0.1:8011/mcp)

    Attributes:
        api_host: LLM provider backend
        azure_endpoint: Azure OpenAI endpoint URL (Azure only)
        deployment_name: Chat model deployment name (Azure only)
        api_key: API key for the selected provider
        api_version: Azure OpenAI API version (Azure only)
        mcp_server_url: GraphRAG MCP server URL
        auth_method: Authentication method ('api_key' or 'azure_cli')
        github_token: GitHub personal access token (GitHub Models)
        github_model: Model ID for GitHub Models
        openai_model: Model ID for OpenAI
        ollama_model: Model ID for Ollama
    """

    api_host: ApiHost = field(default_factory=lambda: os.getenv("API_HOST", "azure"))  # type: ignore[arg-type,return-value]
    azure_endpoint: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", ""))
    deployment_name: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o"))
    api_key: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", ""))
    api_version: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"))
    mcp_server_url: str = field(default_factory=lambda: os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8011/mcp"))
    auth_method: Literal["api_key", "azure_cli"] = field(default="api_key")
    github_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    github_model: str = field(default_factory=lambda: os.getenv("GITHUB_MODEL", "openai/gpt-4.1-mini"))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.2"))

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.api_host == "azure":
            if not self.azure_endpoint:
                raise ValueError(
                    "AZURE_OPENAI_ENDPOINT environment variable is required. Set it to your Azure OpenAI endpoint URL."
                )
            # Determine auth method based on API key availability
            if not self.api_key:
                self.auth_method = "azure_cli"
        elif self.api_host == "github":
            if not self.github_token:
                raise ValueError("GITHUB_TOKEN environment variable is required when API_HOST=github.")
        elif self.api_host == "openai":
            if not self.api_key and not os.getenv("OPENAI_API_KEY", ""):
                raise ValueError("OPENAI_API_KEY environment variable is required when API_HOST=openai.")
            if not self.api_key:
                self.api_key = os.getenv("OPENAI_API_KEY", "")

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create configuration from environment variables.

        Returns:
            AgentConfig: Validated configuration instance

        Raises:
            ValueError: If required environment variables are missing
        """
        from dotenv import load_dotenv

        load_dotenv()
        return cls()

    @property
    def uses_azure_cli(self) -> bool:
        """Check if using Azure CLI credential for authentication."""
        return self.api_host == "azure" and self.auth_method == "azure_cli"

    @property
    def model_id(self) -> str:
        """Return the model identifier for the configured provider."""
        if self.api_host == "azure":
            return self.deployment_name
        if self.api_host == "github":
            return self.github_model
        if self.api_host == "ollama":
            return self.ollama_model
        return self.openai_model

    @property
    def provider_api_key(self) -> str:
        """Return the API key for the configured provider."""
        if self.api_host == "azure":
            return self.api_key
        if self.api_host == "github":
            return self.github_token
        if self.api_host == "ollama":
            return "unused"
        return self.api_key

    @property
    def provider_base_url(self) -> str | None:
        """Return the base URL for the configured provider, or None for OpenAI default."""
        if self.api_host == "azure":
            return f"{self.azure_endpoint.rstrip('/')}/openai/v1/"
        return _PROVIDER_BASE_URLS.get(self.api_host)

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


def is_azure(config: AgentConfig | None = None) -> bool:
    """Check if the configured provider is Azure OpenAI.

    Args:
        config: Optional config instance; loads from env if not provided.

    Returns:
        True when api_host is 'azure'.
    """
    cfg = config or get_agent_config()
    return cfg.api_host == "azure"
