# uv Usage Guide

This project uses uv for dependency management, lockfiles, and virtual environment execution.

## Install uv

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Linux/macOS

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify installation:

```bash
uv --version
```

## Project Setup

From the repository root:

```bash
# Sync runtime + dev dependencies and create .venv
uv sync --dev
```

Use commands through uv so the project environment is always used:

```bash
uv run python -m maf_graphrag.core.index
uv run python -m maf_graphrag.core.example "Who leads Project Alpha?"
uv run pytest
uv run python -m ruff check .
uv run python -m mypy src/maf_graphrag/core/ src/maf_graphrag/agents/ src/maf_graphrag/mcp_server/ src/maf_graphrag/workflows/
```

## Common Commands

| Task                           | Command                                                                                                                                                                      |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Install/update lockfile        | `uv lock`                                                                                                                                                                    |
| Sync environment with lockfile | `uv sync --dev`                                                                                                                                                              |
| Sync only production deps      | `uv sync --no-dev`                                                                                                                                                           |
| Run tests                      | `uv run pytest`                                                                                                                                                              |
| Run linter                     | `uv run python -m ruff check . --output-format github`                                                                                                                       |
| Run formatter check            | `uv run python -m ruff format src/ tests/ --check`                                                                                                                           |
| Run type check                 | `uv run python -m mypy src/maf_graphrag/core/ src/maf_graphrag/agents/ src/maf_graphrag/mcp_server/ src/maf_graphrag/workflows/ --ignore-missing-imports --no-error-summary` |

## CI Notes

The CI workflow uses uv with `uv.lock` as the source of truth:

- `uv sync --dev --frozen` for reproducible installs.
- `uv run ...` for lint, mypy, and tests.

## Migration Notes

If you still have an old Poetry environment locally:

```bash
# Optional cleanup of legacy lock file
rm poetry.lock
```

The canonical lockfile for this repository is `uv.lock`.
