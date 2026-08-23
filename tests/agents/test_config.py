"""Unit tests for the Foundry-specific AgentConfig Pydantic model."""

import dotenv
import pytest

from agents.config import DEFAULT_API_VERSION, AgentConfig, SessionConfig


def _seed_foundry_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "router-balanced")
    monkeypatch.setenv("AZURE_OPENAI_ROUTER_DEPLOYMENT", "router-efficient")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")


class TestAgentConfig:
    def test_defaults_with_required_env(self, monkeypatch):
        _seed_foundry_env(monkeypatch)
        monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
        monkeypatch.delenv("MCP_SERVER_URL", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_ROUTER_SUBSET", raising=False)

        config = AgentConfig.from_env()

        assert str(config.azure_endpoint) == "https://test.openai.azure.com/"
        assert config.deployment_name == "router-balanced"
        assert config.router_model == "router-efficient"
        assert config.api_key == "test-key"
        assert config.api_version == DEFAULT_API_VERSION
        assert str(config.mcp_server_url) == "http://127.0.0.1:8011/mcp"
        assert config.router_subset is None
        assert not config.uses_azure_cli

    def test_switches_to_azure_cli_when_key_missing(self, monkeypatch):
        _seed_foundry_env(monkeypatch)
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

        config = AgentConfig.from_env()

        assert config.uses_azure_cli

    def test_missing_endpoint_raises(self, monkeypatch):
        _seed_foundry_env(monkeypatch)
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)

        with pytest.raises(ValueError, match="azure_endpoint"):
            AgentConfig.from_env()

    def test_missing_deployment_raises(self, monkeypatch):
        _seed_foundry_env(monkeypatch)
        monkeypatch.delenv("AZURE_OPENAI_CHAT_DEPLOYMENT", raising=False)

        with pytest.raises(ValueError, match="deployment_name"):
            AgentConfig.from_env()

    def test_missing_router_deployment_raises(self, monkeypatch):
        _seed_foundry_env(monkeypatch)
        monkeypatch.delenv("AZURE_OPENAI_ROUTER_DEPLOYMENT", raising=False)

        with pytest.raises(ValueError, match="router_deployment"):
            AgentConfig.from_env()

    def test_custom_mcp_url(self, monkeypatch):
        _seed_foundry_env(monkeypatch)
        monkeypatch.setenv("MCP_SERVER_URL", "http://localhost:9000/mcp")

        config = AgentConfig.from_env()

        assert str(config.mcp_server_url) == "http://localhost:9000/mcp"

    def test_azure_base_url_appends_openai_suffix(self, monkeypatch):
        _seed_foundry_env(monkeypatch)
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://myproj.eastus2.openai.azure.com")

        config = AgentConfig.from_env()

        assert config.azure_base_url == "https://myproj.eastus2.openai.azure.com/openai/v1/"

    def test_validate_mcp_server_flags_invalid_value(self, monkeypatch):
        _seed_foundry_env(monkeypatch)

        config = AgentConfig.from_env()
        config.mcp_server_url = ""

        assert config.validate_mcp_server() is False

    def test_from_env_loads_dotenv(self, monkeypatch):
        load_calls: list[bool] = []

        def fake_load_dotenv(*, override: bool = False, **_kwargs: object) -> bool:
            load_calls.append(override)
            return True

        monkeypatch.setattr(dotenv, "load_dotenv", fake_load_dotenv)
        _seed_foundry_env(monkeypatch)

        config = AgentConfig.from_env()

        assert isinstance(config, AgentConfig)
        assert load_calls == [True]
        assert str(config.azure_endpoint) == "https://test.openai.azure.com/"


class TestSessionConfig:
    def test_defaults_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SESSION_TTL_SECONDS", raising=False)
        monkeypatch.delenv("SESSION_MAX_COUNT", raising=False)
        monkeypatch.delenv("SESSION_CLEANUP_INTERVAL_SECONDS", raising=False)
        monkeypatch.delenv("SESSION_MAX_HISTORY_GROUPS", raising=False)

        config = SessionConfig.from_env()

        assert config.ttl_seconds == 1800
        assert config.max_count == 1000
        assert config.cleanup_interval_seconds == 60
        assert config.max_history_groups == 12

    def test_invalid_session_ttl_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SESSION_TTL_SECONDS", "1")

        with pytest.raises(ValueError, match="ttl_seconds"):
            SessionConfig.from_env()
