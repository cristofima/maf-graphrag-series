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

## GraphRAG Version: 1.2.0

### Critical Compatibility Notes

**GraphRAG v1.2.0 has specific requirements:**

1. **Output File Names**: Uses `create_final_*.parquet` prefix
   - `create_final_entities.parquet` (not `entities.parquet`)
   - `create_final_relationships.parquet`
   - `create_final_communities.parquet`
   - `create_final_community_reports.parquet`
   - `create_final_text_units.parquet`
   - `create_final_documents.parquet`
   - `create_final_nodes.parquet`

2. **Column Names**: Entity column is `title` (not `name`)

3. **Prompt Template Bug Fix**: Custom prompts must NOT include:
   - `{max_length}` placeholder
   - `{max_report_length}` placeholder
   
   The v1.2.0 code does not pass these parameters, causing `KeyError: 'max_length'`.

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

### Important: No Incremental Indexing

GraphRAG v1.2.0 does **NOT** support incremental indexing:
- Adding new documents requires **full reindexing**
- All parquet files are regenerated
- All embeddings are recreated
- Cost scales with **total** document count, not just new documents

---

## Knowledge Graph Statistics

### Indexing Results

| Metric | Value |
|--------|-------|
| Entities | 40 |
| Relationships | 132 |
| Communities | 8 |
| Text Units | 7 |
| Documents | 3 |
| Hierarchy Levels | 2 |

### Entity Distribution

| Type | Count |
|------|-------|
| PERSON | 18 |
| ORGANIZATION | 11 |
| DOCUMENT | 5 |
| EVENT | 3 |
| OTHER | 3 |

### Network Analysis

- Network density: 0.0577
- Top connected entity: David Kumar (centrality: 0.256)

---

## Sample Documents

Located in `input/documents/`:

| File | Content |
|------|---------|
| `company_org.md` | TechVenture Inc. organizational structure |
| `project_alpha.md` | Project Alpha details, team, technologies |
| `team_members.md` | Team profiles and responsibilities |

These documents are interconnected, referencing the same people, projects, and technologies to demonstrate GraphRAG's relationship detection.

---

## Key Scripts

### run_index.ps1

Builds the knowledge graph:
- Loads `.env` variables
- Sets UTF-8 encoding (Windows fix)
- Runs `graphrag index` CLI

```powershell
.\run_index.ps1
```

### run_query.ps1

Queries the knowledge graph:
- Supports: `local`, `global`, `drift`, `basic` methods
- Uses community level 2

```powershell
.\run_query.ps1 "Who leads Project Alpha?" -Method local
.\run_query.ps1 "Summarize the organization" -Method global
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

## Legacy src/ Scripts

The Python scripts in `src/` are **reference only**:
- Use old GraphRAG API patterns
- Reference old file names (`entities.parquet` instead of `create_final_entities.parquet`)
- Superseded by `run_index.ps1` and `run_query.ps1`

See [src/README.md](../src/README.md) for details.

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

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate

# Build knowledge graph (full reindex)
.\run_index.ps1

# Local search (entity-focused)
.\run_query.ps1 "Your question" -Method local

# Global search (thematic)
.\run_query.ps1 "Your question" -Method global

# Run notebook
jupyter notebook notebooks/01_explore_graph.ipynb
```

---

## File Structure Summary

```
maf-graphrag-series/
├── .venv/                     # Python virtual environment
├── .env                       # Azure credentials (gitignored)
├── .env.example               # Template for credentials
├── settings.yaml              # GraphRAG configuration
├── run_index.ps1              # Build knowledge graph
├── run_query.ps1              # Query knowledge graph
├── requirements.txt           # Python dependencies
├── input/documents/           # Source documents
├── output/                    # Generated artifacts (gitignored)
│   ├── create_final_*.parquet
│   └── lancedb/
├── prompts/                   # Custom prompt templates (fixed for v1.2.0)
├── docs/                      # Documentation
├── notebooks/                 # Jupyter notebooks
├── src/                       # Legacy scripts (reference only)
└── infra/                     # Terraform infrastructure
```

---

## Author

Cristopher Coronado - Microsoft MVP AI

---

*Last updated: January 31, 2026*
