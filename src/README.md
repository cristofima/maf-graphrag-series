# Source Code

> ⚠️ **Important**: For GraphRAG v1.2.0, use the CLI scripts in the project root instead of these Python scripts.

## Recommended Approach (GraphRAG v1.2.0)

The GraphRAG CLI is the recommended way to run indexing and queries:

```powershell
# Build the knowledge graph
.\run_index.ps1

# Run queries
.\run_query.ps1 "Who leads Project Alpha?" -Method local
.\run_query.ps1 "Summarize the organization" -Method global
```

See [docs/query-guide.md](../docs/query-guide.md) for detailed query examples.

## Legacy Python Scripts (Reference Only)

These scripts were designed for earlier GraphRAG API versions and may not work with v1.2.0. They are kept for reference purposes:

| File | Purpose | Status |
|------|---------|--------|
| `indexer.py` | Build knowledge graph from documents | ⚠️ Use `run_index.ps1` instead |
| `local_search.py` | Entity-focused queries | ⚠️ Use `run_query.ps1 -Method local` |
| `global_search.py` | Community-level queries | ⚠️ Use `run_query.ps1 -Method global` |

### Why CLI is Preferred

1. **Version Compatibility**: CLI handles API changes between versions
2. **Simpler Configuration**: Uses `settings.yaml` directly
3. **Better Error Handling**: Built-in validation and prompts
4. **UTF-8 Support**: PowerShell scripts handle Windows encoding issues
