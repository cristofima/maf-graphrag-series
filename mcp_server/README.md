# GraphRAG MCP Server - Part 2

Exposes GraphRAG functionality as MCP (Model Context Protocol) tools for Microsoft Agent Framework integration.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    Microsoft Agent Framework                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ChatAgent with MCPStreamableHTTPTool                     │  │
│  │ - Sends queries to MCP server                            │  │
│  │ - Receives structured responses                          │  │
│  └──────────────────┬───────────────────────────────────────┘  │
└─────────────────────┼──────────────────────────────────────────┘
                      │ HTTP/SSE
                      ▼
┌────────────────────────────────────────────────────────────────┐
│              GraphRAG MCP Server (FastMCP)                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ MCP Tools:                                               │  │
│  │ - search_knowledge_graph(query, type)                    │  │
│  │ - local_search(query)                                    │  │
│  │ - global_search(query)                                   │  │
│  │ - list_entities(type, limit)                             │  │
│  │ - get_entity(name)                                       │  │
│  └──────────────────┬───────────────────────────────────────┘  │
└─────────────────────┼──────────────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────────────┐
│           GraphRAG Knowledge Graph (core/)                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ - 147 entities                                           │  │
│  │ - 263 relationships                                      │  │
│  │ - 32 communities                                         │  │
│  │ - 10 documents                                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Start MCP Server

```bash
# Using Python module
poetry run python -m mcp_server.server

# Or using convenience script
poetry run python run_mcp_server.py
```

Server will start at: `http://localhost:8011`

### 2. Test Tools

```bash
# Option A: Test in notebook (recommended, no server needed)
jupyter notebook notebooks/02_test_mcp_server.ipynb

# Option B: Use MCP Inspector (interactive testing via server)
poetry run python run_mcp_server.py  # Start server first
npx @modelcontextprotocol/inspector
# In the UI: Transport = SSE, URL = http://localhost:8011/sse
```

## MCP Tools

### search_knowledge_graph

Main entry point for queries. Routes to local or global search.

```python
{
    "query": "Who leads Project Alpha?",
    "search_type": "local",  # "local" or "global"
    "community_level": 2,
    "response_type": "Multiple Paragraphs"
}
```

### local_search

Entity-focused search for specific questions.

**Best for:**
- "Who leads Project Alpha?"
- "What technologies are used in X?"
- "Who resolved the incident?"

```python
{
    "query": "Who leads Project Alpha?",
    "community_level": 2,
    "response_type": "Multiple Paragraphs"
}
```

### global_search

Thematic search across the organization.

**Best for:**
- "What are the main projects?"
- "Summarize the organizational structure"
- "What Azure services are used?"

```python
{
    "query": "What are the main projects?",
    "community_level": 2,
    "response_type": "Multiple Paragraphs"
}
```

### list_entities

List entities from the knowledge graph.

```python
{
    "entity_type": "project",  # Optional: filter by type
    "limit": 10
}
```

### get_entity

Get details about a specific entity.

```python
{
    "entity_name": "Dr. Emily Harrison"
}
```

## Testing with MCP Inspector

The [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) is an interactive browser tool for testing MCP servers.

### Setup

```bash
# Terminal 1: Start MCP Server
poetry run python run_mcp_server.py

# Terminal 2: Launch Inspector
npx @modelcontextprotocol/inspector
```

### Usage

1. Open the Inspector at `http://localhost:6274`
2. Set **Transport** to `SSE` and **URL** to `http://localhost:8011/sse`
3. Click **Connect**
4. Navigate to the **Tools** tab to see all 5 tools with schemas
5. Select a tool, fill parameters, and click **Run**

### Development Workflow

1. Make changes to tools in `mcp_server/tools/`
2. Restart the MCP server
3. Reconnect Inspector and test affected tools
4. Check the **Notifications** pane for server logs

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_HOST` | Server host | `127.0.0.1` |
| `MCP_PORT` | Server port | `8011` |
| `GRAPHRAG_ROOT` | GraphRAG root directory | `.` |

## Module Structure

```
mcp_server/
├── __init__.py           # Package exports
├── config.py             # Configuration management
├── server.py             # FastMCP server implementation
└── tools/
    ├── __init__.py       # Tool exports
    ├── local_search.py   # Entity-focused search
    ├── global_search.py  # Thematic search
    └── entity_query.py   # Direct entity lookup
```

## Development

### Running Tests

```bash
poetry run pytest tests/test_mcp/
```

### Adding New Tools

1. Create tool function in `mcp_server/tools/`
2. Decorate with `@mcp.tool()` in `server.py`
3. Update documentation

### Deployment

```bash
# Production with Gunicorn
poetry run gunicorn mcp_server.server:app -w 4 -k uvicorn.workers.UvicornWorker

# Docker
docker build -t graphrag-mcp .
docker run -p 8011:8011 graphrag-mcp
```

## Next: Part 3 - Supervisor Agent Pattern

In Part 3, we'll integrate Microsoft Agent Framework to create a supervisor agent that orchestrates multiple MCP tools, building on this MCP server as the foundation.

## References

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector)
- [Microsoft GraphRAG](https://github.com/microsoft/graphrag)
