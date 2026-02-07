# Part 2 Implementation Notes: GraphRAG MCP Server

## Overview

Part 2 extends Part 1 by exposing GraphRAG as a **Model Context Protocol (MCP) server** using FastMCP, enabling any MCP-compatible client (Inspector, agents, notebooks) to query the knowledge graph through standardized tool calls over HTTP/SSE.

---

## Goals & Status

1. ✅ **Poetry Setup** — Professional dependency management
2. ✅ **Create MCP Server** — 5 GraphRAG tools exposed via FastMCP over SSE
3. ✅ **Testing via MCP Inspector** — All tools verified with MCP Inspector v0.19.0
4. ✅ **Notebook Testing** — `02_test_mcp_server.ipynb` validates all tools programmatically

> **Note:** Agent Framework integration (ChatAgent, MCPStreamableHTTPTool) is deferred to Part 3.

---

## Architecture (Implemented)

```
┌──────────────────────────────────────────────────────────────────┐
│              MCP Clients (Inspector, Notebook, etc.)             │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ MCP Inspector / Notebook / Future AI Agents              │    │
│  │ - Discovers tools automatically via SSE                  │    │
│  │ - Sends queries, receives structured responses           │    │
│  └──────────────────┬───────────────────────────────────────┘    │
└─────────────────────┤────────────────────────────────────────────┘
                      │ HTTP/SSE (port 8011)
                      ▼
┌──────────────────────────────────────────────────────────────────┐
│              GraphRAG MCP Server (FastMCP 0.2.0)                │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ MCP Tools:                                               │    │
│  │ - search_knowledge_graph(query, type)                    │    │
│  │ - local_search(query)                                    │    │
│  │ - global_search(query)                                   │    │
│  │ - list_entities(type, limit)                             │    │
│  │ - get_entity(name)                                       │    │
│  └──────────────────┬───────────────────────────────────────┘    │
└─────────────────────┤────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────────────────────┐
│           GraphRAG Knowledge Graph (core/)                       │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ - 147 entities, 263 relationships, 32 communities        │    │
│  │ - Parquet files + LanceDB vector store                   │    │
│  │ - Azure OpenAI (GPT-4o + text-embedding-3-small)         │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Module Structure (Implemented)

```
mcp_server/
├── __init__.py           # Package init
├── config.py             # Server configuration (host, port, CORS)
├── server.py             # FastMCP server with 5 tools + CORS middleware
├── README.md             # MCP Server documentation
└── tools/
    ├── __init__.py
    ├── search.py          # search_knowledge_graph (local/global dispatch)
    ├── local_search.py    # local_search (entity-focused queries)
    ├── global_search.py   # global_search (thematic queries)
    └── entity_query.py    # list_entities + get_entity
```

---

## Key Dependencies (Part 2)

```toml
# In pyproject.toml
fastmcp = "0.2.0"      # MCP server framework (pinned — see compatibility notes)
uvicorn = ">=0.27.0"    # ASGI server
graphrag = "~3.0.1"     # Microsoft GraphRAG
```

> **FastMCP 0.2.0** is pinned due to compatibility constraints. See `docs/graphrag-fastmcp-compatibility.md`.

---

## Running the MCP Server

```bash
# Start server
poetry run python run_mcp_server.py

# Server runs on http://localhost:8011
# SSE endpoint: http://localhost:8011/sse
# Messages endpoint: http://localhost:8011/messages/
```

### Testing with MCP Inspector

1. Install: `npx @modelcontextprotocol/inspector`
2. Configuration:
   - Transport Type: **SSE**
   - URL: `http://localhost:8011/sse`
3. Click **Connect** → All 5 tools appear automatically

### Testing with Notebook

Run `notebooks/02_test_mcp_server.ipynb` — validates all tools programmatically with real queries.

---

## Technical Decisions

### FastMCP SSE App Pattern

```python
# server.py — key pattern
mcp = FastMCP(name="graphrag-mcp-server")  # No 'version' param in 0.2.0
app = mcp.sse_app()  # Must call as method — returns Starlette app
app.add_middleware(CORSMiddleware, ...)  # Required for MCP Inspector
```

### Data Loading Per-Request

Each tool call loads data via `core.load_all()`. This ensures data freshness without caching stale state. For production, consider caching with TTL.

### CORS Middleware

Required for MCP Inspector (browser-based). Allows `*` origins in dev. The middleware is added to the Starlette app returned by `mcp.sse_app()`.

---

## Lessons Learned

1. **FastMCP version matters** — v0.2.0 `FastMCP()` does NOT accept `version` parameter (later versions do)
2. **`sse_app()` is a method call** — `mcp.sse_app` (without parens) returns a bound method, not an app
3. **CORS is required for Inspector** — MCP Inspector runs in browser; without CORS middleware, OPTIONS requests fail
4. **GraphRAG v3.x API** — No `nodes` parameter; pass `communities` directly to search functions
5. **Azure rate limits** — Global search triggers many LLM calls; expect 60-120s response times with retries

---

## What's Next: Part 3

Part 3 will add Microsoft Agent Framework integration:
- `ChatAgent` with `MCPStreamableHTTPTool` pointing to this MCP server
- Supervisor agent pattern orchestrating multiple tools
- The MCP server from Part 2 serves as the foundation

---

**Status:** ✅ Complete  
**Author:** Cristopher Coronado — Microsoft MVP AI  
**Date:** February 2025
