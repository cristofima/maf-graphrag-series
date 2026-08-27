# Core Module

Python API for GraphRAG knowledge graph operations.

## Quick Start

### Building the Knowledge Graph

```powershell
# CLI (recommended)
uv run python -m core.index

# With options
uv run python -m core.index --resume          # Resume interrupted run
uv run python -m core.index --memory-profile  # Enable profiling
```

Or programmatically:

```python
import asyncio
from core import build_index

# Build the knowledge graph
results = asyncio.run(build_index())
for result in results:
    print(f"{result.workflow}: {result.errors or 'success'}")

# Non-async callers can use the synchronous helper
from core import build_index_sync

results_sync = build_index_sync()
for result in results_sync:
  print(f"{result.workflow}: {result.errors or 'success'}")
```

### Querying the Knowledge Graph

```python
import asyncio
from core import load_all, local_search, global_search

# Load the knowledge graph data
data = load_all()
print(f"Loaded: {data.entities.shape[0]} entities, {data.relationships.shape[0]} relationships")

# Entity-focused search
response, context = asyncio.run(local_search("Who leads Project Alpha?", data))
print(response)

# Thematic search across communities
response, context = asyncio.run(global_search("What are the main projects?", data))
print(response)
```

## CLI Commands

```powershell
# Build knowledge graph (run from project root)
uv run python -m core.index

# Query the knowledge graph
uv run python -m core.example "Who leads Project Alpha?"
uv run python -m core.example "What are the main projects?" --type global
```

## Module Structure

| File                      | Purpose                                                               |
| ------------------------- | --------------------------------------------------------------------- |
| `__init__.py`             | Module exports                                                        |
| `classification_utils.py` | Shared parsing utilities (for example confidence score normalization) |
| `config.py`               | Load GraphRagConfig, validate output files                            |
| `data_loader.py`          | Load Parquet files into GraphData dataclass                           |
| `indexer.py`              | Build knowledge graph from documents                                  |
| `search.py`               | Async search functions (local, global, drift, basic)                  |
| `index.py`                | CLI for indexing                                                      |
| `example.py`              | CLI for querying                                                      |
| `logging_config.py`       | Shared logging defaults for CLI and runtime entry points              |
| `observability.py`        | Azure Monitor wiring helpers for Agent Framework instrumentation      |

## API Reference

### Data Loading

```python
from core import load_all, get_config, GraphData

# Load all graph data at once
data: GraphData = load_all()

# Access individual DataFrames
data.entities           # All extracted entities
data.relationships      # Entity relationships
data.communities        # Community assignments
data.community_reports  # Generated community summaries
data.text_units         # Original text chunks
data.documents          # Source document metadata (optional)
data.covariates         # Optional claims/covariates
```

### Search Functions

All search functions are async and return `(response: str, context: dict)`.

```python
from core import local_search, global_search

# Local search - entity-focused, good for specific questions
response, context = await local_search(
    query="Who works on Project Alpha?",
    data=data,
    community_level=2,  # Higher = smaller communities
    response_type="Multiple Paragraphs"
)

# Global search - thematic, good for broad questions
response, context = await global_search(
    query="Summarize the organization",
    data=data,
    community_level=2,
    response_type="Multiple Paragraphs",
    dynamic_community_selection=False
)
```

### Advanced Search

```python
from core.search import drift_search, basic_search

# DRIFT search - combines local and global strategies
response, context = await drift_search(query, data)

# Basic RAG - vector similarity only (no graph structure)
response, context = await basic_search(query, data)
```

### Shared Utilities

```python
from core.classification_utils import normalize_confidence_score

normalize_confidence_score(92)       # 92
normalize_confidence_score("high")   # 90
normalize_confidence_score("invalid")  # None
```

`normalize_confidence_score` centralizes confidence parsing to keep routing logic consistent across agents and workflows.

## GraphData Fields

| Field               | Type              | Description                                           |
| ------------------- | ----------------- | ----------------------------------------------------- |
| `entities`          | DataFrame         | Extracted entities with name, type, description       |
| `relationships`     | DataFrame         | Entity relationships with source, target, description |
| `communities`       | DataFrame         | Leiden community assignments                          |
| `community_reports` | DataFrame         | Generated summaries per community                     |
| `text_units`        | DataFrame         | Original document chunks                              |
| `documents`         | DataFrame \| None | Source document metadata (title, text)                |
| `covariates`        | DataFrame \| None | Optional claims/covariates                            |

## Configuration

The module uses `settings.yaml` in the project root. Key settings:

```yaml
completion_models:
  default_completion_model:
    model_provider: azure
    model: gpt-4o
    azure_deployment_name: ${AZURE_OPENAI_CHAT_DEPLOYMENT}

embedding_models:
  default_embedding_model:
    model_provider: azure
    model: text-embedding-3-small
    azure_deployment_name: ${AZURE_OPENAI_EMBEDDING_DEPLOYMENT}

output_storage:
  type: file
  base_dir: "output"
```

## File Locations

GraphRAG outputs files without prefix:

```
output/
├── entities.parquet
├── relationships.parquet
├── communities.parquet
├── community_reports.parquet
├── text_units.parquet
├── covariates.parquet  (optional)
└── lancedb/
    └── default.lance/
```

## Requirements

- Python >=3.11,<3.13
- GraphRAG configured through `pyproject.toml`
- Data and CLI dependencies installed through `uv sync --dev`
- Azure OpenAI credentials in `.env`
