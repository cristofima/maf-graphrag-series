"""Unit tests for workflows/base.py — MCPWorkflowBase async context manager lifecycle.

Uses a minimal concrete subclass since MCPWorkflowBase is abstract. The MCP
tool creation is mocked, so no network connection or credentials are needed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from workflows.base import MCPWorkflowBase


class _StubWorkflow(MCPWorkflowBase):
    """Minimal concrete subclass to exercise the base lifecycle."""

    def __init__(self, mcp_url: str | None = None) -> None:
        super().__init__(mcp_url)
        self.create_agents_calls: list[object] = []

    def _create_agents(self, mcp_tool: object) -> None:
        self.create_agents_calls.append(mcp_tool)


def _mock_mcp_tool() -> MagicMock:
    tool = MagicMock(name="mcp_tool")
    tool.__aenter__ = AsyncMock(return_value=tool)
    tool.__aexit__ = AsyncMock(return_value=False)
    return tool


class TestMCPWorkflowBaseLifecycle:
    async def test_aenter_creates_mcp_tool_and_agents(self):
        mock_tool = _mock_mcp_tool()
        with patch("agents.supervisor.create_mcp_tool", return_value=mock_tool) as mock_create:
            workflow = _StubWorkflow(mcp_url="http://localhost:9999/mcp")
            result = await workflow.__aenter__()

        mock_create.assert_called_once_with("http://localhost:9999/mcp")
        mock_tool.__aenter__.assert_awaited_once()
        assert workflow.create_agents_calls == [mock_tool]
        assert result is workflow
        assert workflow._mcp_tool is mock_tool

    async def test_aexit_closes_exit_stack(self):
        mock_tool = _mock_mcp_tool()
        with patch("agents.supervisor.create_mcp_tool", return_value=mock_tool):
            workflow = _StubWorkflow()
            await workflow.__aenter__()
            await workflow.__aexit__(None, None, None)

        mock_tool.__aexit__.assert_awaited_once()

    async def test_aexit_without_prior_aenter_is_a_no_op(self):
        workflow = _StubWorkflow()
        await workflow.__aexit__(None, None, None)

    async def test_default_mcp_url_is_none(self):
        mock_tool = _mock_mcp_tool()
        with patch("agents.supervisor.create_mcp_tool", return_value=mock_tool) as mock_create:
            workflow = _StubWorkflow()
            await workflow.__aenter__()

        mock_create.assert_called_once_with(None)
