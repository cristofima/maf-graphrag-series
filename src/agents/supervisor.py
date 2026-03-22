"""
Knowledge Captain Supervisor - MCP-Based Agent.

This module provides the Knowledge Captain agent that uses MCPStreamableHTTPTool
to connect to the GraphRAG MCP Server. The agent decides which tool to use
based on its system prompt (no separate routing logic needed).

Supports multiple LLM providers via ``create_client()`` (Azure OpenAI, GitHub
Models, OpenAI, Ollama) controlled by the ``API_HOST`` environment variable.
Default is ``"azure"`` for backward compatibility.

See README.md for architecture diagrams and detailed documentation.

Usage:
    from agents.supervisor import create_knowledge_captain, KnowledgeCaptainRunner

    # Option 1: Quick setup
    async with KnowledgeCaptainRunner() as runner:
        response = await runner.ask("Who leads Project Alpha?")

    # Option 2: Manual setup — Agent as async context manager (rc5+)
    agent = create_knowledge_captain()
    async with agent:
        result = await agent.run("Who leads Project Alpha?")
        print(result.text)
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from agents.config import get_agent_config
from agents.middleware import LoggingFunctionMiddleware, TimingAgentMiddleware, TokenCountingChatMiddleware
from agents.prompts import KNOWLEDGE_CAPTAIN_PROMPT, RESEARCH_DELEGATE_PROMPT

if TYPE_CHECKING:
    from agent_framework import (
        Agent,
        AgentMiddleware,
        AgentSession,
        ChatMiddleware,
        FunctionMiddleware,
        MCPStreamableHTTPTool,
    )
    from agent_framework.types import SupportsChatGetResponse

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Response from the Knowledge Captain agent."""

    text: str
    """The agent's response text."""

    tools_used: list[str] | None = None
    """List of MCP tools that were called (if available)."""

    token_count: int | None = None
    """Total tokens used (if available)."""


def create_mcp_tool(mcp_url: str | None = None) -> "MCPStreamableHTTPTool":
    """Create MCPStreamableHTTPTool for GraphRAG server.

    Args:
        mcp_url: MCP server URL (default: from config or http://localhost:8011/mcp)

    Returns:
        MCPStreamableHTTPTool: Configured MCP tool
    """
    from agent_framework import MCPStreamableHTTPTool

    config = get_agent_config()
    url = mcp_url or config.mcp_server_url

    # Ensure URL ends with /mcp (not /sse)
    if url.endswith("/sse"):
        url = url.replace("/sse", "/mcp")
    elif not url.endswith("/mcp"):
        url = url.rstrip("/") + "/mcp"

    return MCPStreamableHTTPTool(
        name="graphrag", url=url, description="Query the GraphRAG knowledge graph for entity and thematic information"
    )


def create_client() -> "SupportsChatGetResponse":
    """Create an LLM chat client based on the configured provider.

    Dispatches to ``AzureOpenAIChatClient`` when ``api_host='azure'``,
    or ``OpenAIChatClient`` for GitHub Models / OpenAI / Ollama.

    Returns:
        A chat client implementing ``SupportsChatGetResponse``.
    """
    config = get_agent_config()

    if config.api_host == "azure":
        from agent_framework.azure import AzureOpenAIChatClient

        return AzureOpenAIChatClient(
            endpoint=config.azure_endpoint,
            deployment_name=config.deployment_name,
            api_key=config.api_key if not config.uses_azure_cli else None,
            api_version=config.api_version,
        )

    from agent_framework.openai import OpenAIChatClient

    return OpenAIChatClient(
        model_id=config.model_id,
        api_key=config.provider_api_key,
        base_url=config.provider_base_url,
    )


# Backward-compatible alias — workflows import this name.
create_azure_client = create_client


def create_knowledge_captain(
    mcp_url: str | None = None,
    system_prompt: str | None = None,
    middleware: list["AgentMiddleware | ChatMiddleware | FunctionMiddleware"] | None = None,
    local_tools: list[object] | None = None,
) -> "Agent":
    """Create the Knowledge Captain agent with MCP tool.

    The Knowledge Captain uses GPT-4o with a system prompt that guides
    tool selection. No separate routing logic is needed - GPT-4o decides
    which MCP tool to call based on the prompt.

    The returned Agent is an async context manager that manages the MCP
    tool connection lifecycle automatically (rc5+).

    When no ``middleware`` is provided, a default observability stack is
    injected: ``TimingAgentMiddleware``, ``TokenCountingChatMiddleware``,
    and ``LoggingFunctionMiddleware``.

    Args:
        mcp_url: Optional MCP server URL override
        system_prompt: Optional system prompt override
        middleware: Optional middleware list (overrides defaults)
        local_tools: Optional list of ``@tool``-decorated functions to add
            alongside the MCP tool. These run locally (no MCP round-trip).

    Returns:
        Agent: Use as async context manager — ``async with agent:``

    Example:
        from agents.tools import format_as_table, extract_key_entities

        agent = create_knowledge_captain(
            local_tools=[format_as_table, extract_key_entities],
        )
        async with agent:
            result = await agent.run("Who leads Project Alpha?")
            print(result.text)
    """
    from agent_framework import Agent

    client = create_client()
    mcp_tool = create_mcp_tool(mcp_url)

    tools: list[object] = [mcp_tool]
    if local_tools:
        tools.extend(local_tools)

    if middleware is None:
        middleware = _default_middleware()

    return Agent(
        client=client,
        name="knowledge_captain",
        instructions=system_prompt or KNOWLEDGE_CAPTAIN_PROMPT,
        tools=tools,
        middleware=middleware,
    )


def _default_middleware() -> list["AgentMiddleware | ChatMiddleware | FunctionMiddleware"]:
    """Build the default observability middleware stack.

    Returns:
        List of ``[TimingAgentMiddleware, TokenCountingChatMiddleware, LoggingFunctionMiddleware]``.
    """
    return [
        TimingAgentMiddleware(),
        TokenCountingChatMiddleware(),
        LoggingFunctionMiddleware(),
    ]


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


class KnowledgeCaptainRunner:
    """Context manager for running Knowledge Captain queries.

    Handles MCP connection lifecycle via Agent context manager (rc5+)
    and provides a simple interface for asking questions. Maintains
    conversation history across multiple questions in the same session.

    Example:
        async with KnowledgeCaptainRunner() as runner:
            response = await runner.ask("Who leads Project Alpha?")
            print(response.text)
            print(f"Tokens used: {response.token_count}")

            ### Follow-up questions remember context
            response2 = await runner.ask("What about Project Beta?")
    """

    def __init__(
        self,
        mcp_url: str | None = None,
        system_prompt: str | None = None,
        middleware: list["AgentMiddleware | ChatMiddleware | FunctionMiddleware"] | None = None,
        local_tools: list[object] | None = None,
    ):
        """Initialize the runner.

        Args:
            mcp_url: Optional MCP server URL override
            system_prompt: Optional system prompt override
            middleware: Optional middleware list (overrides defaults)
            local_tools: Optional ``@tool`` functions to add alongside MCP
        """
        self.agent = create_knowledge_captain(
            mcp_url=mcp_url,
            system_prompt=system_prompt,
            middleware=middleware,
            local_tools=local_tools,
        )
        self._connected = False
        self._session: AgentSession | None = None

    @property
    def token_counter(self) -> TokenCountingChatMiddleware | None:
        """Return the token-counting middleware if present in the agent's stack."""
        middleware_list = getattr(self.agent, "middleware", None) or []
        for mw in middleware_list:
            if isinstance(mw, TokenCountingChatMiddleware):
                return mw
        return None

    async def __aenter__(self) -> "KnowledgeCaptainRunner":
        """Connect to MCP server via Agent context manager and initialize session."""
        from agent_framework import AgentSession

        await self.agent.__aenter__()
        self._connected = True
        self._session = AgentSession()
        return self

    async def __aexit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        """Disconnect from MCP server via Agent context manager."""
        await self.agent.__aexit__(exc_type, exc_val, exc_tb)
        self._connected = False
        self._session = None

    async def ask(self, question: str) -> AgentResponse:
        """Ask the Knowledge Captain a question.

        Maintains conversation history - follow-up questions will have
        context from previous exchanges in this session.

        Uses an internal timeout of 120 seconds via ``asyncio.timeout``.

        Args:
            question: The question to ask

        Returns:
            AgentResponse: The agent's response

        Raises:
            RuntimeError: If not connected (not in async context)
        """
        if not self._connected:
            raise RuntimeError("Not connected to MCP server. Use 'async with KnowledgeCaptainRunner()'")

        try:
            async with asyncio.timeout(120.0):
                result = await self.agent.run(question, session=self._session)
        except TimeoutError:
            return AgentResponse(text="Request timed out. Please try again.")

        return AgentResponse(
            text=result.text,
            token_count=self.token_counter.total_tokens if self.token_counter else None,
        )

    def clear_history(self) -> None:
        """Clear conversation history, starting fresh.

        Use this to reset context without disconnecting from MCP server.
        """
        from agent_framework import AgentSession

        self._session = AgentSession()
