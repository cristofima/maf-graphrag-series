# Agents Module

Supervisor Agent Pattern with Microsoft Agent Framework

## Overview

This module implements the **Knowledge Captain** agent that queries GraphRAG via MCP. The agent uses GPT-4o with a system prompt to decide which tool to call—no complex routing logic needed.

**Features:**

- Multi-provider LLM support (Azure OpenAI, GitHub Models, OpenAI, Ollama)
- System prompt-based tool routing (no code router)
- Three-layer middleware pipeline (timing, token counting, logging, query rewriting, summarization)
- Local `@tool` functions for formatting and extraction (no MCP round-trip)
- Research delegate sub-agent for context-isolated deep dives
- Conversation memory for follow-up questions
- Single MCP connection to GraphRAG server

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Knowledge Captain (GPT-4o / GitHub Models / OpenAI / Ollama)       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ System Prompt guides tool selection:                           │ │
│  │ - local_search → entity questions                              │ │
│  │ - global_search → thematic questions                           │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Middleware Pipeline (configurable):                                │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐               │
│  │ Timing   │→ │ TokenCounting│→ │ LoggingFunction  │               │
│  │ (Agent)  │  │ (Chat)       │  │ (Function)       │               │
│  └──────────┘  └──────────────┘  └──────────────────┘               │
│                                                                     │
│  Tools:                                                             │
│  ┌─────────────────────┐  ┌───────────────┐  ┌────────────────────┐ │
│  │ MCPStreamableHTTP   │  │format_as_table│  │extract_key_entities│ │
│  │ (remote — MCP)      │  │(local @tool)  │  │(local @tool)       │ │
│  └──────────┬──────────┘  └───────────────┘  └────────────────────┘ │
└─────────────┼───────────────────────────────────────────────────────┘
              │ Streamable HTTP (/mcp)
              ▼
┌─────────────────────────────────────────────────────────┐
│  MCP Server (port 8011)                                 │
│  ├── local_search    (entity-focused)                   │
│  ├── global_search   (thematic)                         │
│  ├── list_entities   (browse)                           │
│  └── get_entity      (details)                          │
└─────────────────────────────────────────────────────────┘
```

## Key Insight: System Prompt as Router

The agent doesn't need complex routing logic. The system prompt tells GPT-4o when to use each tool:

| Question Type  | Tool Selected   | Example                     |
| -------------- | --------------- | --------------------------- |
| Entity-focused | `local_search`  | "Who leads Project Alpha?"  |
| Thematic       | `global_search` | "What are the main themes?" |
| Browse         | `list_entities` | "What entities exist?"      |
| Details        | `get_entity`    | "Tell me about David Kumar" |

## Module Structure

```
agents/
├── __init__.py      # Re-exports (all public API)
├── config.py        # Multi-provider LLM configuration (Azure, GitHub, OpenAI, Ollama)
├── middleware.py     # Three-layer observability middleware pipeline
├── prompts.py       # System prompts (Knowledge Captain, Research Delegate)
├── supervisor.py    # Knowledge Captain agent, runner, research delegate, MCP tool
├── tools.py         # Local @tool functions (format_as_table, extract_key_entities)
└── README.md        # This file
```

## Quick Start

### Prerequisites

1. MCP Server running: `poetry run python run_mcp_server.py`
2. Knowledge graph built: `poetry run python -m core.index`
3. Azure OpenAI configured in `.env`

### Environment Variables

```bash
# Required (Azure — default provider)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o

# Alternative providers (set API_HOST to switch)
API_HOST=azure          # azure | github | openai | ollama
GITHUB_TOKEN=ghp_...    # When API_HOST=github
GITHUB_MODEL=openai/gpt-4.1-mini
OPENAI_API_KEY=sk-...   # When API_HOST=openai
OPENAI_MODEL=gpt-4o
OLLAMA_MODEL=llama3.2   # When API_HOST=ollama

# Optional
MCP_SERVER_URL=http://127.0.0.1:8011/mcp
```

### Running the Agent

```bash
# Interactive CLI mode
poetry run python run_agent.py

# Single query
poetry run python run_agent.py "Who leads Project Alpha?"
```

### CLI Commands

| Command         | Description                |
| --------------- | -------------------------- |
| `clear`         | Clear conversation history |
| `quit` / `exit` | Exit the chat              |

## Usage

### Using KnowledgeCaptainRunner (Recommended)

```python
from agents import KnowledgeCaptainRunner

async with KnowledgeCaptainRunner() as runner:
    # Ask questions
    response = await runner.ask("Who leads Project Alpha?")
    print(response.text)

    # Follow-up questions have context (conversation memory)
    response2 = await runner.ask("What about Project Beta?")
    print(response2.text)

    # Clear history to start fresh
    runner.clear_history()
```

### Manual Setup

```python
from agents import create_knowledge_captain

# Agent as async context manager (rc5+) — auto-manages MCP tool lifecycle
agent = create_knowledge_captain()

async with agent:
    result = await agent.run("Who leads Project Alpha?")
    print(result.text)
```

### Custom System Prompt

```python
from agents import KnowledgeCaptainRunner, SIMPLE_ASSISTANT_PROMPT

# Use simpler prompt
async with KnowledgeCaptainRunner(system_prompt=SIMPLE_ASSISTANT_PROMPT) as runner:
    response = await runner.ask("What technologies are used?")
```

## Multi-Provider LLM Support

The agent supports multiple LLM backends via the `API_HOST` environment variable:

| Provider       | `API_HOST` | Model Config Var               | Default Model         |
| -------------- | ---------- | ------------------------------ | --------------------- |
| Azure OpenAI   | `azure`    | `AZURE_OPENAI_CHAT_DEPLOYMENT` | `gpt-4o`              |
| GitHub Models  | `github`   | `GITHUB_MODEL`                 | `openai/gpt-4.1-mini` |
| OpenAI         | `openai`   | `OPENAI_MODEL`                 | `gpt-4o`              |
| Ollama (local) | `ollama`   | `OLLAMA_MODEL`                 | `llama3.2`            |

```python
# Switch provider via environment variable
import os
os.environ["API_HOST"] = "github"
os.environ["GITHUB_TOKEN"] = "ghp_..."

from agents import create_client
client = create_client()  # Returns OpenAIChatClient pointing to GitHub Models
```

## Middleware Pipeline

The agent supports a three-layer middleware pipeline for observability and context management:

| Layer        | Middleware Class               | Purpose                                   |
| ------------ | ------------------------------ | ----------------------------------------- |
| **Agent**    | `TimingAgentMiddleware`        | Measures total agent execution time       |
| **Agent**    | `SummarizationMiddleware`      | Auto-summarizes long responses            |
| **Chat**     | `TokenCountingChatMiddleware`  | Tracks prompt/completion token usage      |
| **Chat**     | `QueryRewritingChatMiddleware` | Rewrites vague queries for better results |
| **Function** | `LoggingFunctionMiddleware`    | Logs MCP tool calls with arguments        |

Default stack (injected automatically): `TimingAgentMiddleware` → `TokenCountingChatMiddleware` → `LoggingFunctionMiddleware`.

```python
from agents import KnowledgeCaptainRunner, QueryRewritingChatMiddleware, SummarizationMiddleware
from agents.middleware import TimingAgentMiddleware, TokenCountingChatMiddleware, LoggingFunctionMiddleware

# Custom middleware stack with query rewriting
runner = KnowledgeCaptainRunner(middleware=[
    TimingAgentMiddleware(),
    TokenCountingChatMiddleware(),
    QueryRewritingChatMiddleware(),
    LoggingFunctionMiddleware(),
])
```

## Local Tool Functions

Lightweight `@tool`-decorated functions that run locally (no MCP round-trip):

| Tool                   | Purpose                                     |
| ---------------------- | ------------------------------------------- |
| `format_as_table`      | Format a list of dicts as a Markdown table  |
| `extract_key_entities` | Extract entity names from unstructured text |

```python
from agents import create_knowledge_captain, format_as_table, extract_key_entities

# Add local tools alongside the MCP tool
agent = create_knowledge_captain(
    local_tools=[format_as_table, extract_key_entities],
)
async with agent:
    result = await agent.run("List the projects in a table")
```

## Research Delegate (Context Isolation)

A `@tool`-decorated function wrapping a research sub-agent with its own MCP session:

```python
from agents import create_research_delegate

# Create a delegate tool
delegate = create_research_delegate()

# Use as a tool in a supervisor agent
from agents import create_knowledge_captain
agent = create_knowledge_captain(local_tools=[delegate])
async with agent:
    result = await agent.run("Deep dive on Project Alpha's technology decisions")
```

The delegate provides **context isolation**: its internal conversation (raw MCP payloads) never leaks into the coordinator's context. The coordinator only sees a concise summary.

## MCP Transport Protocol

This module uses the **Streamable HTTP** transport (`/mcp` endpoint) instead of SSE (`/sse`):

| Transport           | Endpoint | Use Case                                            |
| ------------------- | -------- | --------------------------------------------------- |
| **Streamable HTTP** | `/mcp`   | Microsoft Agent Framework (`MCPStreamableHTTPTool`) |
| **SSE**             | `/sse`   | MCP Inspector, browser-based clients                |

**Why Streamable HTTP?**

- Required by `MCPStreamableHTTPTool` from Agent Framework
- Bidirectional communication (client can send multiple requests)
- Better suited for agent-to-server interaction
- SSE is unidirectional (server-push only), designed for browser clients

The MCP Server exposes both endpoints, but agents always connect via `/mcp`.

## Architecture Benefits

- **Multi-provider** — Switch LLM backend via `API_HOST` env var (Azure, GitHub, OpenAI, Ollama)
- **Agent owns its MCP tool** — `async with agent:` connects on enter, closes on exit
- **Single source of truth** — All GraphRAG tools live in `mcp_server/`
- **System prompt routing** — GPT-4o decides which tool to call (no code router)
- **Middleware pipeline** — Pluggable observability (timing, tokens, logging, query rewriting)
- **Local + remote tools** — `@tool` functions complement MCP tools without round-trips
- **Context isolation** — Research delegate encapsulates sub-agent conversations

## References

- [Microsoft Agent Framework Documentation](https://learn.microsoft.com/agent-framework/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [GraphRAG Documentation](https://microsoft.github.io/graphrag/)
