"""
Knowledge Captain Supervisor - MCP-Based Agent.

This module provides the Knowledge Captain agent that uses MCPStreamableHTTPTool
to connect to the GraphRAG MCP Server. The agent decides which tool to use
based on its system prompt (no separate routing logic needed).

See README.md for architecture diagrams and detailed documentation.

Usage:
    from agents.supervisor import create_knowledge_captain, KnowledgeCaptainRunner
    
    # Option 1: Quick setup
    async with KnowledgeCaptainRunner() as runner:
        response = await runner.ask("Who leads Project Alpha?")
    
    # Option 2: Manual setup
    mcp_tool, agent = create_knowledge_captain()
    async with mcp_tool:
        result = await agent.run("Who leads Project Alpha?")
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from dotenv import load_dotenv

from agents.config import get_agent_config
from agents.prompts import KNOWLEDGE_CAPTAIN_PROMPT

if TYPE_CHECKING:
    from agent_framework import Agent, MCPStreamableHTTPTool

# Load environment variables
load_dotenv()


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
        name="graphrag",
        url=url,
        description="Query the GraphRAG knowledge graph for entity and thematic information"
    )


def create_azure_client():
    """Create Azure OpenAI chat client for Agent Framework.
    
    Returns:
        AzureOpenAIChatClient: Configured chat client that implements SupportsChatGetResponse
    """
    from agent_framework.azure import AzureOpenAIChatClient
    
    config = get_agent_config()
    
    return AzureOpenAIChatClient(
        endpoint=config.azure_endpoint,
        deployment_name=config.deployment_name,
        api_key=config.api_key if not config.uses_azure_cli else None,
        api_version=config.api_version,
    )


def create_knowledge_captain(
    mcp_url: str | None = None,
    system_prompt: str | None = None,
) -> tuple["MCPStreamableHTTPTool", "Agent"]:
    """Create the Knowledge Captain agent with MCP tool.
    
    The Knowledge Captain uses GPT-4o with a system prompt that guides
    tool selection. No separate routing logic is needed - GPT-4o decides
    which MCP tool to call based on the prompt.
    
    Args:
        mcp_url: Optional MCP server URL override
        system_prompt: Optional system prompt override
        
    Returns:
        tuple: (mcp_tool, agent) - Use mcp_tool as async context manager
        
    Example:
        mcp_tool, agent = create_knowledge_captain()
        async with mcp_tool:
            result = await agent.run("Who leads Project Alpha?")
            print(result.text)
    """
    from agent_framework import Agent
    
    client = create_azure_client()
    mcp_tool = create_mcp_tool(mcp_url)
    
    agent = Agent(
        client=client,
        name="knowledge_captain",
        instructions=system_prompt or KNOWLEDGE_CAPTAIN_PROMPT,
        tools=[mcp_tool],
    )
    
    return mcp_tool, agent


class KnowledgeCaptainRunner:
    """Context manager for running Knowledge Captain queries.
    
    Handles MCP connection lifecycle and provides a simple interface
    for asking questions. Maintains conversation history across multiple
    questions in the same session.
    
    Example:
        async with KnowledgeCaptainRunner() as runner:
            response = await runner.ask("Who leads Project Alpha?")
            print(response.text)
            
            ### Follow-up questions remember context
            response2 = await runner.ask("What about Project Beta?")
    """
    
    def __init__(
        self,
        mcp_url: str | None = None,
        system_prompt: str | None = None,
    ):
        """Initialize the runner.
        
        Args:
            mcp_url: Optional MCP server URL override
            system_prompt: Optional system prompt override
        """
        self.mcp_tool, self.agent = create_knowledge_captain(
            mcp_url=mcp_url,
            system_prompt=system_prompt,
        )
        self._connected = False
        self._session = None
    
    async def __aenter__(self) -> "KnowledgeCaptainRunner":
        """Connect to MCP server and initialize session."""
        from agent_framework import AgentSession
        
        await self.mcp_tool.__aenter__()
        self._connected = True
        self._session = AgentSession()  # Create session for conversation history
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Disconnect from MCP server."""
        await self.mcp_tool.__aexit__(exc_type, exc_val, exc_tb)
        self._connected = False
        self._session = None
    
    async def ask(self, question: str) -> AgentResponse:
        """Ask the Knowledge Captain a question.
        
        Maintains conversation history - follow-up questions will have
        context from previous exchanges in this session.
        
        Args:
            question: The question to ask
            
        Returns:
            AgentResponse: The agent's response
            
        Raises:
            RuntimeError: If not connected (not in async context)
        """
        if not self._connected:
            raise RuntimeError(
                "Not connected to MCP server. Use 'async with KnowledgeCaptainRunner()'"
            )
        
        result = await self.agent.run(question, session=self._session)
        
        return AgentResponse(
            text=result.text,
            # Note: tools_used and token_count depend on agent framework version
        )
    
    def clear_history(self):
        """Clear conversation history, starting fresh.
        
        Use this to reset context without disconnecting from MCP server.
        """
        from agent_framework import AgentSession
        self._session = AgentSession()
