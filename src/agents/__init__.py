"""
MAF + GraphRAG Series - Agents Module
=====================================

Part 3: Supervisor Agent Pattern (Microsoft Agent Framework)

This module provides the Knowledge Captain agent that queries GraphRAG
via MCP. The agent uses GPT-4o with a system prompt to decide which
GraphRAG tool to call - no complex routing logic needed.

Supports multiple LLM providers (Azure OpenAI, GitHub Models, OpenAI,
Ollama) via the ``API_HOST`` environment variable.

See README.md for architecture diagrams and detailed documentation.

Modules:
    - config: Agent and LLM provider configuration
    - middleware: Three-layer observability middleware pipeline
    - prompts: System prompts for the Knowledge Captain
    - supervisor: Knowledge Captain agent with MCP tool

Usage:
    # Quick usage with context manager
    from agents import KnowledgeCaptainRunner

    async with KnowledgeCaptainRunner() as runner:
        response = await runner.ask("Who leads Project Alpha?")
        print(response.text)

    # Or use Agent directly (rc5+)
    from agents import create_knowledge_captain

    agent = create_knowledge_captain()
    async with agent:
        result = await agent.run("Who leads Project Alpha?")
        print(result.text)

    # Or use the CLI
    poetry run python run_agent.py
"""

from agents.config import AgentConfig, get_agent_config, is_azure
from agents.middleware import (
    LoggingFunctionMiddleware,
    QueryRewritingChatMiddleware,
    SummarizationMiddleware,
    TimingAgentMiddleware,
    TokenCountingChatMiddleware,
)
from agents.prompts import KNOWLEDGE_CAPTAIN_PROMPT, RESEARCH_DELEGATE_PROMPT, SIMPLE_ASSISTANT_PROMPT
from agents.supervisor import (
    AgentResponse,
    KnowledgeCaptainRunner,
    create_azure_client,
    create_client,
    create_knowledge_captain,
    create_mcp_tool,
    create_research_delegate,
)
from agents.tools import extract_key_entities, format_as_table

__all__ = [
    # Configuration
    "AgentConfig",
    "get_agent_config",
    "is_azure",
    # Middleware
    "TimingAgentMiddleware",
    "TokenCountingChatMiddleware",
    "LoggingFunctionMiddleware",
    "QueryRewritingChatMiddleware",
    "SummarizationMiddleware",
    # Prompts
    "KNOWLEDGE_CAPTAIN_PROMPT",
    "SIMPLE_ASSISTANT_PROMPT",
    "RESEARCH_DELEGATE_PROMPT",
    # Supervisor
    "KnowledgeCaptainRunner",
    "create_knowledge_captain",
    "create_client",
    "create_azure_client",
    "create_mcp_tool",
    "create_research_delegate",
    "AgentResponse",
    # Local Tools
    "format_as_table",
    "extract_key_entities",
]
