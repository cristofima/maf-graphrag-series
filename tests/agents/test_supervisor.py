"""Unit tests for agents/supervisor.py — local_tools and create_research_delegate."""

from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _azure_env(monkeypatch):
    """Set minimal Azure env vars so AgentConfig() succeeds."""
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
    monkeypatch.delenv("API_HOST", raising=False)


def _mock_mcp_tool():
    """Return a MagicMock standing in for MCPStreamableHTTPTool."""
    tool = MagicMock(name="mcp_tool")
    tool.__aenter__ = AsyncMock(return_value=tool)
    tool.__aexit__ = AsyncMock(return_value=False)
    return tool


# ===========================================================================
# create_knowledge_captain — local_tools parameter
# ===========================================================================


class TestCreateKnowledgeCaptainLocalTools:
    """Tests for the ``local_tools`` parameter on ``create_knowledge_captain``."""

    def test_no_local_tools_only_mcp(self, monkeypatch):
        _azure_env(monkeypatch)
        mock_mcp = _mock_mcp_tool()
        mock_agent_cls = MagicMock()

        with (
            patch("agents.supervisor.create_client", return_value=MagicMock()),
            patch("agents.supervisor.create_mcp_tool", return_value=mock_mcp),
            patch("agent_framework.Agent", mock_agent_cls),
        ):
            from agents.supervisor import create_knowledge_captain

            create_knowledge_captain()

            _, kwargs = mock_agent_cls.call_args
            assert len(kwargs["tools"]) == 1
            assert kwargs["tools"][0] is mock_mcp

    def test_local_tools_appended_after_mcp(self, monkeypatch):
        _azure_env(monkeypatch)
        mock_mcp = _mock_mcp_tool()
        mock_agent_cls = MagicMock()
        local_fn_a = MagicMock(name="tool_a")
        local_fn_b = MagicMock(name="tool_b")

        with (
            patch("agents.supervisor.create_client", return_value=MagicMock()),
            patch("agents.supervisor.create_mcp_tool", return_value=mock_mcp),
            patch("agent_framework.Agent", mock_agent_cls),
        ):
            from agents.supervisor import create_knowledge_captain

            create_knowledge_captain(local_tools=[local_fn_a, local_fn_b])

            _, kwargs = mock_agent_cls.call_args
            tools = kwargs["tools"]
            assert len(tools) == 3
            assert tools[0] is mock_mcp
            assert tools[1] is local_fn_a
            assert tools[2] is local_fn_b

    def test_empty_local_tools_list_yields_only_mcp(self, monkeypatch):
        _azure_env(monkeypatch)
        mock_agent_cls = MagicMock()

        with (
            patch("agents.supervisor.create_client", return_value=MagicMock()),
            patch("agents.supervisor.create_mcp_tool", return_value=_mock_mcp_tool()),
            patch("agent_framework.Agent", mock_agent_cls),
        ):
            from agents.supervisor import create_knowledge_captain

            create_knowledge_captain(local_tools=[])

            _, kwargs = mock_agent_cls.call_args
            assert len(kwargs["tools"]) == 1

    def test_none_local_tools_yields_only_mcp(self, monkeypatch):
        _azure_env(monkeypatch)
        mock_agent_cls = MagicMock()

        with (
            patch("agents.supervisor.create_client", return_value=MagicMock()),
            patch("agents.supervisor.create_mcp_tool", return_value=_mock_mcp_tool()),
            patch("agent_framework.Agent", mock_agent_cls),
        ):
            from agents.supervisor import create_knowledge_captain

            create_knowledge_captain(local_tools=None)

            _, kwargs = mock_agent_cls.call_args
            assert len(kwargs["tools"]) == 1


# ===========================================================================
# KnowledgeCaptainRunner — local_tools forwarding
# ===========================================================================


class TestKnowledgeCaptainRunnerLocalTools:
    """Tests that ``KnowledgeCaptainRunner`` forwards ``local_tools``."""

    def test_runner_passes_local_tools_to_factory(self, monkeypatch):
        _azure_env(monkeypatch)

        local_fn = MagicMock(name="tool_x")
        mock_agent_instance = MagicMock()

        with patch(
            "agents.supervisor.create_knowledge_captain",
            return_value=mock_agent_instance,
        ) as mock_factory:
            from agents.supervisor import KnowledgeCaptainRunner

            runner = KnowledgeCaptainRunner(local_tools=[local_fn])

            mock_factory.assert_called_once()
            call_kwargs = mock_factory.call_args[1]
            assert call_kwargs["local_tools"] == [local_fn]
            assert runner.agent is mock_agent_instance

    def test_runner_default_no_local_tools(self, monkeypatch):
        _azure_env(monkeypatch)

        with patch(
            "agents.supervisor.create_knowledge_captain",
            return_value=MagicMock(),
        ) as mock_factory:
            from agents.supervisor import KnowledgeCaptainRunner

            KnowledgeCaptainRunner()

            call_kwargs = mock_factory.call_args[1]
            assert call_kwargs["local_tools"] is None


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
