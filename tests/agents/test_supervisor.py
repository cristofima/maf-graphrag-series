"""Unit tests for agents/supervisor.py."""

from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _azure_env(monkeypatch):
    """Set minimal Azure env vars so AgentConfig() succeeds."""
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
    monkeypatch.setenv("AZURE_OPENAI_ROUTER_DEPLOYMENT", "router-efficient")


def _mock_mcp_tool():
    """Return a MagicMock standing in for MCPStreamableHTTPTool."""
    tool = MagicMock(name="mcp_tool")
    tool.__aenter__ = AsyncMock(return_value=tool)
    tool.__aexit__ = AsyncMock(return_value=False)
    return tool


# ===========================================================================
# create_research_delegate
# ===========================================================================


class TestCreateResearchDelegate:
    """Tests for ``create_research_delegate`` factory function."""

    def test_returns_callable(self, monkeypatch):
        _azure_env(monkeypatch)

        with (
            patch("agents.supervisor.create_client", return_value=MagicMock()),
            patch("agents.supervisor.create_mcp_tool", return_value=_mock_mcp_tool()),
        ):
            from agents.supervisor import create_research_delegate

            delegate = create_research_delegate()

            assert callable(delegate)

    def test_uses_default_prompt(self, monkeypatch):
        _azure_env(monkeypatch)
        mock_agent_cls = MagicMock()

        with (
            patch("agents.supervisor.create_client", return_value=MagicMock()),
            patch("agents.supervisor.create_mcp_tool", return_value=_mock_mcp_tool()),
            patch("agent_framework.Agent", mock_agent_cls),
        ):
            from agents.supervisor import RESEARCH_DELEGATE_PROMPT, create_research_delegate

            create_research_delegate()

            _, kwargs = mock_agent_cls.call_args
            assert kwargs["instructions"] == RESEARCH_DELEGATE_PROMPT

    def test_uses_custom_prompt(self, monkeypatch):
        _azure_env(monkeypatch)
        custom = "You are a custom delegate."
        mock_agent_cls = MagicMock()

        with (
            patch("agents.supervisor.create_client", return_value=MagicMock()),
            patch("agents.supervisor.create_mcp_tool", return_value=_mock_mcp_tool()),
            patch("agent_framework.Agent", mock_agent_cls),
        ):
            from agents.supervisor import create_research_delegate

            create_research_delegate(system_prompt=custom)

            _, kwargs = mock_agent_cls.call_args
            assert kwargs["instructions"] == custom

    def test_agent_name_is_research_delegate(self, monkeypatch):
        _azure_env(monkeypatch)
        mock_agent_cls = MagicMock()

        with (
            patch("agents.supervisor.create_client", return_value=MagicMock()),
            patch("agents.supervisor.create_mcp_tool", return_value=_mock_mcp_tool()),
            patch("agent_framework.Agent", mock_agent_cls),
        ):
            from agents.supervisor import create_research_delegate

            create_research_delegate()

            _, kwargs = mock_agent_cls.call_args
            assert kwargs["name"] == "research_delegate"

    def test_agent_has_mcp_tool(self, monkeypatch):
        _azure_env(monkeypatch)
        mock_mcp = _mock_mcp_tool()
        mock_agent_cls = MagicMock()

        with (
            patch("agents.supervisor.create_client", return_value=MagicMock()),
            patch("agents.supervisor.create_mcp_tool", return_value=mock_mcp),
            patch("agent_framework.Agent", mock_agent_cls),
        ):
            from agents.supervisor import create_research_delegate

            create_research_delegate()

            _, kwargs = mock_agent_cls.call_args
            assert mock_mcp in kwargs["tools"]

    def test_passes_custom_mcp_url(self, monkeypatch):
        _azure_env(monkeypatch)
        custom_url = "http://custom:9999/mcp"

        with (
            patch("agents.supervisor.create_client", return_value=MagicMock()),
            patch("agents.supervisor.create_mcp_tool", return_value=_mock_mcp_tool()) as mock_mcp,
            patch("agent_framework.Agent", MagicMock()),
        ):
            from agents.supervisor import create_research_delegate

            create_research_delegate(mcp_url=custom_url)

            mock_mcp.assert_called_once_with(custom_url)


class TestResearchDelegateExecution:
    """Tests for the async execution of the research delegate tool."""

    async def test_delegate_runs_sub_agent_and_returns_text(self, monkeypatch):
        _azure_env(monkeypatch)

        mock_result = MagicMock()
        mock_result.text = "Summary of findings about Alpha."
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mock_agent_instance.__aenter__ = AsyncMock(return_value=mock_agent_instance)
        mock_agent_instance.__aexit__ = AsyncMock(return_value=False)

        mcp_tool = _mock_mcp_tool()

        with (
            patch("agents.supervisor.create_client", return_value=MagicMock()),
            patch("agents.supervisor.create_mcp_tool", return_value=mcp_tool),
            patch("agent_framework.Agent", return_value=mock_agent_instance),
        ):
            from agents.supervisor import create_research_delegate

            delegate = create_research_delegate()

            # The @tool-decorated function wraps _research_delegate
            # We need to get the underlying async function
            inner = delegate.func if hasattr(delegate, "func") else delegate
            result = await inner(query="Tell me about Project Alpha")

            assert result == "Summary of findings about Alpha."
            mock_agent_instance.run.assert_awaited_once_with("Tell me about Project Alpha")

    async def test_delegate_enters_agent_context(self, monkeypatch):
        _azure_env(monkeypatch)

        mock_result = MagicMock()
        mock_result.text = "done"
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mock_agent_instance.__aenter__ = AsyncMock(return_value=mock_agent_instance)
        mock_agent_instance.__aexit__ = AsyncMock(return_value=False)

        mcp_tool = _mock_mcp_tool()

        with (
            patch("agents.supervisor.create_client", return_value=MagicMock()),
            patch("agents.supervisor.create_mcp_tool", return_value=mcp_tool),
            patch("agent_framework.Agent", return_value=mock_agent_instance),
        ):
            from agents.supervisor import create_research_delegate

            delegate = create_research_delegate()
            inner = delegate.func if hasattr(delegate, "func") else delegate
            await inner(query="test")

            mock_agent_instance.__aenter__.assert_awaited_once()
            mock_agent_instance.__aexit__.assert_awaited_once()
            mcp_tool.__aenter__.assert_awaited_once()
            mcp_tool.__aexit__.assert_awaited_once()


# ===========================================================================
# create_mcp_tool — URL normalization
# ===========================================================================


class TestCreateMcpTool:
    """Tests for ``create_mcp_tool`` URL normalization logic."""

    def test_appends_mcp_suffix(self, monkeypatch):
        _azure_env(monkeypatch)

        with patch("agent_framework.MCPStreamableHTTPTool") as mock_cls:
            from agents.supervisor import create_mcp_tool

            create_mcp_tool("http://localhost:8011")

            _, kwargs = mock_cls.call_args
            assert kwargs["url"] == "http://localhost:8011/mcp"

    def test_replaces_sse_with_mcp(self, monkeypatch):
        _azure_env(monkeypatch)

        with patch("agent_framework.MCPStreamableHTTPTool") as mock_cls:
            from agents.supervisor import create_mcp_tool

            create_mcp_tool("http://localhost:8011/sse")

            _, kwargs = mock_cls.call_args
            assert kwargs["url"] == "http://localhost:8011/mcp"

    def test_preserves_mcp_suffix(self, monkeypatch):
        _azure_env(monkeypatch)

        with patch("agent_framework.MCPStreamableHTTPTool") as mock_cls:
            from agents.supervisor import create_mcp_tool

            create_mcp_tool("http://localhost:8011/mcp")

            _, kwargs = mock_cls.call_args
            assert kwargs["url"] == "http://localhost:8011/mcp"

    def test_uses_config_default_url(self, monkeypatch):
        _azure_env(monkeypatch)
        monkeypatch.setenv("MCP_SERVER_URL", "http://custom:9000/mcp")

        with patch("agent_framework.MCPStreamableHTTPTool") as mock_cls:
            from agents.supervisor import create_mcp_tool

            create_mcp_tool()

            _, kwargs = mock_cls.call_args
            assert kwargs["url"] == "http://custom:9000/mcp"


# ===========================================================================
# create_client — provider dispatch
# ===========================================================================


class TestCreateClient:
    """Tests for ``create_client`` Foundry integration."""

    def test_client_uses_foundry_base_url(self, monkeypatch):
        _azure_env(monkeypatch)
        monkeypatch.setattr("dotenv.load_dotenv", MagicMock())
        monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2025-11-18")

        with patch("agent_framework.openai.OpenAIChatCompletionClient") as mock_cls:
            from agents.supervisor import create_client

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
            from agents.supervisor import create_client

            create_client()

            _, kwargs = mock_cls.call_args
            assert kwargs["api_key"] is None
