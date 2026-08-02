"""MCP Server configuration backed by Pydantic validation."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


DEFAULT_CORS_ORIGINS = ["http://127.0.0.1:8011"]
DEFAULT_CORS_METHODS = ["GET", "POST", "DELETE", "OPTIONS"]
DEFAULT_CORS_HEADERS = ["Content-Type", "Authorization"]


class MCPConfig(BaseModel):
    """Configuration object for the GraphRAG MCP server."""

    host: str = Field(default="127.0.0.1", description="Hostname for the MCP server")
    port: int = Field(default=8011, description="Port for the MCP server")
    server_name: str = Field(default="graphrag-mcp", description="Logical server name")
    server_version: str = Field(default="1.0.0", description="Server semantic version")
    graphrag_root: Path = Field(default_factory=lambda: Path("."), description="Root path for GraphRAG assets")
    output_dir: Path = Field(default_factory=lambda: Path("output"), description="Output directory for GraphRAG")
    default_community_level: int = Field(default=2, ge=0, description="Default community level for search")
    default_response_type: str = Field(default="Multiple Paragraphs", description="Response type override")
    cors_origins: list[str] = Field(default_factory=lambda: DEFAULT_CORS_ORIGINS.copy())
    cors_methods: list[str] = Field(default_factory=lambda: DEFAULT_CORS_METHODS.copy())
    cors_headers: list[str] = Field(default_factory=lambda: DEFAULT_CORS_HEADERS.copy())

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return value
        raise ValueError("cors_origins must be provided as a comma-separated string or list")

    @field_validator("graphrag_root", mode="before")
    @classmethod
    def _coerce_root(cls, value: object) -> Path:
        if isinstance(value, Path):
            return value.resolve()
        if isinstance(value, str) and value:
            return Path(value).resolve()
        return Path(".").resolve()

    @model_validator(mode="after")
    def _align_output_dir(self) -> "MCPConfig":
        if not self.output_dir.is_absolute():
            self.output_dir = (self.graphrag_root / self.output_dir).resolve()
        return self

    @classmethod
    def from_env(cls) -> "MCPConfig":
        """Create configuration from environment variables with validation."""

        data = {
            "host": os.getenv("MCP_HOST", "127.0.0.1"),
            "port": os.getenv("MCP_PORT", "8011"),
            "graphrag_root": os.getenv("GRAPHRAG_ROOT", "."),
            "cors_origins": os.getenv("MCP_CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS)),
        }

        try:
            return cls(**data)
        except ValidationError as exc:  # pragma: no cover - defensive guard
            raise ValueError(str(exc)) from exc

    @property
    def server_url(self) -> str:
        """Full server URL."""

        return f"http://{self.host}:{self.port}"
