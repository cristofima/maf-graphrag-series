# GraphRAG Query Guide

This guide shows how to query the TechVenture Inc. knowledge graph built with GraphRAG.

## Quick Start

Use the provided PowerShell script to run queries:

```powershell
# Local Search - Specific entity-focused questions
.\run_query.ps1 -Method local -Query "Who leads Project Alpha?"

# Global Search - Broad organizational questions  
.\run_query.ps1 -Method global -Query "What are the main projects at TechVenture Inc?"
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
.\run_query.ps1 -Method local -Query "Who leads Project Alpha?"

# Technology Stack
.\run_query.ps1 -Method local -Query "What technologies are used in Project Alpha?"

# Team Members
.\run_query.ps1 -Method local -Query "Who works on the Infrastructure Department?"

# Relationships
.\run_query.ps1 -Method local -Query "What is the relationship between David Kumar and Emily Harrison?"

# Roles
.\run_query.ps1 -Method local -Query "What does Jennifer Park do?"
```

### Global Search Queries

```powershell
# Organizational Overview
.\run_query.ps1 -Method global -Query "What are the main projects and teams at TechVenture Inc?"

# Strategic Initiatives  
.\run_query.ps1 -Method global -Query "What are the key strategic initiatives?"

# Technology Landscape
.\run_query.ps1 -Method global -Query "What technologies are being used across the organization?"

# Departmental Structure
.\run_query.ps1 -Method global -Query "Describe the organizational structure and key departments"
```

## Advanced Options

The underlying command supports additional options:

```powershell
graphrag query `
    --method [local|global|drift|basic] `
    --query "Your question" `
    --root "." `
    --data "output" `
    --community-level 2 `
    --response-type "Multiple Paragraphs"
```

**Parameters:**
- `--method`: Search algorithm (local, global, drift, basic)
- `--query`: Your question
- `--root`: Project root directory
- `--data`: Output directory with parquet files
- `--community-level`: Community hierarchy level (0-2, higher = smaller communities)
- `--response-type`: Format of response (e.g., "Multiple Paragraphs", "Single Paragraph", "List of 3-7 Points")

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
