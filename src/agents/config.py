"""Agent configuration tuned for Microsoft Foundry model router deployments."""

from __future__ import annotations

import os
from datetime import date

from pydantic import AnyHttpUrl, BaseModel, Field, FieldValidationInfo, ValidationError, field_validator, model_validator


DEFAULT_API_VERSION = "2024-11-20"
"""Default REST API version aligned with the current deployment guidance."""

class AgentConfig(BaseModel):
    """Agent configuration backed by Pydantic validation.

    The project targets Microsoft Foundry exclusively. All chat traffic flows
    through a Foundry model router deployment which optimizes model selection per
    request. Only Azure-hosted endpoints are supported; GitHub Models, OpenAI
    public endpoints, and Ollama are no longer available.
    """

    azure_endpoint: AnyHttpUrl = Field(..., description="Foundry endpoint base URL")
    deployment_name: str = Field(..., description="Primary chat deployment name")
    router_deployment: str = Field(..., description="Dedicated router deployment name")
    api_key: str | None = Field(default=None, description="API key for Foundry access")
    api_version: str = Field(default=DEFAULT_API_VERSION, description="REST API version for primary deployment")
    mcp_server_url: AnyHttpUrl = Field(default="http://127.0.0.1:8011/mcp", description="GraphRAG MCP server URL")
    router_subset: str | None = Field(default=None, description="Optional router subset identifier")
    router_endpoint: AnyHttpUrl | None = Field(
        default=None,
        description="Override base URL for router traffic",
    )

    @field_validator("deployment_name", "router_deployment")
    @classmethod
    def _ensure_non_empty(cls, value: str, info: FieldValidationInfo) -> str:
        if not value or not value.strip():
            raise ValueError(f"{info.field_name.upper()} must be provided")
        return value.strip()

    @field_validator("api_version")
    @classmethod
    def _validate_version(cls, value: str, info: FieldValidationInfo) -> str:
        stripped = value.strip()
        try:
            date.fromisoformat(stripped)
        except ValueError as exc:  # pragma: no cover - defensive guard for env typos
            raise ValueError(f"{info.field_name.upper()} must use YYYY-MM-DD format") from exc
        return stripped

    @model_validator(mode="after")
    def _apply_router_defaults(self) -> "AgentConfig":
        if self.router_endpoint is None:
            self.router_endpoint = self.azure_endpoint
        return self

    @property
    def router_base_url(self) -> str:
        """Return normalized base URL for router traffic."""

        return str(self.router_endpoint).rstrip("/")  # type: ignore[arg-type]

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create configuration from environment variables with strict validation."""

        from dotenv import load_dotenv

        keys_to_preserve = (
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_CHAT_DEPLOYMENT",
            "AZURE_OPENAI_ROUTER_DEPLOYMENT",
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_API_VERSION",
            "MCP_SERVER_URL",
            "AZURE_OPENAI_ROUTER_SUBSET",
            "AZURE_OPENAI_ROUTER_ENDPOINT",
        )
        preserved = {key: os.environ.get(key) for key in keys_to_preserve}

        load_dotenv(override=True)

        for key, value in preserved.items():
            if value is not None:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)
        data = {
            "azure_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
            "deployment_name": os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
            "router_deployment": os.getenv("AZURE_OPENAI_ROUTER_DEPLOYMENT"),
            "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
            "api_version": os.getenv("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION),
            "mcp_server_url": os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8011/mcp"),
            "router_subset": os.getenv("AZURE_OPENAI_ROUTER_SUBSET") or None,
            "router_endpoint": os.getenv("AZURE_OPENAI_ROUTER_ENDPOINT"),
        }

        try:
            return cls(**data)
        except ValidationError as exc:  # pragma: no cover - defensive guard
            raise ValueError(str(exc)) from exc

    @property
    def uses_azure_cli(self) -> bool:
        """Return True when Azure CLI authentication should be used."""

        return self.api_key is None or self.api_key.strip() == ""

    @property
    def azure_base_url(self) -> str:
        """Return the OpenAI-compatible base URL for the configured endpoint."""

        return f"{str(self.azure_endpoint).rstrip('/')}/openai/v1/"

    @property
    def router_model(self) -> str:
        """Return the deployment name dedicated to model routing."""

        return self.router_deployment

    def validate_mcp_server(self) -> bool:
        """Return True when the MCP server URL looks valid."""

        return self.mcp_server_url.startswith("http")


def get_agent_config() -> AgentConfig:
    """Get validated agent configuration from environment."""

    return AgentConfig.from_env()

