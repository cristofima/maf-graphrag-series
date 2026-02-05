# GraphRAG Query Guide

This guide shows how to query the TechVenture Inc. knowledge graph built with GraphRAG.

## Quick Start

Use the Python API to run queries:

```powershell
# Local Search - Specific entity-focused questions
poetry run python -m core.example "Who leads Project Alpha?"

# Global Search - Broad organizational questions  
poetry run python -m core.example "What are the main projects at TechVenture Inc?" --type global
```

Or use it programmatically:

```python
import asyncio
from core import load_all, local_search, global_search

data = load_all()

# Local search
response, context = asyncio.run(local_search("Who leads Project Alpha?", data))
print(response)

# Global search
response, context = asyncio.run(global_search("What are the main projects?", data))
print(response)
```

## Search Methods Comparison

### Local Search
**Best for:** Specific questions about entities and their direct relationships

**Examples:**
- "Who leads Project Alpha?"
- "What technologies are used in Project Alpha?"
- "What is Sarah Chen's role?"
- "Who works with Dr. Emily Harrison?"

**How it works:** Uses vector similarity to find relevant entities, then traverses the knowledge graph to gather connected information (relationships, attributes, community context).

### Global Search
**Best for:** Broad, thematic questions requiring understanding of the entire organization

**Examples:**
- "What are the main projects and teams at TechVenture Inc?"
- "Summarize the organizational structure"
- "What are the key initiatives across all departments?"
- "What technologies are being used company-wide?"

**How it works:** Analyzes community reports (summaries of graph communities) to provide high-level overviews and thematic insights.

## Sample Queries from Our Knowledge Graph

### Local Search Queries

```powershell
# Leadership
poetry run python -m core.example "Who leads Project Alpha?"

# Technology Stack
poetry run python -m core.example "What technologies are used in Project Alpha?"

# Team Members
poetry run python -m core.example "Who works on the Infrastructure Department?"

# Relationships
poetry run python -m core.example "What is the relationship between David Kumar and Emily Harrison?"

# Roles
poetry run python -m core.example "What does Jennifer Park do?"
```

### Global Search Queries

```powershell
# Organizational Overview
poetry run python -m core.example "What are the main projects and teams at TechVenture Inc?" --type global

# Strategic Initiatives  
poetry run python -m core.example "What are the key strategic initiatives?" --type global

# Technology Landscape
poetry run python -m core.example "What technologies are being used across the organization?" --type global

# Departmental Structure
poetry run python -m core.example "Describe the organizational structure and key departments" --type global
```

## Advanced Usage

### Python API

For more control, use the Python API directly:

```python
import asyncio
from core import load_all, local_search, global_search

# Load data once
data = load_all()

# Run multiple queries
async def run_queries():
    # Local search with custom parameters
    response, context = await local_search(
        query="Who leads Project Alpha?",
        data=data,
        community_level=2,
        response_type="Multiple Paragraphs"
    )
    print("Local:", response)
    
    # Global search with dynamic community selection
    response, context = await global_search(
        query="What are the main projects?",
        data=data,
        community_level=2,
        response_type="Multi-Page Report",
        dynamic_community_selection=True
    )
    print("Global:", response)

asyncio.run(run_queries())
```

**Parameters:**
- `query`: Your question (string)
- `data`: GraphData object from `load_all()`
- `community_level`: Community hierarchy level (0-2, higher = smaller communities)
- `response_type`: Format of response (e.g., "Multiple Paragraphs", "Single Paragraph", "List of 3-7 Points", "Multi-Page Report")
- `dynamic_community_selection`: (global only) Enable dynamic community selection

### Available Search Types

```python
from core.search import local_search, global_search, drift_search, basic_search

# Standard searches
await local_search(query, data)        # Entity-focused
await global_search(query, data)       # Thematic/community-based

# Advanced searches
await drift_search(query, data)        # Hybrid local+global
await basic_search(query, data)        # Vector similarity only (no graph)
```

## Understanding the Output

### Local Search Response Format
- **Answer**: Detailed response with specific information
- **Data References**: Citations showing which entities, relationships, and reports were used
- **Context**: Number of entities and relationships consulted

### Global Search Response Format  
- **Answer**: High-level thematic response with markdown formatting
- **Data References**: Citations to community reports
- **Sections**: Organized by themes or topics

## Tips for Best Results

1. **Be specific with local search**: Ask about particular entities, relationships, or attributes
2. **Be broad with global search**: Ask about themes, patterns, or organizational insights
3. **Use proper names**: Reference specific people, projects, or departments from the documents
4. **Iterate**: If the answer isn't what you expected, try rephrasing or using a different search method

## Troubleshooting

**Issue**: Search returns "I do not know"
- **Solution**: Try the other search method (local vs global)
- **Solution**: Make your query more specific or use entity names from the knowledge graph

**Issue**: Response lacks detail
- **Solution**: Use local search for specific details
- **Solution**: Lower `--community-level` for broader context

**Issue**: Response is too broad
- **Solution**: Use higher `--community-level` value (up to 2)
- **Solution**: Make your query more specific
