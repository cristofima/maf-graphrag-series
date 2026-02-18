# Part 3 Implementation Notes: Supervisor Agent Pattern

## Overview

Part 3 implements the **Knowledge Captain** agent pattern using Microsoft Agent Framework with the MCP Server from Part 2. The agent queries the GraphRAG knowledge graph via `MCPStreamableHTTPTool`, with GPT-4o deciding which tool to use based on its system prompt.

**Key Decisions:**
- Tool routing via System Prompt (no SLM required for tutorial scope)
- Conversation memory via `AgentSession`
- MCP transport changed from SSE to Streamable HTTP

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Knowledge Captain Agent (GPT-4o)                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ SYSTEM PROMPT:                                         │ │
│  │ "Use local_search for entity questions...              │ │
│  │  Use global_search for thematic questions..."          │ │
│  └────────────────────────────────────────────────────────┘ │
│                        │                                    │
│          GPT-4o decides which tool to use                   │
│                        │                                    │
│                        ▼                                    │
│            MCPStreamableHTTPTool                            │
└────────────────────────┼────────────────────────────────────┘
                         │ Streamable HTTP (/mcp)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  MCP Server (port 8011)                                     │
│  ├── local_search(query, ...)                               │
│  ├── global_search(query, ...)                              │
│  ├── list_entities(entity_type)                             │
│  └── get_entity(name)                                       │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  GraphRAG Core (Part 1)                                     │
│  └── Knowledge Graph (LanceDB + Parquet)                    │
└─────────────────────────────────────────────────────────────┘
```

**Why System Prompt Routing (vs SLM)?**

| Approach | Latency | Complexity | Decision |
|----------|---------|------------|----------|
| **System Prompt only** | Low | Low | ✅ Used |
| SLM pre-filter + GPT-4o | Slightly higher | High | ❌ Deferred |

> Cost per query depends entirely on prompt length, conversation history, and response size — no fixed per-query figure applies. For actual token pricing see the [Azure OpenAI pricing page](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/).

For tutorial scope, GPT-4o + System Prompt is sufficient. SLM routing is a production optimization for high-volume scenarios (>1000 queries/day).

---

## Implementation Details

### Files Created

| File | Purpose |
|------|---------|
| [agents/__init__.py](../agents/__init__.py) | Public API exports |
| [agents/config.py](../agents/config.py) | Azure OpenAI and MCP configuration |
| [agents/prompts.py](../agents/prompts.py) | Knowledge Captain system prompt |
| [agents/supervisor.py](../agents/supervisor.py) | Agent implementation with MCPStreamableHTTPTool |
| [agents/README.md](../agents/README.md) | Module documentation |
| [run_agent.py](../run_agent.py) | Interactive CLI for Knowledge Captain |

### Key Components

#### 1. AgentConfig (`agents/config.py`)

Typed configuration using dataclasses with validation:

```python
@dataclass
class AgentConfig:
    azure_endpoint: str      # AZURE_OPENAI_ENDPOINT
    deployment_name: str     # AZURE_OPENAI_CHAT_DEPLOYMENT (default: gpt-4o)
    api_key: str            # AZURE_OPENAI_API_KEY
    api_version: str        # Default: 2024-10-21
    mcp_server_url: str     # Default: http://127.0.0.1:8011/mcp
```

#### 2. Knowledge Captain System Prompt (`agents/prompts.py`)

Guides tool selection without programmatic routing:

```python
KNOWLEDGE_CAPTAIN_PROMPT = """You are the Knowledge Captain...

## Available Tools (via graphrag MCP)

1. **local_search** - Use for entity-focused questions:
   - Questions about specific people ("Who leads Project Alpha?")
   - Relationship questions ("What is the connection between X and Y?")

2. **global_search** - Use for thematic/pattern questions:
   - Organizational overviews ("What are the main projects?")
   - Cross-cutting themes ("What technologies are used?")

3. **list_entities** - Use to browse available entities

4. **get_entity** - Use for detailed entity info
"""
```

#### 3. Agent Creation (`agents/supervisor.py`)

Uses Microsoft Agent Framework patterns:

```python
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.azure import AzureOpenAIChatClient

def create_knowledge_captain():
    client = AzureOpenAIChatClient(
        endpoint=config.azure_endpoint,
        deployment_name=config.deployment_name,
        api_key=config.api_key,
    )
    
    mcp_tool = MCPStreamableHTTPTool(
        name="graphrag",
        url=config.mcp_server_url,  # http://127.0.0.1:8011/mcp
        description="Query the GraphRAG knowledge graph"
    )
    
    agent = Agent(
        client=client,
        name="knowledge_captain",
        instructions=KNOWLEDGE_CAPTAIN_PROMPT,
        tools=[mcp_tool],
    )
    
    return mcp_tool, agent
```

#### 4. Conversation Memory (`agents/supervisor.py`)

`AgentSession` maintains history across multiple questions:

```python
from agent_framework import AgentSession

class KnowledgeCaptainRunner:
    async def __aenter__(self):
        self._session = AgentSession()
        return self
    
    async def ask(self, question: str):
        # Session preserves conversation context
        return await self.agent.run(question, session=self._session)
    
    def clear_history(self):
        self._session = AgentSession()  # Reset to fresh state
```

---

## MCP Server Changes

### Transport Protocol Update

Changed from SSE to Streamable HTTP for Agent Framework compatibility:

**Before (Part 2):**
```python
# mcp_server/server.py
app = mcp.sse_app()  # Server-Sent Events on /sse
```

**After (Part 3):**
```python
# mcp_server/server.py
app = mcp.streamable_http_app()  # Streamable HTTP on /mcp
```

### Why This Change?

| Client Type | Required Transport | Endpoint |
|-------------|-------------------|----------|
| MCP Inspector (browser) | SSE | `/sse` |
| MCPStreamableHTTPTool (Agent Framework) | Streamable HTTP | `/mcp` |

The Agent Framework's `MCPStreamableHTTPTool` specifically requires Streamable HTTP protocol. SSE is designed for browser clients with long-polling.

---

## Usage

### Prerequisites

1. MCP Server running (from Part 2):
   ```powershell
   poetry run python run_mcp_server.py
   ```

2. Environment variables configured:
   ```
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_API_KEY=your-key
   AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
   ```

### Interactive CLI

```powershell
poetry run python run_agent.py
```

Commands:
- Type a question to query the knowledge graph
- `clear` - Reset conversation history
- `help` - Show available commands
- `exit` / `quit` - Exit the CLI

### Programmatic Usage

```python
from agents import KnowledgeCaptainRunner

async with KnowledgeCaptainRunner() as runner:
    # First question
    response = await runner.ask("Who leads Project Alpha?")
    print(response.text)
    
    # Follow-up (has context from previous question)
    response = await runner.ask("What is their background?")
    print(response.text)
    
    # Reset conversation
    runner.clear_history()
```

---

## Testing

### Manual Verification

```powershell
# Terminal 1: Start MCP Server
poetry run python run_mcp_server.py

# Terminal 2: Run agent
poetry run python run_agent.py
```

Example session:
```
Knowledge Captain initialized
Type your question (or 'help' for commands):

> Who leads Project Alpha?
Dr. Sarah Chen leads Project Alpha...

> What about Project Beta?
Marcus Johnson is the team lead for Project Beta...

> clear
Conversation history cleared.

> exit
Goodbye!
```

### Conversation Memory Verification

```
> Who leads Project Alpha?
Dr. Sarah Chen leads Project Alpha. She serves as the Innovation Director...

> What is her background?
Dr. Sarah Chen has a background in AI research. She previously worked at...
```

The second question correctly references "her" from the first question's context.

---

## What Was Deferred

Features analyzed but deferred to later parts:

| Feature | Deferred To | Reason |
|---------|-------------|--------|
| SLM Routing (Phi-3/4) | Series B | Tutorial doesn't need cost optimization |
| Semantic Cache | Part 8 | Production optimization |
| Multiple Agent Specialists | Part 4+ | Current single-agent is sufficient |
| Tool Registry | Part 7 | Dynamic discovery not needed yet |
| Human-in-the-Loop | Part 6 | Approval workflows separate concern |

---

## Dependencies

```toml
# pyproject.toml
[tool.poetry.dependencies]
agent-framework-core = "^1.0.0b260212"  # Microsoft Agent Framework
```

Key imports:
- `from agent_framework import Agent, MCPStreamableHTTPTool, AgentSession`
- `from agent_framework.azure import AzureOpenAIChatClient`
