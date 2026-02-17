"""
MAF + GraphRAG Series - Agents Module
=====================================

Part 3: Supervisor Agent Pattern (Microsoft Agent Framework)

This module provides the Knowledge Captain agent that queries GraphRAG
via MCP. The agent uses GPT-4o with a system prompt to decide which
GraphRAG tool to call - no complex routing logic needed.

See README.md for architecture diagrams and detailed documentation.

Modules:
    - config: Agent and Azure OpenAI configuration
    - prompts: System prompts for the Knowledge Captain
    - supervisor: Knowledge Captain agent with MCP tool

Usage:
    # Quick usage with context manager
    from agents import KnowledgeCaptainRunner
    
    async with KnowledgeCaptainRunner() as runner:
        response = await runner.ask("Who leads Project Alpha?")
        print(response.text)
    
    # Or use the CLI
    poetry run python run_agent.py
"""

from agents.config import AgentConfig, get_agent_config
from agents.prompts import KNOWLEDGE_CAPTAIN_PROMPT, SIMPLE_ASSISTANT_PROMPT
from agents.supervisor import (
    KnowledgeCaptainRunner,
    create_knowledge_captain,
    create_mcp_tool,
    AgentResponse,
)

__all__ = [
    # Configuration
    "AgentConfig",
    "get_agent_config",
    # Prompts
    "KNOWLEDGE_CAPTAIN_PROMPT",
    "SIMPLE_ASSISTANT_PROMPT",
    # Supervisor
    "KnowledgeCaptainRunner",
    "create_knowledge_captain",
    "create_mcp_tool",
    "AgentResponse",
]
