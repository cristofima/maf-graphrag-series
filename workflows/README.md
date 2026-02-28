# Workflows Module — Part 4: Workflow Patterns

Multi-agent workflow patterns that extend the single-agent Knowledge Captain from Part 3.

## Architecture Overview

```
                         User Query
                              │
                ┌─────────────┼─────────────┐
                │             │             │
                ▼             ▼             ▼
         Sequential      Concurrent      Handoff
         Pipeline        Search          Router
                │             │             │
         Analyze         local + global   Router
         Search          (parallel)    classifies
         Write                │             │
                │         Synthesize   EntityExpert
                │             │         or
                ▼             ▼        ThemesExpert
             Result        Result        Result
```

## Workflow Patterns

### 1. Sequential Workflow (`sequential.py`) — Research Pipeline

**When to use**: Complex, multi-part questions that need structured decomposition before searching.

```
QueryAnalyzer → KnowledgeSearcher → ReportWriter
     │                │                  │
 Research plan    Raw findings    Final report
```

| Step         | Agent              | Role                                  |
|--------------|--------------------|---------------------------------------|
| 1            | QueryAnalyzer      | Decomposes query into a search plan   |
| 2            | KnowledgeSearcher  | Executes MCP searches from the plan   |
| 3            | ReportWriter       | Synthesizes into structured report    |

**Best for**:
- "What are the leadership, technology decisions, and strategic goals of Project Alpha?"
- Complex research questions that span multiple domains

### 2. Concurrent Workflow (`concurrent.py`) — Parallel Search

**When to use**: Questions that benefit from both entity details AND organizational themes simultaneously.

```
                    Query
                   /     \
          EntitySearcher  ThemesSearcher    ← asyncio.gather()
            (local_search)  (global_search)
                   \     /
               AnswerSynthesizer
```

| Step    | Agent             | Output                                  |
|---------|-------------------|-----------------------------------------|
| 1 (parallel) | EntitySearcher | Entity details via local_search    |
| 2 (parallel) | ThemesSearcher | Thematic patterns via global_search|
| 3       | AnswerSynthesizer | Merged comprehensive answer            |

**Best for**:
- "What are the main projects and who leads them?"
- Questions where entity-level and organizational-level perspectives complement each other

### 3. Handoff Workflow (`handoff.py`) — Expert Routing

**When to use**: When you want explicit, auditable routing to specialist agents.

```
Router (classifies) → EntityExpert  (entity questions)
                    → ThemesExpert  (themes questions)
                    → Both          (mixed questions)
```

| Route    | Agent         | Search type   | Example query                        |
|----------|---------------|---------------|--------------------------------------|
| entity   | EntityExpert  | local_search  | "Who leads Project Alpha?"           |
| themes   | ThemesExpert  | global_search | "What are the main initiatives?"     |
| both     | Both in turn  | both          | "Describe the projects and strategy" |

**Best for**:
- Demonstrating how routing becomes an explicit, logged step
- Systems with many specialist agents
- When routing logic must be auditable

## Choosing the Right Workflow

| Workflow    | Speed       | Traceability | Best Query Type          |
|-------------|-------------|--------------|--------------------------|
| Single Agent (Part 3) | Fast | Low   | Simple Q&A               |
| Sequential  | Slowest     | Highest      | Complex multi-part       |
| Concurrent  | Fastest     | Medium       | Dual-perspective         |
| Handoff     | Medium      | High         | Specialist-specific      |

## Quick Start

```bash
# Prerequisites
poetry run python run_mcp_server.py   # Terminal 1

# Run workflow demo CLI
poetry run python run_workflow.py     # Terminal 2

# Or try a specific workflow
poetry run python run_workflow.py sequential "What are the key projects?"
poetry run python run_workflow.py concurrent "Who leads Project Alpha and what are the main themes?"
poetry run python run_workflow.py handoff    "What are the main strategic initiatives?"
```

## Programmatic Usage

```python
from workflows import ResearchPipelineWorkflow, ParallelSearchWorkflow, ExpertHandoffWorkflow

# Sequential
async with ResearchPipelineWorkflow() as wf:
    result = await wf.run("What is the technology strategy for Project Alpha?")
    print(result.answer)
    print(result.step_summary())   # Step-by-step trace

# Concurrent
async with ParallelSearchWorkflow() as wf:
    result = await wf.run("Who leads the projects and what are the key themes?")
    print(result.answer)

# Handoff
async with ExpertHandoffWorkflow() as wf:
    result = await wf.run("Who leads Project Alpha?")
    print(result.answer)
```

## WorkflowResult

Every workflow returns a `WorkflowResult`:

```python
@dataclass
class WorkflowResult:
    answer: str                     # Final synthesized answer
    workflow_type: WorkflowType     # sequential | concurrent | handoff
    steps: list[WorkflowStep]       # All intermediate agent outputs
    total_elapsed_seconds: float    # Wall-clock time for entire workflow
    query: str                      # Original user query
```

Each `WorkflowStep` contains:

```python
@dataclass
class WorkflowStep:
    agent_name: str          # e.g. "QueryAnalyzer"
    input_summary: str       # Short description of the input
    output: str              # Agent's full output text
    elapsed_seconds: float   # Time for this step
    metadata: dict           # Optional extra info
```

## Module Structure

```
workflows/
├── __init__.py       # Public API exports
├── base.py           # WorkflowResult, WorkflowStep, WorkflowType
├── sequential.py     # ResearchPipelineWorkflow (3-step chain)
├── concurrent.py     # ParallelSearchWorkflow (asyncio.gather + synthesis)
├── handoff.py        # ExpertHandoffWorkflow (Router → specialist)
└── README.md         # This file
```
