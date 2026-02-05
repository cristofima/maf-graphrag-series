# Core Module

Python API for GraphRAG 1.2.0 knowledge graph operations.

## Quick Start

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

## CLI Example

```powershell
# Run from project root
poetry run python -m core.example "Who leads Project Alpha?"
poetry run python -m core.example "What are the main projects?" --method global
```

## Module Structure

| File | Purpose |
|------|---------|
| `__init__.py` | Module exports |
| `config.py` | Load GraphRagConfig, validate output files |
| `data_loader.py` | Load Parquet files into GraphData dataclass |
| `search.py` | Async search functions (local, global, drift, basic) |
| `example.py` | CLI example with rich formatting |

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
output:
  type: file
  base_dir: output

llm:
  type: azure_openai_chat
  model: gpt-4o
  
embeddings:
  llm:
    type: azure_openai_embedding
    model: text-embedding-3-small
```

## File Locations

GraphRAG 1.2.0 outputs files with `create_final_` prefix:

```
output/
├── create_final_entities.parquet
├── create_final_relationships.parquet
├── create_final_nodes.parquet
├── create_final_communities.parquet
├── create_final_community_reports.parquet
├── create_final_text_units.parquet
├── create_final_covariates.parquet  (optional)
└── lancedb/
    └── default.lance/
```

## Requirements

- Python >=3.10,<3.13
- GraphRAG 1.2.0
- pandas, pyarrow
- Azure OpenAI credentials in `.env`
