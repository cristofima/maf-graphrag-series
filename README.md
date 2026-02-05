# MAF + GraphRAG Series

Building Knowledge Graphs with Microsoft GraphRAG and Azure OpenAI.

## Series Overview

This repository contains the code for the **MAF + GraphRAG** article series, demonstrating enterprise-grade knowledge graph integration with Microsoft Agent Framework.

| Part | Title | Status | Folder/Module |
|------|-------|--------|---------------|
| 1 | GraphRAG Fundamentals | ✅ Complete | `core/`, `run_*.ps1` |
| 2 | GraphRAG MCP Server | ⏳ Planned | `mcp_server/` |
| 3 | Supervisor Agent Pattern | ⏳ Planned | `agents/`, `orchestration/` |
| 4 | Workflow Patterns | ⏳ Planned | `workflows/` |
| 5 | Agent Evaluation | ⏳ Planned | `evaluation/` |
| 6 | Human-in-the-Loop | ⏳ Planned | `middleware/` |
| 7 | Tool Registry | ⏳ Planned | `registry/` |
| 8 | Production Deployment | ⏳ Planned | `deploy/` |

## Part 1: GraphRAG Fundamentals

Learn the basics of Microsoft GraphRAG - transforming documents into knowledge graphs for complex reasoning.

### What You'll Learn

- Microsoft Research GraphRAG fundamentals
- Entity extraction from documents
- Relationship detection between entities
- Community detection (Leiden algorithm)
- Local vs Global search strategies

### Why GraphRAG (Not Standard RAG)?

| Question Type | Standard RAG | GraphRAG |
|---------------|-------------|----------|
| "Find similar documents" | ✅ | ✅ |
| "What is the relationship between X and Y?" | ❌ | ✅ |
| "What are all the connections to Project Alpha?" | ❌ | ✅ |
| "What themes span the entire organization?" | ❌ | ✅ |

### Prerequisites

- **Python 3.10+** (tested with 3.11)
- **Poetry** for dependency management
- Azure OpenAI resource with:
  - GPT-4o deployment (for entity extraction and queries)
  - text-embedding-3-small deployment (for embeddings)
- Azure subscription
- PowerShell (Windows) or Bash (Linux/Mac)

### Quick Start

```powershell
# Install Poetry (if not installed)
# Windows PowerShell:
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -

# Linux/macOS:
# curl -sSL https://install.python-poetry.org | python3 -

# Clone the repository
git clone https://github.com/cristofima/maf-graphrag-series.git
cd maf-graphrag-series

# RECOMMENDED: Configure Poetry to create .venv in project folder
poetry config virtualenvs.in-project true

# Install dependencies (Poetry creates virtual environment automatically)
poetry install

# Configure environment variables
cp .env.example .env
# Edit .env with your Azure OpenAI credentials

# Build the knowledge graph (one-time setup)
.\run_index.ps1

# Query the knowledge graph using Python
poetry run python -m core.example "Who leads Project Alpha?"
poetry run python -m core.example "What are the main projects?" --type global
```

💡 **Note:** Poetry manages virtual environments automatically. You don't need to manually create `.venv` like with pip.

📖 **Poetry Guide:** See [docs/poetry-guide.md](docs/poetry-guide.md) for detailed usage instructions.

### Using the Python API

The `core/` module provides a modern Python API for GraphRAG 1.2.0:

```python
import asyncio
from core import load_all, local_search, global_search

# Load the knowledge graph
data = load_all()
print(f"Loaded: {data.entities.shape[0]} entities, {data.relationships.shape[0]} relationships")

# Entity-focused search
response, context = asyncio.run(local_search("Who leads Project Alpha?", data))
print(response)

# Thematic search
response, context = asyncio.run(global_search("What are the main projects?", data))
print(response)
```

Or use the CLI:

```powershell
poetry run python -m core.example "Who leads Project Alpha?"
poetry run python -m core.example "What are the main themes?" --type global
```

📖 **API Documentation:** See [core/README.md](core/README.md) for full API reference.

### Project Structure

```
maf-graphrag-series/
├── README.md
├── pyproject.toml             # Poetry dependency management
├── poetry.lock                # Locked dependency versions
├── settings.yaml              # GraphRAG configuration
├── run_index.ps1              # Build knowledge graph (one-time indexing)
├── .env.example
├── input/
│   └── documents/*.md         # Sample interconnected documents
├── output/                    # Generated knowledge graph
│   ├── create_final_*.parquet
│   └── lancedb/               # Vector store
├── core/                      # Python API for GraphRAG 1.2.0
│   ├── config.py              # Configuration loading
│   ├── data_loader.py         # Parquet file loading
│   ├── search.py              # Async search functions
│   ├── example.py             # CLI example
│   └── README.md              # Module documentation
├── prompts/                   # Custom prompt templates
├── docs/
│   ├── poetry-guide.md              # Poetry usage guide
│   ├── dependency-management-analysis.md  # Why Poetry?
│   ├── query-guide.md               # Query reference
│   ├── qa-examples.md               # Q&A examples with responses
│   └── lessons-learned.md           # Deployment insights
└── notebooks/
    └── 01_explore_graph.ipynb # Graph visualization
```

## Sample Q&A Results

### Local Search (Entity-Focused)

**Question:** "Who leads Project Alpha and what is their background?"

**Answer:**
> Dr. Emily Harrison leads Project Alpha at TechVenture Inc. She holds a Ph.D. in Quantum Computing from MIT and has 15 years of experience in advanced computing research. Under her leadership, Project Alpha is developing a next-generation quantum-classical hybrid processor that has achieved 99.7% gate fidelity in initial testing.

### Global Search (Thematic)

**Question:** "What are the main initiatives at TechVenture?"

**Answer:**
> TechVenture Inc. is pursuing three major strategic initiatives:
> 1. **Project Alpha** - Quantum computing research led by Dr. Emily Harrison
> 2. **Project Beta** - AI/ML platform development focused on healthcare applications  
> 3. **Project Gamma** - Sustainable energy solutions integrating smart grid technology
>
> These projects share resources and talent, with cross-functional teams collaborating across departments.

See [docs/qa-examples.md](docs/qa-examples.md) for more examples.

## Azure AI Services Used

| Service | Purpose | Model |
|---------|---------|-------|
| **Azure OpenAI** | Entity extraction, queries | GPT-4o |
| **Azure OpenAI** | Document embeddings | text-embedding-3-small |

## Key Files

| File | Description |
|------|-------------|
| `settings.yaml` | GraphRAG configuration (LLM, embeddings, storage) |
| `run_index.ps1` | PowerShell script to build knowledge graph |
| `core/` | Python API module for querying and data access |
| `.env` | Azure OpenAI credentials (create from .env.example) |

## License

MIT License - See [LICENSE](LICENSE) for details.

## Author

Cristopher Coronado
