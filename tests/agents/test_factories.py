"""Unit tests for agents/factories.py."""

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _azure_env(monkeypatch):
    """Set minimal Azure env vars so AgentConfig() succeeds."""
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
    monkeypatch.setenv("AZURE_OPENAI_ROUTER_DEPLOYMENT", "router-efficient")


# ==========================================================================
# create_mcp_tool — URL normalization
# ==========================================================================


class TestCreateMcpTool:
    """Tests for ``create_mcp_tool`` URL normalization logic."""

    def test_appends_mcp_suffix(self, monkeypatch):
        _azure_env(monkeypatch)

        with patch("agent_framework.MCPStreamableHTTPTool") as mock_cls:
            from maf_graphrag.agents.factories import create_mcp_tool

            create_mcp_tool("http://localhost:8011")

            _, kwargs = mock_cls.call_args
            assert kwargs["url"] == "http://localhost:8011/mcp"

    def test_replaces_sse_with_mcp(self, monkeypatch):
        _azure_env(monkeypatch)

        with patch("agent_framework.MCPStreamableHTTPTool") as mock_cls:
            from maf_graphrag.agents.factories import create_mcp_tool

            create_mcp_tool("http://localhost:8011/sse")

            _, kwargs = mock_cls.call_args
            assert kwargs["url"] == "http://localhost:8011/mcp"

    def test_preserves_mcp_suffix(self, monkeypatch):
        _azure_env(monkeypatch)

        with patch("agent_framework.MCPStreamableHTTPTool") as mock_cls:
            from maf_graphrag.agents.factories import create_mcp_tool

            create_mcp_tool("http://localhost:8011/mcp")

            _, kwargs = mock_cls.call_args
            assert kwargs["url"] == "http://localhost:8011/mcp"

    def test_uses_config_default_url(self, monkeypatch):
        _azure_env(monkeypatch)
        monkeypatch.setenv("MCP_SERVER_URL", "http://custom:9000/mcp")

        with patch("agent_framework.MCPStreamableHTTPTool") as mock_cls:
            from maf_graphrag.agents.factories import create_mcp_tool

            create_mcp_tool()

            _, kwargs = mock_cls.call_args
            assert kwargs["url"] == "http://custom:9000/mcp"


# ==========================================================================
# create_client — provider dispatch
# ==========================================================================


class TestCreateClient:
    """Tests for ``create_client`` Foundry integration."""

    def test_client_uses_foundry_base_url(self, monkeypatch):
        _azure_env(monkeypatch)
        monkeypatch.setattr("dotenv.load_dotenv", MagicMock())
        monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2025-11-18")

        with patch("agent_framework.openai.OpenAIChatCompletionClient") as mock_cls:
            from maf_graphrag.agents.factories import create_client

            create_client()

            _, kwargs = mock_cls.call_args
            assert kwargs["model"] == "gpt-4o"
            assert kwargs["api_key"] == "test-key"
            assert kwargs["api_version"] == "2025-11-18"
            assert kwargs["base_url"] == "https://test.openai.azure.com/openai/v1/"

    def test_client_uses_azure_cli_when_key_missing(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
        monkeypatch.setenv("AZURE_OPENAI_ROUTER_DEPLOYMENT", "router-efficient")
        monkeypatch.setattr("dotenv.load_dotenv", MagicMock())

        with patch("agent_framework.openai.OpenAIChatCompletionClient") as mock_cls:
            from maf_graphrag.agents.factories import create_client

            create_client()

            _, kwargs = mock_cls.call_args
            assert kwargs["api_key"] is None
