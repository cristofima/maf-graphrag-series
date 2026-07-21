"""Shim package that exposes ``src/agents`` for ``python -m`` execution."""

from __future__ import annotations

import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
_PKG = _SRC / "agents"

src_path = str(_SRC)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

__path__ = [str(_PKG)]

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
