# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Poetry Dependency Management

- **Poetry configuration** ([pyproject.toml](pyproject.toml))
  - Replaces `requirements.txt` as the standard for dependency management
  - Part 1 dependencies: graphrag, pandas, pyarrow, openai, python-dotenv, aiohttp
  - Dev dependencies: pytest, jupyter, networkx, matplotlib
  - Python version requirement: >=3.10
  - Lock file (`poetry.lock`) for reproducible builds
  
- **PowerShell scripts updated** for Poetry
  - `run_index.ps1` auto-detects Poetry (falls back to venv if unavailable)
  - `run_query.ps1` auto-detects Poetry (falls back to venv if unavailable)
  
- **Documentation**
  - `docs/poetry-guide.md` - How to use Poetry with this project
  
- **Updated README** with Poetry as the standard installation method

### Changed

- **Dependency management** - Poetry is now the standard (no more requirements.txt)
- **Installation process** - `poetry install` instead of `pip install -r requirements.txt`

### Technical Rationale

**Why Poetry?**
- ✅ Lock file (`poetry.lock`) ensures reproducible builds
- ✅ Dev/prod separation prevents bloated production deployments
- ✅ Automatic conflict detection prevents runtime errors
- ✅ Python version enforcement (>=3.10 required by GraphRAG)
- ✅ Industry standard for modern Python projects

**YAGNI Applied:**
- Only Part 1 dependencies included
- Future dependencies (Parts 2-8) will be added incrementally as implemented
- No premature optimization or unused dependencies

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

[1.0.0]: https://github.com/cristofima/maf-graphrag-series/releases/tag/v1.0.0
