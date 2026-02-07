# Part 1 Implementation Notes: GraphRAG Fundamentals

## Overview

This document captures the complete implementation details for Part 1 of the MAF + GraphRAG article series. Use this as context when continuing development in future sessions.

---

## Project Goal

Build a knowledge graph from organizational documents using Microsoft GraphRAG and Azure OpenAI, demonstrating entity extraction, relationship detection, community analysis, and both local and global search capabilities.

---

## Azure Infrastructure

### Deployed Resources

| Resource | Region | Configuration |
|----------|--------|---------------|
| Azure OpenAI | **westus** | Cognitive Services account |
| GPT-4o | westus | 30,000 TPM, Standard SKU |
| text-embedding-3-small | westus | 30,000 TPM, Standard SKU |

**Endpoint:** `https://maf-graphrag-openai-5woawz.openai.azure.com/`

### Why westus Region?

- `text-embedding-3-small` is **not available** in `southcentralus`
- Multi-region strategy: Storage in southcentralus, AI in westus
- See [docs/lessons-learned.md](lessons-learned.md) for full regional availability matrix

### Infrastructure as Code

Located in `infra/` folder using Terraform:
- `main.tf` - Azure OpenAI and storage resources
- `variables.tf` - Configurable parameters
- `outputs.tf` - Connection strings and endpoints

---

## GraphRAG Version: 3.0.1

### Migration Notes (from v1.2.0)

**GraphRAG v3.0.x key changes:**

1. **Output File Names**: Simplified names (no `create_final_` prefix)
   - `entities.parquet`
   - `relationships.parquet`
   - `communities.parquet`
   - `community_reports.parquet`
   - `text_units.parquet`
   - `covariates.parquet` (optional)

2. **Column Names**: Entity column is `title`

3. **Config Format**: New YAML structure with `completion_models` and `embedding_models` sections

4. **API Changes**: `nodes` parameter removed from search APIs; `communities` passed directly

### Fixed Prompt Files

The following prompt files were modified to remove incompatible placeholders:

| File | Removed Placeholder |
|------|---------------------|
| `prompts/summarize_descriptions.txt` | `{max_length}` |
| `prompts/global_search_map_system_prompt.txt` | `{max_length}` |
| `prompts/global_search_reduce_system_prompt.txt` | `{max_length}` |
| `prompts/community_report_text.txt` | `{max_report_length}` |
| `prompts/community_report_graph.txt` | `{max_report_length}` |

---

## Vector Store: LanceDB (Local)

### Configuration

```yaml
vector_store:
  type: lancedb
  db_uri: output/lancedb
  collection_name: default
```

### Characteristics

- **File-based**: Stored locally at `output/lancedb/`
- **No cloud dependency**: No Azure AI Search, Pinecone, etc.
- **Good for**: Development, testing, small-scale deployments
- **Limitation**: Not distributed, all data on single machine

### Important: Incremental Indexing

GraphRAG v3.0.x supports update indexing via `IndexingMethod`:
- Standard: Full rebuild
- Update: Incremental update of existing index

---

## Knowledge Graph Statistics

### Indexing Results

| Metric | Value |
|--------|-------|
| Entities | 147 |
| Relationships | 263 |
| Communities | 32 |
| Documents | 10 |
| Hierarchy Levels | 2 |

### Entity Distribution

GraphRAG extracts entities with semantic types from documents:
- PERSON (e.g., Dr. Emily Harrison, David Kumar, Sophia Lee)
- ORGANIZATION (e.g., TechVenture Inc., HealthCorp)
- TECHNOLOGY (e.g., Azure OpenAI, GraphRAG, LanceDB)
- PROJECT (e.g., Project Alpha, Project Beta)
- EVENT (e.g., incidents, milestones)

### Network Analysis

The knowledge graph forms a dense network of interconnected entities:
- Cross-document relationships automatically detected
- Community detection reveals organizational clusters
- Entity centrality identifies key organizational nodes

---

## Sample Documents

Located in `input/documents/` (10 interconnected documents):

| File | Content |
|------|---------|
| `company_org.md` | TechVenture Inc. organizational structure |
| `team_members.md` | Team profiles and responsibilities |
| `project_alpha.md` | Project Alpha details, team, technologies |
| `project_beta.md` | Project Beta AI/ML platform |
| `technical_architecture.md` | Azure architecture and infrastructure |
| `technology_stack.md` | Technology choices and implementations |
| `customers_partners.md` | Customer relationships and partnerships |
| `engineering_processes.md` | Development workflows and practices |
| `incidents_postmortems.md` | Incident reports and learnings |
| `company_events_timeline.md` | Milestones and company history |

These documents are interconnected, referencing the same people, projects, and technologies to demonstrate GraphRAG's cross-document relationship detection.

---

## Key Scripts

### Python Indexing CLI

Build the knowledge graph using Python:

```bash
# CLI usage
poetry run python -m core.index
poetry run python -m core.index --resume          # Resume interrupted run
poetry run python -m core.index --memory-profile  # Enable profiling

# Programmatic usage
from core import build_index
results = await build_index()
```

### Python Query CLI

Query the knowledge graph using the `core/` module:
- Supports: `local`, `global`, `drift`, `basic` search types
- Rich CLI output with statistics
- Programmatic API for integration

```bash
# CLI usage
poetry run python -m core.example "Who leads Project Alpha?"
poetry run python -m core.example "Summarize the organization" --type global

# Python API usage
from core import load_all, local_search
data = load_all()
response, context = await local_search("Your question", data)
```

---

## Search Types Explained

### Local Search

- **Best for**: Entity-specific questions
- **How it works**: Searches entities and direct relationships
- **Examples**:
  - "Who leads Project Alpha?"
  - "What technologies does David Kumar work with?"
  - "What is Emily Harrison's role?"

### Global Search

- **Best for**: Thematic/broad questions
- **How it works**: Analyzes community reports across the organization
- **Examples**:
  - "What are the main initiatives at TechVenture?"
  - "How are departments connected?"
  - "Summarize the organizational structure"

---

## Notebook: Graph Exploration

`notebooks/01_explore_graph.ipynb` provides:

1. **Entity Analysis**: Load and explore extracted entities
2. **Relationship Analysis**: Examine connections between entities
3. **Community Analysis**: Understand hierarchical community structure
4. **Network Visualization**: Interactive graph visualization
5. **Statistics**: Degree distribution, centrality measures

### Dependencies

```python
pandas, pyarrow, networkx, matplotlib
```

---

## Configuration Files

### settings.yaml

Main GraphRAG configuration:
- LLM settings (Azure OpenAI GPT-4o)
- Embedding settings (text-embedding-3-small)
- Vector store (LanceDB)
- Entity extraction parameters
- Community detection settings

### .env

Environment variables (create from `.env.example`):
```
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
```

---

## Python API Module

The `core/` module provides a modern Python API for GraphRAG 3.0.x:
- Async search functions (local, global, drift, basic)
- Parquet data loading with `GraphData` dataclass
- CLI example with rich formatting
- Full API compatibility with GraphRAG 3.0.x

See [core/README.md](../core/README.md) for complete documentation.

---

## Documentation

| Document | Purpose |
|----------|---------|
| `docs/query-guide.md` | Query syntax and examples |
| `docs/qa-examples.md` | Real Q&A responses from GraphRAG |
| `docs/lessons-learned.md` | Azure deployment insights |
| `docs/multi-region-architecture.md` | Cross-region strategy |

---

## Issues Encountered & Solutions

### Issue 1: GraphRAG Version Conflicts

**Problem**: Multiple versions tried (v3.0.1, v2.7.1) had breaking changes.

**Solution**: Settled on v1.2.0 with prompt fixes.

### Issue 2: KeyError 'max_length'

**Problem**: Custom prompts included `{max_length}` placeholder not passed by v1.2.0.

**Solution**: Removed `{max_length}` and `{max_report_length}` from all prompt files.

### Issue 3: Windows UTF-8 Encoding

**Problem**: PowerShell encoding issues caused crashes.

**Solution**: Added to scripts:
```powershell
$OutputEncoding = [console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$env:PYTHONUTF8 = 1
```

### Issue 4: Regional Model Availability

**Problem**: `text-embedding-3-small` not available in `southcentralus`.

**Solution**: Deploy Azure OpenAI to `westus` region.

---

## Part 2 Preview: GraphRAG MCP Server

The next phase will expose GraphRAG as an MCP (Model Context Protocol) server:

- Create FastMCP server with GraphRAG tools
- Integrate with Microsoft Agent Framework via `MCPStreamableHTTPTool`
- Enable agent-to-knowledge-graph communication
- Prepare for multi-agent orchestration

### Planned Structure (New Module)

```
mcp_server/                # New folder for Part 2
├── server.py              # FastMCP server
└── tools/
    ├── local_search.py    # Local search tool
    ├── global_search.py   # Global search tool
    └── entity_query.py    # Direct entity lookup
```

---

## Quick Reference Commands

```bash
# Install dependencies
poetry install

# Build knowledge graph
poetry run python -m core.index

# Build with options
poetry run python -m core.index --resume          # Resume interrupted
poetry run python -m core.index --memory-profile  # Enable profiling

# Query using Python CLI
poetry run python -m core.example "Your question"
poetry run python -m core.example "Your question" --type global

# Query using Python API
poetry run python -c "import asyncio; from core import load_all, local_search; data = load_all(); print(asyncio.run(local_search('Your question', data))[0])"

# Run notebook
jupyter notebook notebooks/01_explore_graph.ipynb
```

---

## File Structure Summary

```
maf-graphrag-series/
├── .venv/                     # Python virtual environment (Poetry-managed)
├── .env                       # Azure credentials (gitignored)
├── .env.example               # Template for credentials
├── pyproject.toml             # Poetry dependencies
├── settings.yaml              # GraphRAG configuration
├── requirements.txt           # Legacy Python dependencies
├── input/
│   ├── README.md              # Document descriptions
│   └── documents/             # 10 source documents
├── output/                    # Generated artifacts (gitignored)
│   ├── *.parquet
│   └── lancedb/
├── prompts/                   # Custom prompt templates
├── core/                      # Python API module
│   ├── __init__.py
│   ├── config.py              # Configuration loading
│   ├── data_loader.py         # Parquet data loading
│   ├── indexer.py             # Build knowledge graph
│   ├── search.py              # Async search functions
│   ├── index.py               # Indexing CLI
│   └── example.py             # Query CLI
├── docs/                      # Documentation
├── notebooks/                 # Jupyter notebooks
└── infra/                     # Terraform infrastructure
```

---

## Author

Cristopher Coronado - Microsoft MVP AI

---

*Last updated: February 7, 2026*
