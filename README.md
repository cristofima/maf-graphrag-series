# MAF + GraphRAG Series

Building Knowledge Graphs with Microsoft GraphRAG and Azure OpenAI.

## Series Overview

This repository contains the code for the **MAF + GraphRAG** article series, demonstrating enterprise-grade knowledge graph integration with Microsoft Agent Framework.

| Week | Article | Status |
|------|---------|--------|
| 1 | GraphRAG Fundamentals | 🚧 In Progress |
| 2 | GraphRAG MCP Server | ⏳ Planned |
| 3 | Supervisor Agent Pattern | ⏳ Planned |
| 4 | Workflow Patterns | ⏳ Planned |
| 5 | Agent Evaluation | ⏳ Planned |
| 6 | Human-in-the-Loop | ⏳ Planned |
| 7 | Tool Registry | ⏳ Planned |
| 8 | Production Deployment | ⏳ Planned |

## Week 1: GraphRAG Fundamentals

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

- Python 3.10+
- Azure OpenAI resource with:
  - GPT-4o deployment (for entity extraction)
  - text-embedding-3-large deployment (for embeddings)
- Azure subscription

### Quick Start

```bash
# Clone the repository
git clone https://github.com/cristofima/maf-graphrag-series.git
cd maf-graphrag-series

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your Azure OpenAI credentials

# Run the indexer (Week 1)
python src/indexer.py
```

### Project Structure

```
maf-graphrag-series/
├── README.md
├── requirements.txt
├── .env.example
├── input/
│   └── documents/           # Sample interconnected documents
├── output/                  # Generated knowledge graph (parquet files)
├── src/
│   ├── indexer.py          # Build knowledge graph
│   ├── local_search.py     # Entity-focused queries
│   └── global_search.py    # Community-level queries
└── notebooks/
    └── 01_explore_graph.ipynb
```

## Azure AI Services Used

| Service | Purpose | Model |
|---------|---------|-------|
| **Azure OpenAI** | Entity extraction, relationship detection | GPT-4o |
| **Azure OpenAI** | Document embeddings | text-embedding-3-large |

## License

MIT License - See [LICENSE](LICENSE) for details.

## Author

Cristopher Coronado - Microsoft MVP AI
