"""Regression tests for maf_graphrag.agents.mcp_compat."""

from __future__ import annotations

import sys
from types import ModuleType

import pytest


def _install_stub_mcp(monkeypatch):
    """Install stub mcp modules with snake_case-only attributes."""

    mcp_module = ModuleType("mcp")
    types_module = ModuleType("mcp.types")
    shared_module = ModuleType("mcp.shared")
    exceptions_module = ModuleType("mcp.shared.exceptions")

    class InitializeResult:  # pragma: no cover - exercised via alias access
        def __init__(self, protocol_version: str) -> None:
            self.protocol_version = protocol_version

    class Tool:  # pragma: no cover - exercised via alias access
        def __init__(self, input_schema: dict[str, object]) -> None:
            self.input_schema = input_schema

    class CallToolResult:  # pragma: no cover - exercised via alias access
        def __init__(self, *, is_error: bool, structured_content: list[object]) -> None:
            self.is_error = is_error
            self.structured_content = structured_content

    class ListToolsResult:  # pragma: no cover - exercised via alias access
        def __init__(self, *, next_cursor: str | None) -> None:
            self.next_cursor = next_cursor

    class ListPromptsResult:  # pragma: no cover - exercised via alias access
        def __init__(self, *, next_cursor: str | None) -> None:
            self.next_cursor = next_cursor

    class MCPError(Exception):
        pass

    types_module.InitializeResult = InitializeResult
    types_module.Tool = Tool
    types_module.CallToolResult = CallToolResult
    types_module.ListToolsResult = ListToolsResult
    types_module.ListPromptsResult = ListPromptsResult

    exceptions_module.MCPError = MCPError

    shared_module.exceptions = exceptions_module

    mcp_module.types = types_module
    mcp_module.shared = shared_module

    monkeypatch.setitem(sys.modules, "mcp", mcp_module)
    monkeypatch.setitem(sys.modules, "mcp.types", types_module)
    monkeypatch.setitem(sys.modules, "mcp.shared", shared_module)
    monkeypatch.setitem(sys.modules, "mcp.shared.exceptions", exceptions_module)

    return types_module, exceptions_module


@pytest.fixture()
def stub_mcp(monkeypatch):
    types_module, exceptions_module = _install_stub_mcp(monkeypatch)

    import maf_graphrag.agents.mcp_compat as mcp_compat

    monkeypatch.setattr(mcp_compat, "_COMPAT_PATCHED", False)

    return types_module, exceptions_module, mcp_compat


class TestEnsureMcpClientCompatibility:
    def test_alias_properties_bridge_camel_case_and_snake_case(self, stub_mcp):
        types_module, exceptions_module, mcp_compat = stub_mcp

        mcp_compat.ensure_mcp_client_compatibility()

        handshake = types_module.InitializeResult(protocol_version="1.0")
        assert handshake.protocolVersion == "1.0"

        handshake.protocolVersion = "2.0"
        assert handshake.protocol_version == "2.0"

        tool = types_module.Tool(input_schema={"type": "object"})
        assert tool.inputSchema == {"type": "object"}

        result = types_module.CallToolResult(is_error=False, structured_content=[])
        assert result.isError is False
        assert isinstance(result.structuredContent, list)

        tools_page = types_module.ListToolsResult(next_cursor="cursor-1")
        assert tools_page.nextCursor == "cursor-1"

        prompts_page = types_module.ListPromptsResult(next_cursor=None)
        assert prompts_page.nextCursor is None

        assert exceptions_module.McpError is exceptions_module.MCPError
        assert mcp_compat._COMPAT_PATCHED is True

    def test_noop_when_alias_already_present(self, stub_mcp, monkeypatch):
        types_module, _, mcp_compat = stub_mcp

        sentinel = property(lambda self: "sentinel")
        types_module.Tool.inputSchema = sentinel

        mcp_compat.ensure_mcp_client_compatibility()

        assert types_module.Tool.inputSchema is sentinel
        assert mcp_compat._COMPAT_PATCHED is True
