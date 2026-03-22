"""Unit tests for agents/config.py — Multi-provider configuration."""

import pytest

from agents.config import AgentConfig, is_azure


class TestMultiProviderConfig:
    """Tests for the new multi-provider fields — backward compat is tested in test_config.py."""

    def test_default_api_host_is_azure(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.delenv("API_HOST", raising=False)

        config = AgentConfig()

        assert config.api_host == "azure"

    def test_github_host_requires_token(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "github")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)

        with pytest.raises(ValueError, match="GITHUB_TOKEN"):
            AgentConfig()

    def test_github_host_valid(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "github")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)

        config = AgentConfig()

        assert config.api_host == "github"
        assert config.github_token == "ghp_test123"

    def test_openai_host_requires_api_key(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "openai")
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)

        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            AgentConfig()

    def test_openai_host_valid(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test123")
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)

        config = AgentConfig()

        assert config.api_host == "openai"
        assert config.api_key == "sk-test123"

    def test_ollama_host_no_key_required(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "ollama")
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

        config = AgentConfig()

        assert config.api_host == "ollama"

    def test_azure_endpoint_not_required_for_non_azure(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "github")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)

        config = AgentConfig()
        assert config.azure_endpoint == ""


class TestModelIdProperty:
    def test_azure_returns_deployment_name(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
        monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-custom")

        config = AgentConfig()
        assert config.model_id == "gpt-4o-custom"

    def test_github_returns_github_model(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "github")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        monkeypatch.setenv("GITHUB_MODEL", "openai/gpt-4.1")

        config = AgentConfig()
        assert config.model_id == "openai/gpt-4.1"

    def test_ollama_returns_ollama_model(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "ollama")
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)

        config = AgentConfig()
        assert config.model_id == "llama3.2"

    def test_openai_returns_openai_model(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

        config = AgentConfig()
        assert config.model_id == "gpt-4o"


class TestProviderApiKeyProperty:
    def test_azure_returns_azure_key(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "az-key")

        config = AgentConfig()
        assert config.provider_api_key == "az-key"

    def test_github_returns_github_token(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "github")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_xyz")

        config = AgentConfig()
        assert config.provider_api_key == "ghp_xyz"

    def test_ollama_returns_unused(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "ollama")
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)

        config = AgentConfig()
        assert config.provider_api_key == "unused"


class TestProviderBaseUrlProperty:
    def test_azure_constructs_openai_v1_url(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://myresource.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")

        config = AgentConfig()
        assert config.provider_base_url == "https://myresource.openai.azure.com/openai/v1/"

    def test_github_returns_github_url(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "github")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        config = AgentConfig()
        assert config.provider_base_url == "https://models.github.ai/inference"

    def test_ollama_returns_localhost(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "ollama")
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)

        config = AgentConfig()
        assert config.provider_base_url == "http://localhost:11434/v1/"

    def test_openai_returns_none(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

        config = AgentConfig()
        assert config.provider_base_url is None


class TestIsAzureHelper:
    def test_true_for_azure(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")

        config = AgentConfig()
        assert is_azure(config) is True

    def test_false_for_github(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "github")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        config = AgentConfig()
        assert is_azure(config) is False
