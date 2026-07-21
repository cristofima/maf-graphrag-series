"""Shim package that exposes ``src/agents`` for ``python -m`` execution."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
_PKG = _SRC / "agents"

src_path = str(_SRC)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

__path__ = [str(_PKG)]

_SYMBOL_TO_MODULE = {
    # Configuration
    "AgentConfig": "agents.config",
    "get_agent_config": "agents.config",
    "is_azure": "agents.config",
    # Middleware
    "TimingAgentMiddleware": "agents.middleware",
    "TokenCountingChatMiddleware": "agents.middleware",
    "LoggingFunctionMiddleware": "agents.middleware",
    "QueryRewritingChatMiddleware": "agents.middleware",
    "SummarizationMiddleware": "agents.middleware",
    # Prompts
    "KNOWLEDGE_CAPTAIN_PROMPT": "agents.prompts",
    "SIMPLE_ASSISTANT_PROMPT": "agents.prompts",
    "RESEARCH_DELEGATE_PROMPT": "agents.prompts",
    # Supervisor
    "KnowledgeCaptainRunner": "agents.supervisor",
    "create_knowledge_captain": "agents.supervisor",
    "create_client": "agents.supervisor",
    "create_azure_client": "agents.supervisor",
    "create_mcp_tool": "agents.supervisor",
    "create_research_delegate": "agents.supervisor",
    "AgentResponse": "agents.supervisor",
    # Local tools
    "format_as_table": "agents.tools",
    "extract_key_entities": "agents.tools",
}

__all__ = [
    "AgentConfig",
    "get_agent_config",
    "is_azure",
    "TimingAgentMiddleware",
    "TokenCountingChatMiddleware",
    "LoggingFunctionMiddleware",
    "QueryRewritingChatMiddleware",
    "SummarizationMiddleware",
    "KNOWLEDGE_CAPTAIN_PROMPT",
    "SIMPLE_ASSISTANT_PROMPT",
    "RESEARCH_DELEGATE_PROMPT",
    "KnowledgeCaptainRunner",
    "create_knowledge_captain",
    "create_client",
    "create_azure_client",
    "create_mcp_tool",
    "create_research_delegate",
    "AgentResponse",
    "format_as_table",
    "extract_key_entities",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve public symbols from the real package modules."""
    module_name = _SYMBOL_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

    module = importlib.import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
