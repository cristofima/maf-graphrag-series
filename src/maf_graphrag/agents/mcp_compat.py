"""Compatibility helpers for MCP client integration.

Agent Framework 1.17.x expects camelCase attributes on certain MCP models,
while the modern ``mcp`` library exposes snake_case field names via Pydantic.
This module adds lightweight aliases so the runtime remains compatible with
newer protocol releases without downgrading dependencies.
"""

from __future__ import annotations

from typing import Any, cast

_COMPAT_PATCHED: bool = False


def ensure_mcp_client_compatibility() -> None:
    """Ensure Agent Framework can read modern MCP handshake fields.

    Newer versions of ``mcp`` expose ``InitializeResult.protocol_version``
    instead of the legacy camelCase attribute. Agent Framework still reads
    ``protocolVersion``, which raises ``AttributeError`` and breaks workflow
    startup. This helper installs a matching property so both spellings work.
    """

    global _COMPAT_PATCHED

    if _COMPAT_PATCHED:
        return

    try:
        from mcp import types
    except ModuleNotFoundError:
        return

    initialize_result = getattr(types, "InitializeResult", None)
    if initialize_result is not None:
        _add_alias_property(initialize_result, "protocolVersion", "protocol_version")

    tool_model = getattr(types, "Tool", None)
    if tool_model is not None:
        _add_alias_property(tool_model, "inputSchema", "input_schema")

    call_tool_result = getattr(types, "CallToolResult", None)
    if call_tool_result is not None:
        _add_alias_property(call_tool_result, "isError", "is_error")
        _add_alias_property(call_tool_result, "structuredContent", "structured_content")

    list_tools_result = getattr(types, "ListToolsResult", None)
    if list_tools_result is not None:
        _add_alias_property(list_tools_result, "nextCursor", "next_cursor")

    list_prompts_result = getattr(types, "ListPromptsResult", None)
    if list_prompts_result is not None:
        _add_alias_property(list_prompts_result, "nextCursor", "next_cursor")

    try:
        from mcp.shared import exceptions as shared_exceptions  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        pass
    else:
        if hasattr(shared_exceptions, "MCPError") and not hasattr(shared_exceptions, "McpError"):
            cast(Any, shared_exceptions).McpError = shared_exceptions.MCPError

    _COMPAT_PATCHED = True


def _add_alias_property(model_cls: type[Any], alias: str, field_name: str) -> None:
    """Expose ``alias`` as a property that proxies to ``field_name``."""

    if hasattr(model_cls, alias):
        return

    def getter(self: Any) -> Any:
        return getattr(self, field_name)

    def setter(self: Any, value: Any) -> None:
        setattr(self, field_name, value)

    setattr(model_cls, alias, property(getter, setter))
