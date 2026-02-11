# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-02-11

### ⚠️ BREAKING CHANGES

- **GraphRAG 3.0.x upgrade** - Major dependency update ([cc0054b](https://github.com/cristofima/maf-graphrag-series/commit/cc0054b))
  - Python >=3.11,<3.13 (was >=3.10)
  - pandas 2.3.0, pyarrow 22.0.0
  - New configuration schema in `settings.yaml` (`completion_models`/`embedding_models`)
  - Updated prompts for v3.0.x compatibility

### Added - Part 2: GraphRAG MCP Server

- **`mcp_server/` module** - Model Context Protocol server ([5cfb788](https://github.com/cristofima/maf-graphrag-series/commit/5cfb788))
  - `mcp_server/server.py` - FastMCP server with HTTP/SSE on port 8011
  - `mcp_server/tools/` - 5 MCP tools implementation
  - `mcp_server/tools/source_resolver.py` - Source traceability ([6e5b3a9](https://github.com/cristofima/maf-graphrag-series/commit/6e5b3a9))

- **MCP Tools exposed via HTTP/SSE**
  - `search_knowledge_graph` - Main entry point for queries
  - `local_search` - Entity-focused search
  - `global_search` - Community/thematic search
  - `list_entities` - List entities by type
  - `get_entity` - Get specific entity details

- **Testing & Tooling**
  - `notebooks/02_test_mcp_server.ipynb` - MCP tool testing notebook
  - `run_mcp_server.py` - Convenience script to start MCP server

- **Dependencies added (Part 2 group)**
  - `fastmcp 0.2.0` - Model Context Protocol server framework
  - `uvicorn[standard] ^0.40.0` - ASGI server for HTTP/SSE

### Added - Core Python Module (replaces `src/`)

- **`core/` Python module** - Modern API for GraphRAG 3.0.x ([998e3b9](https://github.com/cristofima/maf-graphrag-series/commit/998e3b9))
  - `core/config.py` - Configuration loading and validation
  - `core/data_loader.py` - Parquet file loading with `GraphData` dataclass
  - `core/search.py` - Async search functions (local, global, drift, basic)
  - `core/index.py` - CLI for indexing with async `build_index`
  - `core/example.py` - CLI for querying

- **Python CLI commands**
  - `poetry run python -m core.index` - Build knowledge graph
  - `poetry run python -m core.example "Your question"` - Query CLI

### Added - Input Document Expansion

- **7 new input documents** - Expanded from 3 to 10 documents ([c3da728](https://github.com/cristofima/maf-graphrag-series/commit/c3da728))
  - `project_beta.md` - Healthcare analytics project
  - `technical_architecture.md` - System architecture
  - `technology_stack.md` - Tech standards
  - `customers_partners.md` - Customer case studies
  - `engineering_processes.md` - Development methodology
  - `incidents_postmortems.md` - Incident history (5 postmortems)
  - `company_events_timeline.md` - Company milestones

### Added - Poetry Dependency Management

- **Poetry configuration** ([728f4b6](https://github.com/cristofima/maf-graphrag-series/commit/728f4b6))
  - `pyproject.toml` replaces `requirements.txt`
  - Lock file (`poetry.lock`) for reproducible builds
  - Dev/prod dependency separation

### Removed

- **`src/` folder** - Superseded by `core/` module ([998e3b9](https://github.com/cristofima/maf-graphrag-series/commit/998e3b9))
- **`run_query.ps1`** - Replaced by `poetry run python -m core.example`
- **`run_index.ps1`** - Replaced by `poetry run python -m core.index` ([41de572](https://github.com/cristofima/maf-graphrag-series/commit/41de572))

### Changed

- **Notebook 01** - Updated for GraphRAG 3.0.x API ([5bf0482](https://github.com/cristofima/maf-graphrag-series/commit/5bf0482))
- **Documentation** - Updated for new CLI workflow and v3.0.x migration ([203b470](https://github.com/cristofima/maf-graphrag-series/commit/203b470), [3e979d6](https://github.com/cristofima/maf-graphrag-series/commit/3e979d6))
- **Installation** - `poetry install` instead of `pip install -r requirements.txt`

---

## [1.0.0] - 2026-02-03

### Added

- **GraphRAG Indexing and Query System**
  - CLI scripts for building knowledge graphs from documents ([d4de575](https://github.com/cristofima/maf-graphrag-series/commit/d4de575))
  - PowerShell scripts (`run_index.ps1`, `run_query.ps1`) with UTF-8 encoding support and environment variable loading ([323ceae](https://github.com/cristofima/maf-graphrag-series/commit/323ceae))
  - Local search functionality for entity-focused queries
  - Global search functionality for thematic/organizational queries
  - Python modules: `indexer.py`, `local_search.py`, `global_search.py`

- **Azure Infrastructure**
  - Terraform configuration for Azure OpenAI, Storage Account, and state management ([cf7c996](https://github.com/cristofima/maf-graphrag-series/commit/cf7c996))
  - Multi-region deployment strategy
  - Backend state storage configuration with `backend.hcl`
  - Infrastructure bootstrap scripts

- **GraphRAG Configuration**
  - LLM and embeddings configuration in `settings.yaml` ([95badce](https://github.com/cristofima/maf-graphrag-series/commit/95badce), [4792409](https://github.com/cristofima/maf-graphrag-series/commit/4792409))
  - Custom prompt templates for entity extraction, community reporting, and search operations ([1397a81](https://github.com/cristofima/maf-graphrag-series/commit/1397a81))
  - Support for Azure OpenAI GPT-4o and text-embedding-3-small models

- **Sample Documents**
  - Interconnected markdown documents demonstrating knowledge graph relationships ([168fc66](https://github.com/cristofima/maf-graphrag-series/commit/168fc66))
  - Documents placed in `input/documents/` for indexing

- **Data Exploration**
  - Jupyter notebook `01_explore_graph.ipynb` for visualizing knowledge graph outputs ([cf80620](https://github.com/cristofima/maf-graphrag-series/commit/cf80620), [7cff002](https://github.com/cristofima/maf-graphrag-series/commit/7cff002))
  - Entity tables and relationship analysis capabilities

- **Documentation**
  - Implementation notes for Part 1: GraphRAG Fundamentals ([1e62a26](https://github.com/cristofima/maf-graphrag-series/commit/1e62a26))
  - Query guide with examples for local and global searches ([d2a2c62](https://github.com/cristofima/maf-graphrag-series/commit/d2a2c62))
  - Azure deployment lessons learned documentation ([74bc102](https://github.com/cristofima/maf-graphrag-series/commit/74bc102))
  - Comprehensive README with project structure and usage instructions ([96608f8](https://github.com/cristofima/maf-graphrag-series/commit/96608f8))

- **Project Structure**
  - Initial project scaffolding with organized folder structure ([bee9c20](https://github.com/cristofima/maf-graphrag-series/commit/bee9c20))
  - Separation of concerns: `src/`, `infra/`, `prompts/`, `input/`, `output/`, `docs/`, `notebooks/`
  - Requirements file with GraphRAG v1.2.0 dependencies

### Changed

- Updated copyright holder in LICENSE file ([d3ab331](https://github.com/cristofima/maf-graphrag-series/commit/d3ab331))

---

[2.0.0]: https://github.com/cristofima/maf-graphrag-series/releases/tag/v2.0.0
