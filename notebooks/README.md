# Notebooks

Jupyter notebooks for exploring the knowledge graph and testing MCP tools.

## Prerequisites

1. Knowledge graph indexed: `poetry run python -m core.index`
2. Azure OpenAI configured in `.env`
3. *(Notebook 02 only, optional)* MCP server running for HTTP tests: `poetry run python run_mcp_server.py`

## Notebooks

| Notebook | Description | Makes LLM calls? |
|---|---|---|
| `01_explore_graph.ipynb` | Load parquet files, visualize entities/relationships/communities with NetworkX + matplotlib | No |
| `02_test_mcp_server.ipynb` | Test MCP tools directly (entity query, local search, global search, cross-document reasoning) | Yes |

## Logging

Notebook 02 includes a logging configuration cell that suppresses noisy `litellm` / `graphrag` INFO-level logs while preserving WARNING+ messages for traceability. Run it before executing search cells.

## Output Management

Notebook outputs are preserved in git to provide documentation value. Readers on GitHub can see executed results (graphs, search responses) without running locally.
