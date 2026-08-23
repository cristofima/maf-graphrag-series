"""
MAF + GraphRAG Series - Agents Module
=====================================

Part 3: Supervisor Agent Pattern (Microsoft Agent Framework)

This module provides shared utilities for agent creation and MCP connectivity.
All conversational routing is handled by the RouterWorkflow entry point.

Modules:
    - config: Agent and LLM provider configuration
    - middleware: Three-layer observability middleware pipeline
    - prompts: System prompts for agent configuration
    - supervisor: Agent creation and MCP connectivity utilities
"""

from agents.config import AgentConfig, SessionConfig, get_agent_config, get_session_config
from agents.middleware import (
    LoggingFunctionMiddleware,
    QueryRewritingChatMiddleware,
    TimingAgentMiddleware,
    TokenCountingChatMiddleware,
)
from agents.prompts import RESEARCH_DELEGATE_PROMPT, SIMPLE_ASSISTANT_PROMPT
from agents.session_store import (
    InMemorySessionStore,
    SessionCompactionDiagnostics,
    SessionKey,
    SessionRecord,
    SessionStoreMetrics,
)
from agents.supervisor import (
    create_azure_client,
    create_client,
    create_mcp_tool,
    create_research_delegate,
)
from agents.tools import extract_key_entities, format_as_table

__all__ = [
    # Configuration
    "AgentConfig",
    "SessionConfig",
    "get_agent_config",
    "get_session_config",
    # Middleware
    "TimingAgentMiddleware",
    "TokenCountingChatMiddleware",
    "LoggingFunctionMiddleware",
    "QueryRewritingChatMiddleware",
    # Prompts
    "SIMPLE_ASSISTANT_PROMPT",
    "RESEARCH_DELEGATE_PROMPT",
    # Session store
    "SessionKey",
    "SessionRecord",
    "SessionCompactionDiagnostics",
    "SessionStoreMetrics",
    "InMemorySessionStore",
    # Supervisor
    "create_client",
    "create_azure_client",
    "create_mcp_tool",
    "create_research_delegate",
    # Local Tools
    "format_as_table",
    "extract_key_entities",
]
