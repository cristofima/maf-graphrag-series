# Agents Module

Supervisor Agent Pattern with Microsoft Agent Framework

## Overview

This module implements the **Knowledge Captain** agent that queries GraphRAG via MCP. The agent uses GPT-4o with a system prompt to decide which tool to call—no complex routing logic needed.

**Features:**
- System prompt-based tool routing (no code router)
- Conversation memory for follow-up questions
- Single MCP connection to GraphRAG server

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Knowledge Captain (GPT-4o)                             │
│  ┌────────────────────────────────────────────────────┐ │
│  │ System Prompt guides tool selection:               │ │
│  │ - local_search → entity questions                  │ │
│  │ - global_search → thematic questions               │ │
│  └────────────────────────────────────────────────────┘ │
│                        │                                │
│          GPT-4o decides which MCP tool to call          │
│                        │                                │
│                        ▼                                │
│            MCPStreamableHTTPTool                        │
└────────────────────────┼────────────────────────────────┘
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

| Question Type | Tool Selected | Example |
|---------------|---------------|---------|
| Entity-focused | `local_search` | "Who leads Project Alpha?" |
| Thematic | `global_search` | "What are the main themes?" |
| Browse | `list_entities` | "What entities exist?" |
| Details | `get_entity` | "Tell me about David Kumar" |

## Module Structure

```
agents/
├── __init__.py      # Re-exports
├── config.py        # Azure OpenAI configuration
├── prompts.py       # System prompts for the agent
├── supervisor.py    # Knowledge Captain with MCP tool
└── README.md        # This file
```

## Quick Start

### Prerequisites

1. MCP Server running: `poetry run python run_mcp_server.py`
2. Knowledge graph built: `poetry run python -m core.index`
3. Azure OpenAI configured in `.env`

### Environment Variables

```bash
# Required
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o

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

| Command | Description |
|---------|-------------|
| `clear` | Clear conversation history |
| `quit` / `exit` | Exit the chat |

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

mcp_tool, agent = create_knowledge_captain()

async with mcp_tool:
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

## MCP Transport Protocol

This module uses the **Streamable HTTP** transport (`/mcp` endpoint) instead of SSE (`/sse`):

| Transport | Endpoint | Use Case |
|-----------|----------|----------|
| **Streamable HTTP** | `/mcp` | Microsoft Agent Framework (`MCPStreamableHTTPTool`) |
| **SSE** | `/sse` | MCP Inspector, browser-based clients |

**Why Streamable HTTP?**
- Required by `MCPStreamableHTTPTool` from Agent Framework
- Bidirectional communication (client can send multiple requests)
- Better suited for agent-to-server interaction
- SSE is unidirectional (server-push only), designed for browser clients

The MCP Server exposes both endpoints, but agents always connect via `/mcp`.

## Architecture Benefits

```
agents/supervisor.py      ← Single agent with MCPStreamableHTTPTool
```

- **Single source of truth** — All GraphRAG tools live in `mcp_server/`
- **System prompt routing** — GPT-4o decides which tool to call (no code router)
- **Simpler architecture** — One agent, one MCP connection
- **Easier maintenance** — Update tools in one place

## References

- [Microsoft Agent Framework Documentation](https://learn.microsoft.com/agent-framework/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [GraphRAG Documentation](https://microsoft.github.io/graphrag/)
