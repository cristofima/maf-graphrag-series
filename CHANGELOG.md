# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.1.0] - 2026-08-03

### Added

- **Router-first runtime**: Production router runtime with `RouterClassifier` and `RouterWorkflow`, including retry, fallback, and confidence-based routing. ([19dc6c4](https://github.com/cristofima/maf-graphrag-series/commit/19dc6c4))
- **Out-of-context routing path**: Router `out_of_context` branch and dedicated chatbot endpoint for Agents Playground validation. ([5b4aed6](https://github.com/cristofima/maf-graphrag-series/commit/5b4aed6))
- **Router evaluation stack**: Reusable evaluation workflow and PR merge gate with local, Foundry, and optional red-team modes. ([4b9bfd3](https://github.com/cristofima/maf-graphrag-series/commit/4b9bfd3))

### Changed

- **Workflow behavior**: Progress/status handling simplification in message processing, plus clearer router event handling and metadata extraction. ([e4b48be](https://github.com/cristofima/maf-graphrag-series/commit/e4b48be), [c9a5b27](https://github.com/cristofima/maf-graphrag-series/commit/c9a5b27))
- **PR gate behavior**: Required router gate execution on PR lifecycle updates, with expensive evaluation controlled by internal path-diff detection and route metrics publication in job/PR summaries. ([8f34af6](https://github.com/cristofima/maf-graphrag-series/commit/8f34af6), [3cf9c12](https://github.com/cristofima/maf-graphrag-series/commit/3cf9c12), [db5a3cd](https://github.com/cristofima/maf-graphrag-series/commit/db5a3cd))
- **Developer experience**: Documentation and examples aligned with router-first architecture and DevUI entrypoints. ([ec658fe](https://github.com/cristofima/maf-graphrag-series/commit/ec658fe), [a8e8fca](https://github.com/cristofima/maf-graphrag-series/commit/a8e8fca), [7951811](https://github.com/cristofima/maf-graphrag-series/commit/7951811), [60b0aa0](https://github.com/cristofima/maf-graphrag-series/commit/60b0aa0))

### Fixed

- **Runtime reliability**: Error-handling hardening in workflow execution and response processing, plus confidence score normalization for router decisions. ([e154b45](https://github.com/cristofima/maf-graphrag-series/commit/e154b45), [41f0f95](https://github.com/cristofima/maf-graphrag-series/commit/41f0f95), [9157583](https://github.com/cristofima/maf-graphrag-series/commit/9157583), [3b754f1](https://github.com/cristofima/maf-graphrag-series/commit/3b754f1))
- **CI reliability**: Reusable-workflow deadlock removal by dropping nested concurrency and reduced cache-save collisions in parallel uv setup jobs. ([1c1a414](https://github.com/cristofima/maf-graphrag-series/commit/1c1a414))

### Documentation

- Router integration, evaluation-governance, and release-note documentation updates for the router workflow stack. ([7e4748d](https://github.com/cristofima/maf-graphrag-series/commit/7e4748d), [66cb27d](https://github.com/cristofima/maf-graphrag-series/commit/66cb27d), [ec658fe](https://github.com/cristofima/maf-graphrag-series/commit/ec658fe))

### Internal

- CI/release automation alignment: Node 24-compatible GitHub Actions runtime updates, reusable workflow permission fixes, and branch trigger coverage for feature/refactor branches. ([af9b7a7](https://github.com/cristofima/maf-graphrag-series/commit/af9b7a7), [f17a6d3](https://github.com/cristofima/maf-graphrag-series/commit/f17a6d3), [5d57f57](https://github.com/cristofima/maf-graphrag-series/commit/5d57f57))

---

## [4.0.0] - 2026-07-22

### Breaking

- **Dependency management**: Poetry-to-uv migration across tooling and docs, with the updated workflow documented in [pyproject.toml](pyproject.toml), [docs/uv-guide.md](docs/uv-guide.md), and [uv.lock](uv.lock). ([16f952c](https://github.com/cristofima/maf-graphrag-series/commit/16f952c))

### Added

- **Evaluation toolkit**: Dedicated evaluation package with custom GraphRAG validators, Azure AI Evaluation scripts, OpenTelemetry monitoring hooks, and seed datasets in [src/evaluation/README.md](src/evaluation/README.md), [src/evaluation/scripts/run_batch_evaluation.py](src/evaluation/scripts/run_batch_evaluation.py), and [src/evaluation/monitoring/otel_setup.py](src/evaluation/monitoring/otel_setup.py). ([aa56389](https://github.com/cristofima/maf-graphrag-series/commit/aa56389))
- **Quality metrics**: Relevance, coherence, and response-completeness evaluators with conditional tool-call gating in [src/evaluation/evaluators/builtin.py](src/evaluation/evaluators/builtin.py) and [src/evaluation/scripts/run_batch_evaluation.py](src/evaluation/scripts/run_batch_evaluation.py). ([7c6af20](https://github.com/cristofima/maf-graphrag-series/commit/7c6af20))
- **Testing coverage**: Expanded regression suites for agents, evaluation, MCP server, and workflows covering new configuration paths under [tests](tests). ([6ab5554](https://github.com/cristofima/maf-graphrag-series/commit/6ab5554), [2a6b543](https://github.com/cristofima/maf-graphrag-series/commit/2a6b543), [8482906](https://github.com/cristofima/maf-graphrag-series/commit/8482906))

### Fixed

- **Dataset path safety**: `_resolve_cli_data_path` now constrains batch evaluations to repository datasets and validates file extensions in [src/evaluation/scripts/run_batch_evaluation.py](src/evaluation/scripts/run_batch_evaluation.py). ([9c575b6](https://github.com/cristofima/maf-graphrag-series/commit/9c575b6))
- **Runtime alignment**: Normalized agent and evaluation configuration defaults to keep provider credentials and deployments consistent in [src/agents/config.py](src/agents/config.py) and [src/evaluation/config.py](src/evaluation/config.py). ([bc20a56](https://github.com/cristofima/maf-graphrag-series/commit/bc20a56))
- **Module entrypoints**: Added shim packages and sitecustomize support so `uv run python -m …` works from the repository root via [agents/**init**.py](agents/__init__.py), [core/**init**.py](core/__init__.py), [evaluation/**init**.py](evaluation/__init__.py), [mcp_server/**init**.py](mcp_server/__init__.py), and [sitecustomize.py](sitecustomize.py). ([b0fc39a](https://github.com/cristofima/maf-graphrag-series/commit/b0fc39a))

### Changed

- **Infrastructure**: Terraform provisioning for Azure AI Services with Application Insights integration and Foundry project-management toggles in [infra/main.tf](infra/main.tf) and companion variables files. ([4bcd1dc](https://github.com/cristofima/maf-graphrag-series/commit/4bcd1dc))
- **Dependency stack**: Telemetry and evaluation package additions plus refreshed Agent Framework version bounds in [pyproject.toml](pyproject.toml) and [uv.lock](uv.lock). ([101d2fb](https://github.com/cristofima/maf-graphrag-series/commit/101d2fb))
- **Evaluation helpers**: Reduced duplication and streamlined evaluator wiring in [src/evaluation/evaluators/builtin.py](src/evaluation/evaluators/builtin.py) and [src/evaluation/evaluators/relationship_validity.py](src/evaluation/evaluators/relationship_validity.py). ([c87f376](https://github.com/cristofima/maf-graphrag-series/commit/c87f376), [05bb126](https://github.com/cristofima/maf-graphrag-series/commit/05bb126))
- **CI pipeline**: Hardened dependency installation and added SonarQube coverage publishing in [.github/workflows/ci.yml](.github/workflows/ci.yml) and [sonar-project.properties](sonar-project.properties). ([e880e56](https://github.com/cristofima/maf-graphrag-series/commit/e880e56), [456b4ca](https://github.com/cristofima/maf-graphrag-series/commit/456b4ca), [e667561](https://github.com/cristofima/maf-graphrag-series/commit/e667561))

### Documentation

- Refreshed developer guides with uv instructions and expanded evaluation coverage notes in [README.md](README.md), [docs/part5-implementation-notes.md](docs/part5-implementation-notes.md), and [docs/uv-guide.md](docs/uv-guide.md). ([16f952c](https://github.com/cristofima/maf-graphrag-series/commit/16f952c), [29a368c](https://github.com/cristofima/maf-graphrag-series/commit/29a368c))

## [3.2.0] - 2026-03-22

### Added

- **`agents/tools.py`**: Local tool functions for agent-side data processing ([f0d244c](https://github.com/cristofima/maf-graphrag-series/commit/f0d244c))
  - `format_as_table` — Formats structured data as readable tables for agent responses
  - `extract_key_entities` — Extracts key entities from text for focused analysis
- **Factory functions for state isolation**: Factory-based workflow-component construction improving testability and isolation. ([7f647f5](https://github.com/cristofima/maf-graphrag-series/commit/7f647f5))
- **`MCPWorkflowBase`**: Shared base class for MCP tool-connection management in sequential and handoff workflows. ([6959427](https://github.com/cristofima/maf-graphrag-series/commit/6959427))
- **SonarCloud integration**: README quality-metric badges for maintainability, reliability, and security ratings. ([7ba54d2](https://github.com/cristofima/maf-graphrag-series/commit/7ba54d2))
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

- **Source ID type conversion**: String conversion before integer parsing to prevent `TypeError`. ([be73f03](https://github.com/cristofima/maf-graphrag-series/commit/be73f03))
- **WebSocket deprecation**: WebSocket protocol disabled in `uvicorn.run()` to avoid `DeprecationWarning`. ([5eaeaf7](https://github.com/cristofima/maf-graphrag-series/commit/5eaeaf7))
- **Linting per-file ignore**: `UP035` ignore for `types.py` to prevent false-positive linting errors. ([63e7d2f](https://github.com/cristofima/maf-graphrag-series/commit/63e7d2f))

### Changed

- **Agent context management**
  - Streamlined workflow execution and enhanced agent context management ([f5cf9ad](https://github.com/cristofima/maf-graphrag-series/commit/f5cf9ad))
  - Simplified `ask` method by removing `timeout` parameter; uses internal `asyncio` timeout instead ([6bbe86b](https://github.com/cristofima/maf-graphrag-series/commit/6bbe86b))
  - Environment variable loading in correct context with timeout parameter for `KnowledgeCaptainRunner.ask()` ([0f7d372](https://github.com/cristofima/maf-graphrag-series/commit/0f7d372))
- **MCP server enhancements**: CORS support, response caching, and improved tool error handling. ([7a8b92f](https://github.com/cristofima/maf-graphrag-series/commit/7a8b92f))
- **Source resolution**: Modularized source-resolution functions for readability and maintainability. ([9ee62ae](https://github.com/cristofima/maf-graphrag-series/commit/9ee62ae))
- **Search functions**: Streamlined community-level determination and context printing. ([e2e1476](https://github.com/cristofima/maf-graphrag-series/commit/e2e1476))
- **Workflow CLI**: Modularized workflow execution and example-query display. ([70438b5](https://github.com/cristofima/maf-graphrag-series/commit/70438b5))
- **Formatting toolchain**: Black-to-Ruff replacement for linting and formatting, with updated Python compatibility. ([3012173](https://github.com/cristofima/maf-graphrag-series/commit/3012173))
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
- **Coverage configuration**: Expanded coverage-source scope to include additional directories. ([4bf9b42](https://github.com/cristofima/maf-graphrag-series/commit/4bf9b42))
- **README**: MAF 1.0.0rc5 updates, MCP lifecycle details, version updates, and test-command alignment. ([a25b37c](https://github.com/cristofima/maf-graphrag-series/commit/a25b37c), [a5a5a54](https://github.com/cristofima/maf-graphrag-series/commit/a5a5a54), [10c0001](https://github.com/cristofima/maf-graphrag-series/commit/10c0001))
- **`.env.example`**: Optional MCP server configuration variables (`MCP_HOST`, `MCP_PORT`). ([0ae3f63](https://github.com/cristofima/maf-graphrag-series/commit/0ae3f63))

---

## [3.1.0] - 2026-03-07

### Added

- **Part 4 workflow module**: Three orchestration patterns for multi-agent query processing. ([8dda887](https://github.com/cristofima/maf-graphrag-series/commit/8dda887))
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

- **`run_workflow.py`**: CLI entrypoint with Rich formatting, interactive menu, and direct mode (`poetry run python run_workflow.py sequential "query"`).

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

- **Project layout**: PyPA `src/` layout migration. ([3539f8e](https://github.com/cristofima/maf-graphrag-series/commit/3539f8e))
  - Moved `core/`, `agents/`, `mcp_server/`, and `workflows/` into `src/` directory
  - Updated `pyproject.toml`: `pythonpath` from `"."` to `"src"`, coverage source paths prefixed with `src/`
  - No import changes required — bare package names resolve via `pythonpath`
- **Import paths**: Import-path updates aligned with the `src/` directory structure. ([1864b68](https://github.com/cristofima/maf-graphrag-series/commit/1864b68))
- **Dependencies updated**
  - `agent-framework-core` → `1.0.0rc3`, `agent-framework-orchestrations` → `1.0.0b260304` ([163f0e3](https://github.com/cristofima/maf-graphrag-series/commit/163f0e3), [a383b06](https://github.com/cristofima/maf-graphrag-series/commit/a383b06))
  - `graphrag` → `3.0.2` ([bd29525](https://github.com/cristofima/maf-graphrag-series/commit/bd29525))
- **Code quality improvements**
  - Added type hints across multiple files for improved clarity and type safety ([53ce6f7](https://github.com/cristofima/maf-graphrag-series/commit/53ce6f7))
  - Cleaned up code formatting and readability ([a6ecabf](https://github.com/cristofima/maf-graphrag-series/commit/a6ecabf))
  - Cleaned up imports in `run_workflow.py` and `server.py` ([c8caa7e](https://github.com/cristofima/maf-graphrag-series/commit/c8caa7e))
  - Enhanced logging and error handling across workflows; updated YAML settings ([1dc48d6](https://github.com/cristofima/maf-graphrag-series/commit/1dc48d6))
- **README**: Part 4 section with workflow architecture diagrams and `src/`-layout updates. ([54ed926](https://github.com/cristofima/maf-graphrag-series/commit/54ed926), [99a294a](https://github.com/cristofima/maf-graphrag-series/commit/99a294a), [482da8a](https://github.com/cristofima/maf-graphrag-series/commit/482da8a))
- **`docs/part4-implementation-notes.md`**: Detailed workflow-pattern implementation notes, including architecture and optimization details. ([54ed926](https://github.com/cristofima/maf-graphrag-series/commit/54ed926))
- **`docs/lessons-learned.md`**: Additional insights from MAF and GraphRAG integration challenges. ([54ed926](https://github.com/cristofima/maf-graphrag-series/commit/54ed926))
- **Version bump**: 3.0.0 → 3.1.0.

---

## [3.0.0] - 2026-02-18

### Breaking

- **MCP server transport split**: `streamable_http_app()` and `sse_app()` serving distinct endpoints. ([1ca5879](https://github.com/cristofima/maf-graphrag-series/commit/1ca5879))
  - `/mcp` (Streamable HTTP) — for `MCPStreamableHTTPTool` in Microsoft Agent Framework
  - `/sse` (SSE) — for MCP Inspector and browser-based clients
  - Clients connecting via `/sse` for MAF integration must update URL to `/mcp`

### Added

- **Part 3 agents module**: Microsoft Agent Framework integration. ([d71708c](https://github.com/cristofima/maf-graphrag-series/commit/d71708c))
  - `agents/config.py` - `AgentConfig` dataclass; loads Azure OpenAI config from env; supports `api_key` and `azure_cli` auth
  - `agents/prompts.py` - `KNOWLEDGE_CAPTAIN_PROMPT` system prompt driving tool selection
  - `agents/supervisor.py` - `KnowledgeCaptainRunner` context manager; `create_knowledge_captain()`; `AgentResponse` dataclass
  - `agents/__init__.py` - Public re-exports (`KnowledgeCaptainRunner`, `AgentConfig`)

- **Knowledge Captain agent pattern**:
  - Single `Agent` (GPT-4o) with `MCPStreamableHTTPTool` — no separate routing layer
  - System prompt routes questions to the right MCP tool (`local_search`, `global_search`, `list_entities`, `get_entity`)
  - `AgentSession` maintains conversation memory across multiple turns
  - `KnowledgeCaptainRunner` async context manager for safe setup/teardown
  - URL validation in `create_mcp_tool()` auto-corrects `/sse` → `/mcp`

- **`run_agent.py`**: CLI entrypoint with Rich formatting, interactive mode, and single-query mode.

- **Dependencies**:
  - `microsoft-agent-framework 1.0.0b260212` - `Agent`, `MCPStreamableHTTPTool`, `AzureOpenAIChatClient`, `AgentSession`
  - `azure-identity ^1.19.0` - Azure CLI credential support via `DefaultAzureCredential`
  - `httpx ^0.28.0` - Async HTTP client for MCP server communication

### Changed

- **`mcp_server/server.py`**: `streamable_http_app()` route at `/mcp` alongside `sse_app()` at `/sse`, with both transports on port 8011. ([1ca5879](https://github.com/cristofima/maf-graphrag-series/commit/1ca5879))
- **Version bump**: 2.0.0 → 3.0.0.
- **README**: Part 3 section with architecture diagrams, Mermaid flow, quick start, and usage examples. ([340b7b0](https://github.com/cristofima/maf-graphrag-series/commit/340b7b0), [030b71b](https://github.com/cristofima/maf-graphrag-series/commit/030b71b))
- **`docs/lessons-learned.md`**: Transport protocol notes and MAF integration lessons. ([030b71b](https://github.com/cristofima/maf-graphrag-series/commit/030b71b))
- **`docs/part2-implementation-notes.md`**: Clarified Streamable HTTP vs SSE transport roles. ([adfcea0](https://github.com/cristofima/maf-graphrag-series/commit/adfcea0))

---

## [2.0.0] - 2026-02-11

### Breaking

- **GraphRAG 3.0.x upgrade**: Major dependency update. ([cc0054b](https://github.com/cristofima/maf-graphrag-series/commit/cc0054b))
  - Python >=3.11,<3.13 (was >=3.10)
  - pandas 2.3.0, pyarrow 22.0.0
  - New configuration schema in `settings.yaml` (`completion_models`/`embedding_models`)
  - Updated prompts for v3.0.x compatibility

### Added

- **Part 2 MCP server module**: Model Context Protocol server. ([5cfb788](https://github.com/cristofima/maf-graphrag-series/commit/5cfb788))
  - `mcp_server/server.py` - FastMCP server with HTTP/SSE on port 8011
  - `mcp_server/tools/` - 5 MCP tools implementation
  - `mcp_server/tools/source_resolver.py` - Source traceability ([6e5b3a9](https://github.com/cristofima/maf-graphrag-series/commit/6e5b3a9))

- **MCP tools exposed via HTTP/SSE**:
  - `search_knowledge_graph` - Main entry point for queries
  - `local_search` - Entity-focused search
  - `global_search` - Community/thematic search
  - `list_entities` - List entities by type
  - `get_entity` - Get specific entity details

- **Testing and tooling**:
  - `notebooks/02_test_mcp_server.ipynb` - MCP tool testing notebook
  - `run_mcp_server.py` - Convenience script to start MCP server

- **Dependencies (Part 2 group)**:
  - `fastmcp 0.2.0` - Model Context Protocol server framework
  - `uvicorn[standard] ^0.40.0` - ASGI server for HTTP/SSE

- **Core Python module (replaces `src/`)**: Modern API for GraphRAG 3.0.x. ([998e3b9](https://github.com/cristofima/maf-graphrag-series/commit/998e3b9))
  - `core/config.py` - Configuration loading and validation
  - `core/data_loader.py` - Parquet file loading with `GraphData` dataclass
  - `core/search.py` - Async search functions (local, global, drift, basic)
  - `core/index.py` - CLI for indexing with async `build_index`
  - `core/example.py` - CLI for querying

- **Python CLI commands**:
  - `poetry run python -m core.index` - Build knowledge graph
  - `poetry run python -m core.example "Your question"` - Query CLI

- **Input document expansion**: Dataset expansion from 3 to 10 documents. ([c3da728](https://github.com/cristofima/maf-graphrag-series/commit/c3da728))
  - `project_beta.md` - Healthcare analytics project
  - `technical_architecture.md` - System architecture
  - `technology_stack.md` - Tech standards
  - `customers_partners.md` - Customer case studies
  - `engineering_processes.md` - Development methodology
  - `incidents_postmortems.md` - Incident history (5 postmortems)
  - `company_events_timeline.md` - Company milestones

- **Poetry dependency management**: Project dependency configuration and lock-file workflow. ([728f4b6](https://github.com/cristofima/maf-graphrag-series/commit/728f4b6))
  - `pyproject.toml` replaces `requirements.txt`
  - Lock file (`poetry.lock`) for reproducible builds
  - Dev/prod dependency separation

### Removed

- **`src/` folder**: Superseded by the `core/` module. ([998e3b9](https://github.com/cristofima/maf-graphrag-series/commit/998e3b9))
- **`run_query.ps1`**: Replaced by `poetry run python -m core.example`.
- **`run_index.ps1`**: Replaced by `poetry run python -m core.index`. ([41de572](https://github.com/cristofima/maf-graphrag-series/commit/41de572))

### Changed

- **Notebook 01**: GraphRAG 3.0.x API updates. ([5bf0482](https://github.com/cristofima/maf-graphrag-series/commit/5bf0482))
- **Documentation**: New CLI workflow and v3.0.x migration updates. ([203b470](https://github.com/cristofima/maf-graphrag-series/commit/203b470), [3e979d6](https://github.com/cristofima/maf-graphrag-series/commit/3e979d6))
- **Installation**: `poetry install` replacing `pip install -r requirements.txt`.

---

## [1.0.0] - 2026-02-03

### Added

- **GraphRAG indexing and query system**:
  - CLI scripts for building knowledge graphs from documents ([d4de575](https://github.com/cristofima/maf-graphrag-series/commit/d4de575))
  - PowerShell scripts (`run_index.ps1`, `run_query.ps1`) with UTF-8 encoding support and environment variable loading ([323ceae](https://github.com/cristofima/maf-graphrag-series/commit/323ceae))
  - Local search functionality for entity-focused queries
  - Global search functionality for thematic/organizational queries
  - Python modules: `indexer.py`, `local_search.py`, `global_search.py`

- **Azure infrastructure**:
  - Terraform configuration for Azure OpenAI, Storage Account, and state management ([cf7c996](https://github.com/cristofima/maf-graphrag-series/commit/cf7c996))
  - Multi-region deployment strategy
  - Backend state storage configuration with `backend.hcl`
  - Infrastructure bootstrap scripts

- **GraphRAG configuration**:
  - LLM and embeddings configuration in `settings.yaml` ([95badce](https://github.com/cristofima/maf-graphrag-series/commit/95badce), [4792409](https://github.com/cristofima/maf-graphrag-series/commit/4792409))
  - Custom prompt templates for entity extraction, community reporting, and search operations ([1397a81](https://github.com/cristofima/maf-graphrag-series/commit/1397a81))
  - Support for Azure OpenAI GPT-4o and text-embedding-3-small models

- **Sample documents**:
  - Interconnected markdown documents demonstrating knowledge graph relationships ([168fc66](https://github.com/cristofima/maf-graphrag-series/commit/168fc66))
  - Documents placed in `input/documents/` for indexing

- **Data exploration**:
  - Jupyter notebook `01_explore_graph.ipynb` for visualizing knowledge graph outputs ([cf80620](https://github.com/cristofima/maf-graphrag-series/commit/cf80620), [7cff002](https://github.com/cristofima/maf-graphrag-series/commit/7cff002))
  - Entity tables and relationship analysis capabilities

- **Documentation**:
  - Implementation notes for Part 1: GraphRAG Fundamentals ([1e62a26](https://github.com/cristofima/maf-graphrag-series/commit/1e62a26))
  - Query guide with examples for local and global searches ([d2a2c62](https://github.com/cristofima/maf-graphrag-series/commit/d2a2c62))
  - Azure deployment lessons learned documentation ([74bc102](https://github.com/cristofima/maf-graphrag-series/commit/74bc102))
  - Comprehensive README with project structure and usage instructions ([96608f8](https://github.com/cristofima/maf-graphrag-series/commit/96608f8))

- **Project structure**:
  - Initial project scaffolding with organized folder structure ([bee9c20](https://github.com/cristofima/maf-graphrag-series/commit/bee9c20))
  - Separation of concerns: `src/`, `infra/`, `prompts/`, `input/`, `output/`, `docs/`, `notebooks/`
  - Requirements file with GraphRAG v1.2.0 dependencies

### Changed

- **LICENSE**: Copyright holder update. ([d3ab331](https://github.com/cristofima/maf-graphrag-series/commit/d3ab331))
