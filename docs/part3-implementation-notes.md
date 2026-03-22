# Part 3 Implementation Notes: Supervisor Agent Pattern

## Overview

Part 3 implements the **Knowledge Captain** agent pattern using Microsoft Agent Framework with the MCP Server from Part 2. The agent queries the GraphRAG knowledge graph via `MCPStreamableHTTPTool`, with GPT-4o deciding which tool to use based on its system prompt.

**Key Decisions:**

- Tool routing via System Prompt (no SLM required for tutorial scope)
- Conversation memory via `AgentSession`
- MCP transport changed from SSE to Streamable HTTP
- Multi-provider LLM support via `create_client()` (Azure, GitHub Models, OpenAI, Ollama)
- Three-layer middleware pipeline for observability
- Local `@tool` functions for formatting/extraction (no MCP round-trip)
- Research delegate pattern for context isolation
- `Agent` as async context manager for MCP lifecycle (rc5+)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Knowledge Captain Agent                                        │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ create_client()  Azure | GitHub Models | OpenAI | Ollama  │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ SYSTEM PROMPT (prompts.py):                               │  │
│  │   Captain: "Use local_search for entity questions..."     │  │
│  │   Delegate: "Perform deep searches, return summaries"     │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Middleware Pipeline:                                      │  │
│  │   TimingAgent → TokenCounting → LoggingFunction           │  │
│  │   + QueryRewriting · Summarization (optional)             │  │
│  └───────────────────────────────────────────────────────────┘  │
│                         │                                       │
│       GPT-4o decides which tool to use                          │
│            │                              │                     │
│            ▼                              ▼                     │
│  MCPStreamableHTTPTool          Local @tool functions           │
│  (graphrag MCP)                 format_as_table                 │
│                                 extract_key_entities            │
└────────────┼────────────────────────────────────────────────────┘
             │ Streamable HTTP (/mcp)
             ▼
┌─────────────────────────────────────────────────────────────────┐
│  MCP Server (port 8011)                                         │
│  ├── local_search(query, ...)                                   │
│  ├── global_search(query, ...)                                  │
│  ├── list_entities(entity_type)                                 │
│  └── get_entity(name)                                           │
└─────────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│  GraphRAG Core (Part 1)                                         │
│  └── Knowledge Graph (LanceDB + Parquet)                        │
└─────────────────────────────────────────────────────────────────┘
```

**Why System Prompt Routing (vs SLM)?**

| Approach                | Latency         | Complexity | Decision    |
| ----------------------- | --------------- | ---------- | ----------- |
| **System Prompt only**  | Low             | Low        | ✅ Used     |
| SLM pre-filter + GPT-4o | Slightly higher | High       | ❌ Deferred |

> Cost per query depends entirely on prompt length, conversation history, and response size — no fixed per-query figure applies. For actual token pricing see the [Azure OpenAI pricing page](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/).

For tutorial scope, GPT-4o + System Prompt is sufficient. SLM routing is a production optimization for high-volume scenarios (>1000 queries/day).

---

## Implementation Details

### Files Created

| File                                            | Purpose                                                         |
| ----------------------------------------------- | --------------------------------------------------------------- |
| [agents/**init**.py](../agents/__init__.py)     | Public API exports                                              |
| [agents/config.py](../agents/config.py)         | Multi-provider LLM and MCP configuration                        |
| [agents/middleware.py](../agents/middleware.py) | Three-layer observability middleware pipeline                   |
| [agents/prompts.py](../agents/prompts.py)       | Knowledge Captain + Research Delegate system prompts            |
| [agents/supervisor.py](../agents/supervisor.py) | Agent creation, multi-provider client, research delegate        |
| [agents/tools.py](../agents/tools.py)           | Local `@tool` functions (format_as_table, extract_key_entities) |
| [agents/README.md](../agents/README.md)         | Module documentation                                            |
| [run_agent.py](../run_agent.py)                 | Interactive CLI for Knowledge Captain                           |

### Key Components

#### 1. AgentConfig (`agents/config.py`)

Typed configuration using dataclasses with multi-provider validation:

```python
ApiHost = Literal["azure", "github", "openai", "ollama"]

@dataclass
class AgentConfig:
    api_host: ApiHost           # API_HOST (default: "azure")
    azure_endpoint: str         # AZURE_OPENAI_ENDPOINT
    deployment_name: str        # AZURE_OPENAI_CHAT_DEPLOYMENT (default: gpt-4o)
    api_key: str                # AZURE_OPENAI_API_KEY
    api_version: str            # Default: 2024-10-21
    mcp_server_url: str         # Default: http://127.0.0.1:8011/mcp
    auth_method: Literal["api_key", "azure_cli"]
    github_token: str           # GITHUB_TOKEN (GitHub Models)
    github_model: str           # GITHUB_MODEL (default: openai/gpt-4.1-mini)
    openai_model: str           # OPENAI_MODEL (default: gpt-4o)
    ollama_model: str           # OLLAMA_MODEL (default: llama3.2)
```

Validation per provider:

- **Azure** (default): Requires `AZURE_OPENAI_ENDPOINT`; falls back to `azure_cli` auth if no API key.
- **GitHub**: Requires `GITHUB_TOKEN`.
- **OpenAI**: Requires `OPENAI_API_KEY`.
- **Ollama**: No credentials needed (local server at `http://localhost:11434/v1/`).

#### 2. System Prompts (`agents/prompts.py`)

Centralized prompt templates guide tool selection without programmatic routing:

```python
# Three specialized prompts
KNOWLEDGE_CAPTAIN_PROMPT = """You are the Knowledge Captain...
## Available Tools (via graphrag MCP)
1. **local_search** - entity-focused questions
2. **global_search** - thematic/pattern questions
3. **list_entities** - browse available entities
4. **get_entity** - detailed entity info
"""

SIMPLE_ASSISTANT_PROMPT = """You are a helpful assistant with access
to a knowledge graph about TechVenture Inc..."""

RESEARCH_DELEGATE_PROMPT = """You are a Research Delegate — a specialist
sub-agent that performs deep knowledge graph searches and returns
concise summaries (max 3 paragraphs, under 200 words)..."""
```

| Prompt                     | Used By                      | Purpose                                               |
| -------------------------- | ---------------------------- | ----------------------------------------------------- |
| `KNOWLEDGE_CAPTAIN_PROMPT` | `create_knowledge_captain()` | Full tool-selection guidance with response formatting |
| `SIMPLE_ASSISTANT_PROMPT`  | Quick/test scenarios         | Minimal prompt for basic queries                      |
| `RESEARCH_DELEGATE_PROMPT` | `create_research_delegate()` | Context-isolated sub-agent returning summaries only   |

#### 3. Agent Creation (`agents/supervisor.py`)

Uses Microsoft Agent Framework rc5 patterns:

```python
def create_client() -> SupportsChatGetResponse:
    """Multi-provider LLM client factory."""
    config = get_agent_config()

    if config.api_host == "azure":
        from agent_framework.azure import AzureOpenAIChatClient
        return AzureOpenAIChatClient(
            endpoint=config.azure_endpoint,
            deployment_name=config.deployment_name,
            api_key=config.api_key if not config.uses_azure_cli else None,
            api_version=config.api_version,
        )

    from agent_framework.openai import OpenAIChatClient
    return OpenAIChatClient(
        model_id=config.model_id,
        api_key=config.provider_api_key,
        base_url=config.provider_base_url,
    )


def create_knowledge_captain(
    mcp_url=None, system_prompt=None, middleware=None, local_tools=None,
) -> Agent:
    """Agent as async context manager (rc5+)."""
    client = create_client()
    mcp_tool = create_mcp_tool(mcp_url)

    tools = [mcp_tool]
    if local_tools:
        tools.extend(local_tools)

    if middleware is None:
        middleware = _default_middleware()  # Timing + TokenCount + Logging

    return Agent(
        client=client,
        name="knowledge_captain",
        instructions=system_prompt or KNOWLEDGE_CAPTAIN_PROMPT,
        tools=tools,
        middleware=middleware,
    )
```

**Key changes vs initial implementation:**

- `create_client()` replaces `AzureOpenAIChatClient` direct instantiation — dispatches based on `api_host`
- `Agent` is returned directly (not `(mcp_tool, agent)` tuple) — rc5 manages MCP lifecycle via `async with agent:`
- Default middleware stack injected automatically
- Optional `local_tools` parameter for `@tool`-decorated local functions

#### 4. Conversation Memory (`agents/supervisor.py`)

`AgentSession` maintains history across multiple questions:

```python
from agent_framework import AgentSession

class KnowledgeCaptainRunner:
    async def __aenter__(self):
        self._agent = create_knowledge_captain()
        self._agent_ctx = self._agent  # Agent is an async context manager (rc5+)
        await self._agent_ctx.__aenter__()
        self._session = AgentSession()
        return self

    async def ask(self, question: str) -> AgentResponse:
        result = await self._agent.run(question, session=self._session)
        return AgentResponse(text=result.text)

    def clear_history(self):
        self._session = AgentSession()  # Reset to fresh state
```

#### 5. Middleware Pipeline (`agents/middleware.py`)

Three-layer observability pipeline following MAF's middleware design:

```python
class TimingAgentMiddleware(AgentMiddleware):        # Wraps entire agent.run()
    """Logs wall-clock time per run."""

class TokenCountingChatMiddleware(ChatMiddleware):    # Intercepts LLM calls
    """Accumulates input/output/total token counts."""

class LoggingFunctionMiddleware(FunctionMiddleware):  # Wraps tool invocations
    """Logs function name, arguments, and timing."""

class QueryRewritingChatMiddleware(ChatMiddleware):   # Resolves anaphora
    """Prepends context nudge when follow-up questions contain pronouns."""

class SummarizationAgentMiddleware(AgentMiddleware):  # Post-processing
    """Compresses long responses for downstream consumers."""
```

| Layer    | Middleware                     | Purpose                             |
| -------- | ------------------------------ | ----------------------------------- |
| Agent    | `TimingAgentMiddleware`        | Wall-clock timing per `agent.run()` |
| Agent    | `SummarizationAgentMiddleware` | Compress long responses             |
| Chat     | `TokenCountingChatMiddleware`  | Cumulative token tracking           |
| Chat     | `QueryRewritingChatMiddleware` | Anaphora resolution for follow-ups  |
| Function | `LoggingFunctionMiddleware`    | Tool call logging with timing       |

The default stack (injected by `create_knowledge_captain()` when no middleware is specified) is: `TimingAgentMiddleware` + `TokenCountingChatMiddleware` + `LoggingFunctionMiddleware`.

#### 6. Local Tool Functions (`agents/tools.py`)

Lightweight `@tool`-decorated functions that run locally (no MCP round-trip):

```python
from agent_framework import tool

@tool(name="format_as_table", approval_mode="never_require")
def format_as_table(rows: list[dict], columns: list[str] | None = None) -> str:
    """Format a list of dicts as a Markdown table."""

@tool(name="extract_key_entities", approval_mode="never_require")
def extract_key_entities(text: str) -> list[str]:
    """Extract named entities using lightweight heuristics."""
```

These complement MCP tools by handling pure formatting and extraction locally.

#### 7. Research Delegate (`agents/supervisor.py`)

Context isolation pattern — a sub-agent with its own MCP tool and session:

```python
def create_research_delegate(mcp_url=None, system_prompt=None) -> object:
    """Create a @tool-decorated function wrapping a research sub-agent."""
    client = create_client()
    mcp_tool = create_mcp_tool(mcp_url)

    delegate_agent = Agent(
        client=client,
        name="research_delegate",
        instructions=RESEARCH_DELEGATE_PROMPT,
        tools=[mcp_tool],
    )

    @tool(name="research_delegate", description="...")
    async def research_delegate(question: str) -> str:
        async with delegate_agent:
            result = await delegate_agent.run(question)
            return result.text

    return research_delegate
```

**Why context isolation matters:** The coordinator agent sees only the summary text returned by the delegate. The delegate's internal MCP payloads, tool calls, and intermediate context never leak into the coordinator's conversation history — preventing token bloat.

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

| Client Type                             | Required Transport | Endpoint |
| --------------------------------------- | ------------------ | -------- |
| MCP Inspector (browser)                 | SSE                | `/sse`   |
| MCPStreamableHTTPTool (Agent Framework) | Streamable HTTP    | `/mcp`   |

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
   # Azure OpenAI (default provider)
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_API_KEY=your-key
   AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o

   # Alternative: GitHub Models
   # API_HOST=github
   # GITHUB_TOKEN=ghp_...

   # Alternative: OpenAI
   # API_HOST=openai
   # OPENAI_API_KEY=sk-...

   # Alternative: Ollama (local, no credentials)
   # API_HOST=ollama
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

# Or use Agent directly (rc5+ async context manager)
from agents.supervisor import create_knowledge_captain

agent = create_knowledge_captain()
async with agent:
    result = await agent.run("Who leads Project Alpha?")
    print(result.text)
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

The second question correctly references "her" from the first question's context. The `QueryRewritingChatMiddleware` helps resolve such anaphora when enabled.

---

## What Was Deferred

Features analyzed but deferred to later parts:

| Feature                    | Deferred To | Reason                                  |
| -------------------------- | ----------- | --------------------------------------- |
| SLM Routing (Phi-3/4)      | Series B    | Tutorial doesn't need cost optimization |
| Semantic Cache             | Part 8      | Production optimization                 |
| Multiple Agent Specialists | Part 4      | ✅ Implemented (workflows module)       |
| Tool Registry              | Part 7      | Dynamic discovery not needed yet        |
| Human-in-the-Loop          | Part 6      | Approval workflows separate concern     |

---

## Dependencies

```toml
# pyproject.toml
[tool.poetry.dependencies]
agent-framework-core = "1.0.0rc5"  # Microsoft Agent Framework (RC)
```

Key imports:

- `from agent_framework import Agent, MCPStreamableHTTPTool, AgentSession`
- `from agent_framework import AgentMiddleware, ChatMiddleware, FunctionMiddleware, tool`
- `from agent_framework.azure import AzureOpenAIChatClient`
- `from agent_framework.openai import OpenAIChatClient` (GitHub/OpenAI/Ollama)
- `from agent_framework.types import SupportsChatGetResponse`

### Key Changes from Beta to RC5

| Area                  | Beta (`b260212`)                  | RC5 (`1.0.0rc5`)                                       |
| --------------------- | --------------------------------- | ------------------------------------------------------ |
| Agent lifecycle       | Manual MCP tool cleanup           | `Agent` is async context manager — `async with agent:` |
| Agent creation        | Returns `(mcp_tool, agent)` tuple | Returns `Agent` directly                               |
| Middleware            | Not available                     | Three-layer pipeline: Agent, Chat, Function            |
| Local tools           | Not available                     | `@tool(approval_mode="never_require")` decorator       |
| `Message` constructor | `items=[...]` parameter           | `text="..."` parameter                                 |
| MCP tool naming       | Single name per process           | `tool_name_prefix` to avoid duplicate names            |
