"""Workflow-support functions for agent creation and MCP connectivity."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from maf_graphrag.agents.config import get_agent_config
from maf_graphrag.agents.prompts import RESEARCH_DELEGATE_PROMPT

if TYPE_CHECKING:  # pragma: no cover - import guard for typing only
    from agent_framework import (
        MCPStreamableHTTPTool,
        SupportsChatGetResponse,
    )

logger = logging.getLogger(__name__)


def create_mcp_tool(mcp_url: str | None = None) -> MCPStreamableHTTPTool:
    """Create MCPStreamableHTTPTool for GraphRAG server.

    Args:
        mcp_url: MCP server URL (default: from config or http://localhost:8011/mcp)

    Returns:
        MCPStreamableHTTPTool: Configured MCP tool
    """
    from agent_framework import MCPStreamableHTTPTool

    config = get_agent_config()
    url_value = mcp_url or config.mcp_server_url
    url = str(url_value)

    # Ensure URL ends with /mcp (not /sse)
    if url.endswith("/sse"):
        url = url.replace("/sse", "/mcp")
    elif not url.endswith("/mcp"):
        url = url.rstrip("/") + "/mcp"

    return MCPStreamableHTTPTool(
        name="graphrag",
        url=url,
        description="Query the GraphRAG knowledge graph for entity and thematic information",
    )


def create_client() -> SupportsChatGetResponse:
    """Create an LLM chat client for the configured Foundry deployment."""
    config = get_agent_config()

    from agent_framework.openai import OpenAIChatCompletionClient

    return OpenAIChatCompletionClient(
        model=config.deployment_name,
        base_url=config.azure_base_url,
        api_key=config.api_key if not config.uses_azure_cli else None,
        api_version=config.api_version,
    )


# Backward-compatible alias — workflows import this name.
create_azure_client = create_client


def create_research_delegate(
    mcp_url: str | None = None,
    system_prompt: str | None = None,
) -> object:
    """Create a ``@tool``-decorated function wrapping a research sub-agent.

    The sub-agent has its own MCP tool and session — its internal
    conversation never leaks into the coordinator's context. It receives
    a query, runs a full search, and returns a concise summary.

    This implements the *context isolation* pattern: the coordinator sees
    only the summary, avoiding token bloat from raw MCP payloads.

    Args:
        mcp_url: Optional MCP server URL override.
        system_prompt: Optional prompt override for the delegate.

    Returns:
        A ``@tool``-decorated async callable suitable for passing to
        ``Agent(tools=[...])``.

    Example::

        delegate = create_research_delegate()
        supervisor = Agent(
            client=client,
            instructions="Use the research delegate for deep dives.",
            tools=[delegate],
        )
        async with supervisor:
            result = await supervisor.run("Deep dive on Project Alpha")
    """
    from agent_framework import Agent, tool

    client = create_client()
    mcp_tool = create_mcp_tool(mcp_url)
    prompt = system_prompt or RESEARCH_DELEGATE_PROMPT

    delegate_agent = Agent(
        client=client,
        name="research_delegate",
        instructions=prompt,
        tools=[mcp_tool],
    )

    @tool(
        name="research_delegate",
        description=(
            "Delegate a research question to a specialist sub-agent that performs "
            "an in-depth knowledge graph search and returns a concise summary. "
            "Use for complex questions requiring deep analysis."
        ),
        approval_mode="never_require",
    )
    async def _research_delegate(query: str) -> str:
        """Run a research query through an isolated sub-agent.

        Args:
            query: The research question to investigate.

        Returns:
            A concise summary of the sub-agent's findings.
        """
        async with delegate_agent, mcp_tool:
            result = await delegate_agent.run(query)
            return result.text

    return _research_delegate
