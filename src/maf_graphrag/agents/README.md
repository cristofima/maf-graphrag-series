# Agents Module

Session store, router classifier, observability middleware, and agent factories for the MAF + GraphRAG router-first architecture.

## Overview

The module provides three distinct capabilities that support the `RouterWorkflow` production entry point:

1. **Session store** — process-local `InMemorySessionStore` for multi-turn conversational state, TTL expiration, bounded capacity, and checkpoint/resume tracking.
2. **Router classifier** — Foundry-backed `RouterClassifier` used by `RouterWorkflow` to classify queries and select the appropriate sub-workflow.
3. **Agent factories** — `create_client` and `create_mcp_tool` for wiring workflows to Azure OpenAI and the GraphRAG MCP server.

## Module Structure

```
agents/
├── __init__.py          # Public API exports
├── config.py            # AgentConfig + SessionConfig (validated from env)
├── middleware.py        # Four-layer observability middleware pipeline
├── router_classifier.py # RouterClassifier used by RouterWorkflow
├── session_store.py     # InMemorySessionStore with TTL, LRU, checkpoint tracking
├── factories.py         # create_client, create_mcp_tool
├── tools.py             # Local @tool functions (format_as_table, extract_key_entities)
└── README.md            # This file
```

## Session Store

`InMemorySessionStore` extends `agent_framework.SessionStore` with production-ready TTL expiration, bounded LRU capacity, opportunistic cleanup, and process-local checkpoint/resume tracking for multi-turn conversations.

### Key types

| Type                              | Purpose                                                                          |
| --------------------------------- | -------------------------------------------------------------------------------- |
| `SessionKey`                      | Normalized channel + conversation + user → deterministic SHA256 `session_id`     |
| `SessionRecord`                   | Mutable session state: history groups, turn index, per-session lock, diagnostics |
| `ActiveWorkflowRun`               | Process-local checkpoint correlation for interrupted workflow runs               |
| `InMemorySessionStore`            | TTL + LRU eviction + cleanup + metrics; subclasses native `SessionStore`         |
| `SessionCompactionDiagnostics`    | Structured output from history sliding-window compaction                         |
| `SessionStoreMetrics`             | Counters: `active_sessions`, `evictions`, `ttl_expirations`, `cleanup_runs`      |
| `ensure_mcp_client_compatibility` | Patches Agent Framework ↔ MCP field naming gaps before establishing sessions     |

```python
from agents.session_store import InMemorySessionStore, SessionKey

store = InMemorySessionStore(
    ttl_seconds=1800,
    max_count=1000,
    cleanup_interval_seconds=60,
    max_history_groups=12,
)

key = SessionKey.create(channel_id="msteams", conversation_id="conv-1", user_id="user-1")
record, created = await store.get_or_create(key.session_id)

# Append a completed turn (updates history and triggers compaction if needed)
diagnostics = store.append_turn(record, user_text="Hello", assistant_text="Hi!")
```

### Checkpoint/resume tracking

`SessionRecord.active_workflow_run` holds an optional `ActiveWorkflowRun` that correlates the session with a native framework checkpoint after a workflow timeout or interruption:

```python
from agents.session_store import ActiveWorkflowRun

# Set by RouterChatService._save_checkpoint_after_interruption() on timeout
record.active_workflow_run = ActiveWorkflowRun(
    workflow_run_id="run-uuid",
    checkpoint_id="framework-checkpoint-uuid",
    workflow_type="sequential",   # used to validate compatibility on resume
)
```

On the next request, `RouterChatService._resolve_resume_checkpoint()` validates the checkpoint (exists + correct workflow type) and passes `checkpoint_id` to `Workflow.run()`.

### Configuration

Session defaults are sourced from environment variables via `SessionConfig`:

| Variable                           | Default | Description                   |
| ---------------------------------- | ------- | ----------------------------- |
| `SESSION_TTL_SECONDS`              | 1800    | Session expiration time       |
| `SESSION_MAX_COUNT`                | 1000    | Maximum active sessions       |
| `SESSION_CLEANUP_INTERVAL_SECONDS` | 60      | Cleanup cadence               |
| `SESSION_MAX_HISTORY_GROUPS`       | 12      | Sliding window turns retained |

## Router Classifier

`RouterClassifier` is called by `RouterWorkflow` to classify a query and select a sub-workflow. It uses an `OpenAIChatCompletionClient` pointed at the Foundry model-router deployment.

```python
from agents.router_classifier import RouterClassifier
from agents.config import AgentConfig

config = AgentConfig.from_env()
classifier = RouterClassifier(config)
classification = await classifier.classify("Who leads Project Alpha?")
# classification.workflow_label → "sequential" | "concurrent" | "handoff" | "out_of_context"
# classification.confidence_score → 0-100
```

Configuration variables:

| Variable                         | Description                                     |
| -------------------------------- | ----------------------------------------------- |
| `AZURE_OPENAI_ROUTER_DEPLOYMENT` | Foundry model-router deployment name            |
| `AZURE_OPENAI_ROUTER_ENDPOINT`   | Optional separate endpoint for the router model |
| `AZURE_OPENAI_ROUTER_SUBSET`     | Optional comma-separated subset label           |

## Agent Factories

A focused set of factory helpers create Azure OpenAI chat clients and MCP tools that align with the router workflow defaults:

```python
from agents.factories import create_client, create_mcp_tool

# Foundry OpenAI chat client scoped to RouterWorkflow defaults
client = create_client()

# MCPStreamableHTTPTool connected to the GraphRAG MCP server
mcp_tool = create_mcp_tool(mcp_url="http://localhost:8011/mcp")
```

### MCP Compatibility Shim

FastMCP 4.x replaced several camelCase handshake fields (for example `protocolVersion`, `inputSchema`, `nextCursor`) with snake_case names. Microsoft Agent Framework 1.17 still accesses the legacy names. `create_mcp_tool()` calls `ensure_mcp_client_compatibility()` before instantiating `MCPStreamableHTTPTool`; the helper adds read/write aliases so RouterWorkflow, DevUI, and Teams-based agents remain functional without downgrading dependencies.

## Observability Middleware

A four-layer middleware pipeline for agent observability and context management:

| Layer    | Class                          | Purpose                                |
| -------- | ------------------------------ | -------------------------------------- |
| Agent    | `TimingAgentMiddleware`        | Measures total agent execution time    |
| Chat     | `QueryRewritingChatMiddleware` | Rewrites vague queries before LLM call |
| Chat     | `TokenCountingChatMiddleware`  | Tracks prompt/completion token usage   |
| Function | `LoggingFunctionMiddleware`    | Logs MCP tool calls with arguments     |

```python
from agents.middleware import (
    TimingAgentMiddleware,
    QueryRewritingChatMiddleware,
    TokenCountingChatMiddleware,
    LoggingFunctionMiddleware,
)
```

## Configuration

`AgentConfig` validates all Azure OpenAI settings from environment variables:

```python
from agents.config import AgentConfig, get_agent_config

config = AgentConfig.from_env()   # or get_agent_config() for a cached singleton
client = create_client(config)
```

Required environment variables:

| Variable                         | Description                                                            |
| -------------------------------- | ---------------------------------------------------------------------- |
| `AZURE_OPENAI_ENDPOINT`          | Azure OpenAI service base URL                                          |
| `AZURE_OPENAI_API_KEY`           | API key (or use `AZURE_CLIENT_ID`/`AZURE_TENANT_ID` for Entra ID auth) |
| `AZURE_OPENAI_CHAT_DEPLOYMENT`   | Default chat deployment (e.g. `gpt-4o`)                                |
| `AZURE_OPENAI_ROUTER_DEPLOYMENT` | Router deployment for the classifier                                   |

## Local Tool Functions

Lightweight `@tool`-decorated functions that run in-process (no MCP round-trip):

| Tool                   | Purpose                                      |
| ---------------------- | -------------------------------------------- |
| `format_as_table`      | Formats a list of dicts as a Markdown table  |
| `extract_key_entities` | Extracts entity names from unstructured text |

## Router Workflow Integration

`RouterWorkflow` composes this module end to end:

- During initialization it resolves `AgentConfig`, builds a shared `OpenAIChatCompletionClient` via `create_client()`, and wires the classifier to the Foundry model-router deployment.
- On each turn the workflow opens an `MCPStreamableHTTPTool` with `create_mcp_tool()` so tool calls use the Streamable HTTP transport and compatibility shim.
- Session-scoped state is fetched through `InMemorySessionStore.get_or_create()`, enabling checkpoint resume and deterministic locking when multiple requests target the same session.
- Middleware from `agents.middleware` wraps every agent call, ensuring router telemetry flows into distributed tracing and structured logs.

## MCP Transport Protocol

This module uses the **Streamable HTTP** transport (`/mcp` endpoint) as the agent-facing MCP transport:

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

## Router Metadata Hand-off

`AgentConfig` captures Foundry router metadata (mode, subset) so downstream workflows can log or audit how production traffic is partitioned. The metadata returned by `create_client()` travels with each router invocation and is recorded in `WorkflowResult` metadata for observability.

## Architecture Benefits

- **Foundry-aligned configuration** — Environment parsing enforces Azure OpenAI and Foundry router requirements.
- **Centralized factories** — `create_client()` and `create_mcp_tool()` consistently apply compatibility shims and endpoint normalization.
- **Session durability** — `InMemorySessionStore` handles TTL eviction, checkpoint tracking, and concurrency guards.
- **Deterministic routing** — `RouterClassifier` enforces the 80-point confidence contract and structured fallbacks.
- **Layered observability** — Middleware emits timing, rewriting, token, and function-call diagnostics across all workflows.
- **Local + remote tools** — The tools module exposes lightweight helpers that complement the GraphRAG MCP toolset without extra round-trips.

## References

- [Microsoft Agent Framework Documentation](https://learn.microsoft.com/agent-framework/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [GraphRAG Documentation](https://microsoft.github.io/graphrag/)
