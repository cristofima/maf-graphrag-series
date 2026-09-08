"""Agent utilities for Microsoft Agent Framework integrations.

The agents package supplies configuration objects, telemetry middleware,
session-store helpers, and factory functions used by router-first workflows.
All conversational routing continues to be coordinated by
``RouterWorkflow`` inside ``maf_graphrag.workflows``.

Modules:
    - config: Load and validate agent + session configuration from env vars.
    - factories: Create Azure OpenAI chat clients and MCP tool adapters.
    - middleware: Instrument Agent Framework pipelines with observability hooks.
    - session_store: Persist router session metadata and diagnostics.
    - tools: Local utility tools surfaced to agents.
"""

from maf_graphrag.agents.config import AgentConfig, SessionConfig, get_agent_config, get_session_config
from maf_graphrag.agents.factories import (
    create_azure_client,
    create_client,
    create_mcp_tool,
)
from maf_graphrag.agents.middleware import (
    LoggingFunctionMiddleware,
    QueryRewritingChatMiddleware,
    TimingAgentMiddleware,
    TokenCountingChatMiddleware,
)
from maf_graphrag.agents.session_store import (
    ActiveWorkflowRun,
    InMemorySessionStore,
    SessionCompactionDiagnostics,
    SessionKey,
    SessionRecord,
    SessionStoreMetrics,
)
from maf_graphrag.agents.tools import extract_key_entities, format_as_table

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
    # Session store
    "SessionKey",
    "SessionRecord",
    "SessionCompactionDiagnostics",
    "SessionStoreMetrics",
    "InMemorySessionStore",
    "ActiveWorkflowRun",
    # Factories
    "create_client",
    "create_azure_client",
    "create_mcp_tool",
    # Local Tools
    "format_as_table",
    "extract_key_entities",
]
