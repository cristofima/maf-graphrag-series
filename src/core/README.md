# Core Module

Python API for GraphRAG 3.0.x knowledge graph operations.

## Quick Start

### Building the Knowledge Graph

```powershell
# CLI (recommended)
poetry run python -m core.index

# With options
poetry run python -m core.index --resume          # Resume interrupted run
poetry run python -m core.index --memory-profile  # Enable profiling
```

Or programmatically:

```python
import asyncio
from core import build_index

# Build the knowledge graph
results = asyncio.run(build_index())
for result in results:
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
poetry run python -m core.index

# Query the knowledge graph
poetry run python -m core.example "Who leads Project Alpha?"
poetry run python -m core.example "What are the main projects?" --type global
```

## Module Structure

| File | Purpose |
|------|---------|
| `__init__.py` | Module exports |
| `config.py` | Load GraphRagConfig, validate output files |
| `data_loader.py` | Load Parquet files into GraphData dataclass |
| `indexer.py` | Build knowledge graph from documents |
| `search.py` | Async search functions (local, global, drift, basic) |
| `index.py` | CLI for indexing |
| `example.py` | CLI for querying |

## API Reference

### Data Loading

```python
from core import load_all, get_config, GraphData

# Load all graph data at once
data: GraphData = load_all()

# Access individual DataFrames
data.entities        # All extracted entities
data.relationships   # Entity relationships
data.nodes           # Graph nodes
data.communities     # Community assignments
data.community_reports  # Generated community summaries
data.text_units      # Original text chunks
data.covariates      # Optional claims/covariates
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

## GraphData Fields

| Field | Type | Description |
|-------|------|-------------|
| `entities` | DataFrame | Extracted entities with name, type, description |
| `relationships` | DataFrame | Entity relationships with source, target, description |
| `nodes` | DataFrame | Graph nodes for search algorithms |
| `communities` | DataFrame | Leiden community assignments |
| `community_reports` | DataFrame | Generated summaries per community |
| `text_units` | DataFrame | Original document chunks |
| `covariates` | DataFrame | Optional claims (may be None) |

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

GraphRAG 3.0.x outputs files without prefix:

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
- GraphRAG ~3.0.1
- pandas ^2.3.0, pyarrow ^22.0.0
- rich ^13.0.0
- Azure OpenAI credentials in `.env`
