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

_MOD_CONFIG = "agents.config"
_MOD_MIDDLEWARE = "agents.middleware"
_MOD_PROMPTS = "agents.prompts"
_MOD_SUPERVISOR = "agents.supervisor"
_MOD_TOOLS = "agents.tools"
_MOD_ROUTER_CLASSIFIER = "agents.router_classifier"

_SYMBOL_TO_MODULE = {
    # Configuration
    "AgentConfig": _MOD_CONFIG,
    "get_agent_config": _MOD_CONFIG,
    # Middleware
    "TimingAgentMiddleware": _MOD_MIDDLEWARE,
    "TokenCountingChatMiddleware": _MOD_MIDDLEWARE,
    "LoggingFunctionMiddleware": _MOD_MIDDLEWARE,
    "QueryRewritingChatMiddleware": _MOD_MIDDLEWARE,
    # Prompts
    "SIMPLE_ASSISTANT_PROMPT": _MOD_PROMPTS,
    "RESEARCH_DELEGATE_PROMPT": _MOD_PROMPTS,
    # Supervisor
    "create_client": _MOD_SUPERVISOR,
    "create_azure_client": _MOD_SUPERVISOR,
    "create_mcp_tool": _MOD_SUPERVISOR,
    "create_research_delegate": _MOD_SUPERVISOR,
    # Local tools
    "format_as_table": _MOD_TOOLS,
    "extract_key_entities": _MOD_TOOLS,
    # Router classifier
    "RouterClassifier": _MOD_ROUTER_CLASSIFIER,
    "RouterClassifierError": _MOD_ROUTER_CLASSIFIER,
    "RouterClassification": _MOD_ROUTER_CLASSIFIER,
}

__all__ = [
    "AgentConfig",
    "get_agent_config",
    "TimingAgentMiddleware",
    "TokenCountingChatMiddleware",
    "LoggingFunctionMiddleware",
    "QueryRewritingChatMiddleware",
    "SIMPLE_ASSISTANT_PROMPT",
    "RESEARCH_DELEGATE_PROMPT",
    "create_client",
    "create_azure_client",
    "create_mcp_tool",
    "create_research_delegate",
    "format_as_table",
    "extract_key_entities",
    "RouterClassifier",
    "RouterClassifierError",
    "RouterClassification",
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
