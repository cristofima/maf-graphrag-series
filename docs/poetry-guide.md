# Poetry Usage Guide

## Overview

This project uses **Poetry** for dependency management. Poetry provides reproducible builds, automatic conflict resolution, and clean separation between production and development dependencies.

---

## Installation

### Windows (PowerShell)

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

### Linux/macOS/WSL

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### Verify Installation

```bash
poetry --version
# Should output: Poetry (version 1.7.0+)
```

---

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/cristofima/maf-graphrag-series.git
cd maf-graphrag-series

# RECOMMENDED: Configure Poetry to create .venv inside project
poetry config virtualenvs.in-project true

# Install all dependencies (Poetry creates .venv automatically)
poetry install
```

**Note:** Poetry manages virtual environments automatically. You **don't need** to create `.venv` manually like with pip. The `virtualenvs.in-project` setting tells Poetry to create `.venv` in your project folder (instead of a central location), which is useful for IDE integration.

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your Azure OpenAI credentials
# AZURE_OPENAI_API_KEY=your-key
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
```

### 3. Run the Project

```bash
# Build knowledge graph
.\run_index.ps1

# Query the knowledge graph
.\run_query.ps1 -Method local -Query "Who leads Project Alpha?"
```

---

## Common Commands

### Managing Dependencies

```bash
# Install all dependencies
poetry install

# Install without dev dependencies (for production)
poetry install --without dev

# Add a new dependency
poetry add package-name

# Add a development dependency
poetry add --group dev package-name

# Update dependencies
poetry update

# Update specific package
poetry update graphrag

# Show installed packages
poetry show

# Show dependency tree
poetry show --tree
```

### Running Commands

```bash
# Activate Poetry shell (optional)
poetry shell

# Run command in Poetry environment without activating shell
poetry run python -m graphrag index
poetry run python script.py

# Run tests
poetry run pytest

# Run notebooks
poetry run jupyter notebook
```

### Environment Management

```bash
# Show Poetry configuration
poetry config --list

# RECOMMENDED: Create virtualenv inside project (for IDE integration)
poetry config virtualenvs.in-project true

# Show virtualenv path
poetry env info

# Show virtualenv path only
poetry env info --path

# List all Poetry-managed environments for this project
poetry env list

# Remove virtualenv (Poetry will recreate on next install)
poetry env remove python
```

**Where does Poetry store virtualenvs?**

| Setting | Location | When to Use |
|---------|----------|-------------|
| `virtualenvs.in-project = false` (default) | `%APPDATA%\pypoetry\virtualenvs\` (Windows)<br>`~/.cache/pypoetry/virtualenvs/` (Linux/Mac) | Multiple projects, shared environments |
| `virtualenvs.in-project = true` | `.venv/` inside project folder | Better IDE integration, per-project isolation |

**Recommendation:** Use `virtualenvs.in-project = true` for this project.

---

## Project Scripts

The PowerShell scripts (`run_index.ps1`, `run_query.ps1`) automatically detect Poetry and use it:

```powershell
# These scripts will:
# 1. Check if Poetry is installed
# 2. Use 'poetry run' if available
# 3. Fall back to .venv if Poetry not found
.\run_index.ps1
.\run_query.ps1 -Method local -Query "Your question"
```

---

## CI/CD Integration

### GitHub Actions

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install Poetry
        uses: snok/install-poetry@v1
        with:
          version: 1.7.0
          virtualenvs-create: true
          virtualenvs-in-project: true
      
      - name: Load cached venv
        uses: actions/cache@v3
        with:
          path: .venv
          key: venv-${{ runner.os }}-${{ hashFiles('**/poetry.lock') }}
      
      - name: Install dependencies
        run: poetry install
      
      - name: Run tests
        run: poetry run pytest
```

### Azure DevOps

```yaml
steps:
- task: UsePythonVersion@0
  inputs:
    versionSpec: '3.10'

- script: |
    curl -sSL https://install.python-poetry.org | python3 -
    echo "##vso[task.prependpath]$HOME/.local/bin"
  displayName: 'Install Poetry'

- script: poetry install
  displayName: 'Install dependencies'

- script: poetry run pytest
  displayName: 'Run tests'
```

---

## Docker Integration

### Dockerfile with Poetry

```dockerfile
FROM python:3.10-slim as builder

# Install Poetry
RUN pip install --no-cache-dir poetry==1.7.0

WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies (production only)
RUN poetry config virtualenvs.create false \
    && poetry install --without dev --no-interaction --no-ansi

# Copy application code
COPY . .

# Runtime stage
FROM python:3.10-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /app /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONUTF8=1

CMD ["python", "-m", "graphrag", "index"]
```

---

## Dependency Structure

### Current (Part 1)

```toml
[tool.poetry.dependencies]
python = "^3.10"
graphrag = "~1.2.0"
openai = "^1.40.0"
pandas = "^2.0.0"
pyarrow = "^15.0.0"
python-dotenv = "^1.0.0"
aiohttp = "^3.9.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
httpx = "^0.26.0"
jupyter = "^1.0.0"
networkx = "^3.0"
matplotlib = "^3.7.0"
```

### Future Parts

Dependencies will be added incrementally as each part is implemented:

- **Part 2**: MCP Server dependencies (`fastmcp`, `uvicorn`, etc.)
- **Part 3-5**: Azure AI services (`azure-search-documents`, etc.)
- **Part 6-8**: Production dependencies (`gunicorn`, `prometheus-client`, etc.)

**YAGNI Principle**: We only add dependencies when they're actually needed.

---

## Troubleshooting

### Poetry not found after installation

**Solution:**
```powershell
# Windows: Add to PATH
$env:Path += ";$env:APPDATA\Python\Scripts"

# Or restart terminal
```

### SSL certificate errors

**Solution:**
```bash
poetry config certificates.my-cert.cert /path/to/cert.pem
```

### Slow dependency resolution

**Solution:**
```bash
poetry config experimental.new-installer true
```

### Lock file conflicts (git merge)

**Solution:**
```bash
# Regenerate lock file
poetry lock --no-update
```

### Python version incompatibility with GraphRAG

**Problem:**
```
The current project's supported Python range (>=3.10,<4.0) is not compatible
with some of the required packages Python requirement:
  - graphrag requires Python <3.13,>=3.10
```

**Cause:** Using `python = "^3.10"` allows Python 3.13+, but GraphRAG requires Python < 3.13.

**Solution:**
```toml
[tool.poetry.dependencies]
python = ">=3.10,<3.13"  # Explicit range instead of ^3.10
```

### Dependency conflict with httpx

**Problem:**
```
Because graphrag (1.2.0) depends on httpx (>=0.28.1,<0.29.0)
and maf-graphrag-series depends on httpx (^0.26.0),
version solving failed.
```

**Cause:** GraphRAG 1.2.0 requires httpx >= 0.28.1, but project specified httpx ^0.26.0.

**Solution:**
```toml
[tool.poetry.group.dev.dependencies]
httpx = "^0.28.0"  # Update to compatible version
```

**Best Practice:** Always check dependency requirements:
```bash
# View dependency requirements
poetry show graphrag --tree

# Or check PyPI page
pip show graphrag
```

### "No file/folder found for package" error

**Problem:**
```
Error: The current project could not be installed: No file/folder found for package maf-graphrag-series
If you do not want to install the current project use --no-root.
```

**Cause:** Poetry assumes you're creating a distributable package (for PyPI) and looks for:
- A package structure like `maf_graphrag_series/` at project root
- Or a single module file `maf_graphrag_series.py`

This project has modules in folders like `core/`, `mcp_server/`, etc., which are not standard package layouts.

**Solution:**
```toml
[tool.poetry]
name = "maf-graphrag-series"
version = "1.0.0"
# ... other metadata ...
package-mode = false  # Disable packaging, only manage dependencies
```

**When to use `package-mode = false`:**
- Tutorial projects
- Script collections
- Application codebases (not libraries)
- When you only want dependency management

**When to keep package mode enabled (default):**
- Creating a library for PyPI
- Building a reusable Python package
- When you need `pip install .` support

### Poetry corrupted or metadata errors

**Problem:**
```
KeyboardInterrupt in importlib.metadata.version("cachecontrol")
OSError: [Errno 22] Invalid argument
```

**Cause:** Corrupted Poetry installation or conflicting global packages.

**Solution:**
```bash
# Uninstall and reinstall Poetry
pip uninstall poetry -y
pip install poetry --force-reinstall

# Clear Poetry cache
poetry cache clear --all pypi

# Recreate virtualenv
poetry env remove python
poetry install
```

---

## Why Poetry?

| Feature | pip + requirements.txt | Poetry |
|---------|----------------------|--------|
| **Lock file** | Manual (pip freeze) | Automatic (poetry.lock) |
| **Dev/prod separation** | Multiple files | Groups |
| **Conflict detection** | No | Yes |
| **Python version** | Not enforced | Enforced |
| **Build system** | setup.py | pyproject.toml (PEP 517/518) |
| **Reproducibility** | Limited | Guaranteed |

---

## Resources

- **Poetry Documentation:** https://python-poetry.org/docs/
- **PEP 517 (Build System):** https://peps.python.org/pep-0517/
- **PEP 518 (pyproject.toml):** https://peps.python.org/pep-0518/

---

**Author:** Cristopher Coronado
**Last Updated:** February 3, 2026
