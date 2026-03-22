# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.2.0] - 2026-03-22

### Added

- **`agents/tools.py`** — Local tool functions for agent-side data processing ([f0d244c](https://github.com/cristofima/maf-graphrag-series/commit/f0d244c))
  - `format_as_table` — Formats structured data as readable tables for agent responses
  - `extract_key_entities` — Extracts key entities from text for focused analysis
- **Factory functions for state isolation** ([7f647f5](https://github.com/cristofima/maf-graphrag-series/commit/7f647f5)) — Factory-based construction for workflow components, improving testability and state isolation
- **`MCPWorkflowBase`** ([6959427](https://github.com/cristofima/maf-graphrag-series/commit/6959427)) — Shared base class managing MCP tool connections for sequential and handoff workflows
- **SonarCloud integration** ([7ba54d2](https://github.com/cristofima/maf-graphrag-series/commit/7ba54d2)) — Quality metric badges in README for maintainability, reliability, and security ratings
- **Testing** ([3ea31a9](https://github.com/cristofima/maf-graphrag-series/commit/3ea31a9), [f0d244c](https://github.com/cristofima/maf-graphrag-series/commit/f0d244c), [7f647f5](https://github.com/cristofima/maf-graphrag-series/commit/7f647f5))
  - Unit tests for `mcp_server` — config, tools, types, data caching, entity querying, global/local search, source resolver, and input validation
  - Unit tests for `workflows` — `WorkflowStep` and `WorkflowResult` classes
  - Tests for local tools (`format_as_table`, `extract_key_entities`), middleware (logging, token counting, query rewriting), multi-provider config, and supervisor module
  - Factory function unit tests for state isolation
- **CI enhancements**
  - Concurrency group with auto-cancel for in-progress runs on the same branch ([08f3c08](https://github.com/cristofima/maf-graphrag-series/commit/08f3c08))
  - Ruff format check step alongside linting ([bd8e6eb](https://github.com/cristofima/maf-graphrag-series/commit/bd8e6eb))
  - Least privilege permissions structure ([0b2e745](https://github.com/cristofima/maf-graphrag-series/commit/0b2e745))

### Fixed

- **Source ID type conversion** ([be73f03](https://github.com/cristofima/maf-graphrag-series/commit/be73f03)) — Ensured source ID is converted to string before integer conversion to prevent `TypeError`
- **WebSocket deprecation** ([5eaeaf7](https://github.com/cristofima/maf-graphrag-series/commit/5eaeaf7)) — Disabled WebSocket protocol in `uvicorn.run()` to avoid `DeprecationWarning`
- **Linting per-file ignore** ([63e7d2f](https://github.com/cristofima/maf-graphrag-series/commit/63e7d2f)) — Added `UP035` ignore for `types.py` to prevent false positive linting errors

### Changed

- **Agent context management**
  - Streamlined workflow execution and enhanced agent context management ([f5cf9ad](https://github.com/cristofima/maf-graphrag-series/commit/f5cf9ad))
  - Simplified `ask` method by removing `timeout` parameter; uses internal `asyncio` timeout instead ([6bbe86b](https://github.com/cristofima/maf-graphrag-series/commit/6bbe86b))
  - Environment variable loading in correct context with timeout parameter for `KnowledgeCaptainRunner.ask()` ([0f7d372](https://github.com/cristofima/maf-graphrag-series/commit/0f7d372))
- **MCP server enhancements** ([7a8b92f](https://github.com/cristofima/maf-graphrag-series/commit/7a8b92f)) — Added CORS support, response caching, and improved error handling in tools
- **Source resolution** ([9ee62ae](https://github.com/cristofima/maf-graphrag-series/commit/9ee62ae)) — Modularized source resolution functions for improved readability and maintainability
- **Search functions** ([e2e1476](https://github.com/cristofima/maf-graphrag-series/commit/e2e1476)) — Streamlined community level determination and context printing
- **Workflow CLI** ([70438b5](https://github.com/cristofima/maf-graphrag-series/commit/70438b5)) — Modularized workflow execution and example query display
- **Replaced Black with Ruff** ([3012173](https://github.com/cristofima/maf-graphrag-series/commit/3012173)) — Ruff now handles both linting and formatting; updated Python version compatibility
- **Dependencies updated**
  - `agent-framework-core` → `1.0.0rc5`, `agent-framework-orchestrations` → `1.0.0b260319` ([aa22269](https://github.com/cristofima/maf-graphrag-series/commit/aa22269))
  - `rich` → `14.0.0`, `fastmcp` → `3.1.0`, `uvicorn` → `>=0.41.0,<1.0.0` ([6f4ee94](https://github.com/cristofima/maf-graphrag-series/commit/6f4ee94))
  - `pytest` → `9.0.0`, `pytest-asyncio` → `1.3.0`, `pytest-cov` → `7.0.0`, `ruff` → `0.15.0` ([6f4ee94](https://github.com/cristofima/maf-graphrag-series/commit/6f4ee94))
- **Code quality improvements**
  - Improved formatting and readability across entry points, agents, core, MCP server, and workflows ([78a516f](https://github.com/cristofima/maf-graphrag-series/commit/78a516f), [3128350](https://github.com/cristofima/maf-graphrag-series/commit/3128350), [73d4835](https://github.com/cristofima/maf-graphrag-series/commit/73d4835))
  - Improved notebook formatting and readability ([57112c8](https://github.com/cristofima/maf-graphrag-series/commit/57112c8))
  - Removed unnecessary blank lines in documentation and code comments ([985d1b0](https://github.com/cristofima/maf-graphrag-series/commit/985d1b0))
- **Test improvements**
  - Updated assertions to use `pytest.approx` for floating-point comparisons ([f20f111](https://github.com/cristofima/maf-graphrag-series/commit/f20f111))
  - Cleaned up unused imports and formatting in test files ([823ed12](https://github.com/cristofima/maf-graphrag-series/commit/823ed12))
- **Coverage configuration** ([4bf9b42](https://github.com/cristofima/maf-graphrag-series/commit/4bf9b42)) — Expanded coverage source to include additional directories
- **README** ([a25b37c](https://github.com/cristofima/maf-graphrag-series/commit/a25b37c), [a5a5a54](https://github.com/cristofima/maf-graphrag-series/commit/a5a5a54), [10c0001](https://github.com/cristofima/maf-graphrag-series/commit/10c0001)) — Updated for MAF 1.0.0rc5 changes, MCP lifecycle management details, version changes, and test command adjustments
- **`.env.example`** ([0ae3f63](https://github.com/cristofima/maf-graphrag-series/commit/0ae3f63)) — Added optional MCP server configuration variables (`MCP_HOST`, `MCP_PORT`)

---

## [3.1.0] - 2026-03-07

### Added - Part 4: Multi-Agent Workflow Patterns

- **`workflows/` module** - Three orchestration patterns for multi-agent query processing ([8dda887](https://github.com/cristofima/maf-graphrag-series/commit/8dda887))
  - `workflows/base.py` - Shared types: `WorkflowType` enum, `WorkflowStep` and `WorkflowResult` dataclasses with step tracing, timing, and metadata
  - `workflows/sequential.py` - `SequentialWorkflow` — structured research pipeline (Analyze → Search → Write) for complex queries
  - `workflows/concurrent.py` - `ConcurrentWorkflow` — parallel entity + thematic search with synthesis for comprehensive answers
  - `workflows/handoff.py` - `HandoffWorkflow` — query classification and routing to specialized expert agents
  - `workflows/__init__.py` - Public re-exports (`SequentialWorkflow`, `ConcurrentWorkflow`, `HandoffWorkflow`, `WorkflowResult`, `WorkflowStep`, `WorkflowType`)

- **Multi-agent workflow patterns**
  - All workflows are async context managers (`async with WorkflowClass()`) managing MCP connection lifecycle
  - Agent-specific system prompts for structured reasoning and output formatting (defined inline per workflow)
  - Step-level traceability and logging for auditing and debugging
  - Shared infrastructure via `agents/supervisor.py`: `create_mcp_tool()` and `create_azure_client()`

- **`run_workflow.py`** - CLI entry point with Rich formatting; interactive menu and direct mode (`poetry run python run_workflow.py sequential "query"`)

- **CI/CD pipeline** ([c921214](https://github.com/cristofima/maf-graphrag-series/commit/c921214))
  - GitHub Actions workflow for automated testing and linting
  - CI triggers on relevant file changes for push and pull_request events ([94f3f45](https://github.com/cristofima/maf-graphrag-series/commit/94f3f45))
  - pip-based Poetry installation with in-project virtualenvs ([5a6c2b5](https://github.com/cristofima/maf-graphrag-series/commit/5a6c2b5))

- **Testing** ([1d55930](https://github.com/cristofima/maf-graphrag-series/commit/1d55930))
  - Unit tests for `AgentConfig`, `MCPConfig`, and workflow components
  - Class-based test organization with `monkeypatch` for env var isolation

- **Dev dependencies added** ([a383b06](https://github.com/cristofima/maf-graphrag-series/commit/a383b06))
  - `pytest-cov` - Coverage reporting
  - `mypy` - Static type checking with `disallow_untyped_defs = true`
  - `ruff` - Linting (line-length 120, `E/W/F/I/B/C4/UP` rules)

### Changed

- **Project layout** — Migrated to PyPA `src/` layout ([3539f8e](https://github.com/cristofima/maf-graphrag-series/commit/3539f8e))
  - Moved `core/`, `agents/`, `mcp_server/`, and `workflows/` into `src/` directory
  - Updated `pyproject.toml`: `pythonpath` from `"."` to `"src"`, coverage source paths prefixed with `src/`
  - No import changes required — bare package names resolve via `pythonpath`
- **Import paths** ([1864b68](https://github.com/cristofima/maf-graphrag-series/commit/1864b68)) — Updated all import paths to use `src/` directory structure
- **Dependencies updated**
  - `agent-framework-core` → `1.0.0rc3`, `agent-framework-orchestrations` → `1.0.0b260304` ([163f0e3](https://github.com/cristofima/maf-graphrag-series/commit/163f0e3), [a383b06](https://github.com/cristofima/maf-graphrag-series/commit/a383b06))
  - `graphrag` → `3.0.2` ([bd29525](https://github.com/cristofima/maf-graphrag-series/commit/bd29525))
- **Code quality improvements**
  - Added type hints across multiple files for improved clarity and type safety ([53ce6f7](https://github.com/cristofima/maf-graphrag-series/commit/53ce6f7))
  - Cleaned up code formatting and readability ([a6ecabf](https://github.com/cristofima/maf-graphrag-series/commit/a6ecabf))
  - Cleaned up imports in `run_workflow.py` and `server.py` ([c8caa7e](https://github.com/cristofima/maf-graphrag-series/commit/c8caa7e))
  - Enhanced logging and error handling across workflows; updated YAML settings ([1dc48d6](https://github.com/cristofima/maf-graphrag-series/commit/1dc48d6))
- **README** ([54ed926](https://github.com/cristofima/maf-graphrag-series/commit/54ed926), [99a294a](https://github.com/cristofima/maf-graphrag-series/commit/99a294a), [482da8a](https://github.com/cristofima/maf-graphrag-series/commit/482da8a)) — Added Part 4 section with workflow architecture diagrams, visual representations, and updated for `src/` directory structure
- **`docs/part4-implementation-notes.md`** ([54ed926](https://github.com/cristofima/maf-graphrag-series/commit/54ed926)) — Added detailed implementation notes for Workflow Patterns including architecture, pattern details, and performance optimizations
- **`docs/lessons-learned.md`** ([54ed926](https://github.com/cristofima/maf-graphrag-series/commit/54ed926)) — Enhanced with insights from MAF and GraphRAG integration challenges
- **Version bump** — 3.0.0 → 3.1.0

---

## [3.0.0] - 2026-02-18

### ⚠️ BREAKING CHANGES

- **MCP Server transport split** ([1ca5879](https://github.com/cristofima/maf-graphrag-series/commit/1ca5879)) — `streamable_http_app()` and `sse_app()` now serve different endpoints
  - `/mcp` (Streamable HTTP) — for `MCPStreamableHTTPTool` in Microsoft Agent Framework
  - `/sse` (SSE) — for MCP Inspector and browser-based clients
  - Clients connecting via `/sse` for MAF integration must update URL to `/mcp`

### Added - Part 3: Knowledge Captain Agent

- **`agents/` module** - Microsoft Agent Framework integration ([d71708c](https://github.com/cristofima/maf-graphrag-series/commit/d71708c))
  - `agents/config.py` - `AgentConfig` dataclass; loads Azure OpenAI config from env; supports `api_key` and `azure_cli` auth
  - `agents/prompts.py` - `KNOWLEDGE_CAPTAIN_PROMPT` system prompt driving tool selection
  - `agents/supervisor.py` - `KnowledgeCaptainRunner` context manager; `create_knowledge_captain()`; `AgentResponse` dataclass
  - `agents/__init__.py` - Public re-exports (`KnowledgeCaptainRunner`, `AgentConfig`)

- **Knowledge Captain agent pattern**
  - Single `Agent` (GPT-4o) with `MCPStreamableHTTPTool` — no separate routing layer
  - System prompt routes questions to the right MCP tool (`local_search`, `global_search`, `list_entities`, `get_entity`)
  - `AgentSession` maintains conversation memory across multiple turns
  - `KnowledgeCaptainRunner` async context manager for safe setup/teardown
  - URL validation in `create_mcp_tool()` auto-corrects `/sse` → `/mcp`

- **`run_agent.py`** - CLI entry point with Rich formatting; interactive mode and single-query mode

- **Dependencies added**
  - `microsoft-agent-framework 1.0.0b260212` - `Agent`, `MCPStreamableHTTPTool`, `AzureOpenAIChatClient`, `AgentSession`
  - `azure-identity ^1.19.0` - Azure CLI credential support via `DefaultAzureCredential`
  - `httpx ^0.28.0` - Async HTTP client for MCP server communication

### Changed

- **`mcp_server/server.py`** ([1ca5879](https://github.com/cristofima/maf-graphrag-series/commit/1ca5879)) — Added `streamable_http_app()` route at `/mcp` alongside existing `sse_app()` at `/sse`; both transports served simultaneously on port 8011
- **Version bump** — 2.0.0 → 3.0.0
- **README** ([340b7b0](https://github.com/cristofima/maf-graphrag-series/commit/340b7b0), [030b71b](https://github.com/cristofima/maf-graphrag-series/commit/030b71b)) — Added Part 3 section with architecture diagrams, Mermaid flow, quick start, and usage examples
- **`docs/lessons-learned.md`** ([030b71b](https://github.com/cristofima/maf-graphrag-series/commit/030b71b)) — Added transport protocol notes and MAF integration lessons
- **`docs/part2-implementation-notes.md`** ([adfcea0](https://github.com/cristofima/maf-graphrag-series/commit/adfcea0)) — Clarified Streamable HTTP vs SSE transport roles

---

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
