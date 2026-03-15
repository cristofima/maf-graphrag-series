"""Unit tests for agents/config.py — AgentConfig dataclass."""

import pytest

from agents.config import AgentConfig


class TestAgentConfig:
    def test_defaults_with_endpoint(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.delenv("AZURE_OPENAI_CHAT_DEPLOYMENT", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
        monkeypatch.delenv("MCP_SERVER_URL", raising=False)

        config = AgentConfig()

        assert config.azure_endpoint == "https://test.openai.azure.com/"
        assert config.api_key == "test-key"
        assert config.deployment_name == "gpt-4o"
        assert config.api_version == "2024-10-21"
        assert config.mcp_server_url == "http://127.0.0.1:8011/mcp"
        assert config.auth_method == "api_key"
        assert not config.uses_azure_cli

    def test_azure_cli_auth_when_no_api_key(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

        config = AgentConfig()

        assert config.auth_method == "azure_cli"
        assert config.uses_azure_cli

    def test_raises_when_endpoint_missing(self, monkeypatch):
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)

        with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
            AgentConfig()

    def test_custom_mcp_url(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("MCP_SERVER_URL", "http://localhost:9000/mcp")

        config = AgentConfig()

        assert config.mcp_server_url == "http://localhost:9000/mcp"

    def test_validate_mcp_server_valid(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")

        config = AgentConfig()

        assert config.validate_mcp_server() is True

    def test_validate_mcp_server_invalid(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")

        config = AgentConfig()
        config.mcp_server_url = ""

        assert config.validate_mcp_server() is False

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "my-key")

        config = AgentConfig.from_env()

        assert isinstance(config, AgentConfig)
        assert config.azure_endpoint == "https://test.openai.azure.com/"
