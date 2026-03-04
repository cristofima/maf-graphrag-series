# Part 4 Implementation Notes: Workflow Patterns

## Overview

Part 4 introduces three multi-agent workflow patterns built on top of the single Knowledge Captain agent from Part 3. All workflows connect to the same GraphRAG MCP Server via `MCPStreamableHTTPTool` and share the same underlying `core/` search functions.

**Key Decision**: Workflow patterns are implemented by composing `Agent` objects directly rather than using `agent_framework_orchestrations` builder classes. This makes the patterns explicit, easy to understand, and not subject to beta API changes.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  run_workflow.py  (CLI entry point)                                  │
│  workflow_type = sequential | concurrent | handoff                   │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐  ┌─────────────────┐  ┌───────────────────┐
│  Sequential   │  │   Concurrent    │  │     Handoff       │
│  Pipeline     │  │    Search       │  │     Router        │
│               │  │                 │  │                   │
│ QueryAnalyzer │  │ EntitySearcher ─┤  │ Router            │
│       ↓       │  │    (parallel)   │  │    ├─ EntityExpert│
│ KnowledgeS.   │  │ ThemesSearcher ─┤  │    └─ ThemesExpert│
│       ↓       │  │      ↓          │  │                   │
│ ReportWriter  │  │  Synthesizer    │  │                   │
└───────┬───────┘  └────────┬────────┘  └─────────┬─────────┘
        │                   │                     │
        └───────────────────┴─────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  MCPStreamable │
                    │   HTTPTool     │
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │  MCP Server    │
                    │  (port 8011)   │
                    │  local_search  │
                    │  global_search │
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │  GraphRAG Core │
                    │  (LanceDB +    │
                    │   Parquet)     │
                    └────────────────┘
```

---

## Files Created

| File                                                  | Purpose                                               |
| ----------------------------------------------------- | ----------------------------------------------------- |
| [workflows/\_\_init\_\_.py](../workflows/__init__.py) | Public API re-exports                                 |
| [workflows/base.py](../workflows/base.py)             | `WorkflowResult`, `WorkflowStep`, `WorkflowType`      |
| [workflows/sequential.py](../workflows/sequential.py) | `ResearchPipelineWorkflow` — 3-step chain             |
| [workflows/concurrent.py](../workflows/concurrent.py) | `ParallelSearchWorkflow` — asyncio.gather + synthesis |
| [workflows/handoff.py](../workflows/handoff.py)       | `ExpertHandoffWorkflow` — Router → specialist         |
| [workflows/README.md](../workflows/README.md)         | Module documentation                                  |
| [run_workflow.py](../run_workflow.py)                 | Interactive CLI demo                                  |

---

## Pattern Details

### Pattern 1: Sequential Workflow (`sequential.py`)

**Concept**: Chain three agents where each output feeds the next as context.

```python
# Step 1: Pure reasoning — no MCP tools
query_analyzer = Agent(client=client, name="query_analyzer",
                       instructions=QUERY_ANALYZER_PROMPT, tools=[])

# Step 2: MCP search — uses MCP tools
knowledge_searcher = Agent(client=client, name="knowledge_searcher",
                           instructions=KNOWLEDGE_SEARCHER_PROMPT, tools=[mcp_tool])

# Step 3: Pure synthesis — no MCP tools
report_writer = Agent(client=client, name="report_writer",
                      instructions=REPORT_WRITER_PROMPT, tools=[])
```

**Data flow between agents**:

```python
# Step 1: Analyze → research plan (no MCP tools)
analysis_result = await query_analyzer.run(
    f"Analyze this research question and produce a search plan:\n\n{query}"
)
research_plan = analysis_result.text

# Step 2: Search with plan as context (uses MCP tools)
search_result = await knowledge_searcher.run(
    f"Original question: {query}\n\n"
    f"Research plan:\n{research_plan}\n\n"
    "Execute all relevant searches and return the raw findings."
)
raw_findings = search_result.text

# Step 3: Synthesize into report (no MCP tools)
report_result = await report_writer.run(
    f"Original question: {query}\n\n"
    f"Research plan:\n{research_plan}\n\n"
    f"Raw search findings:\n{raw_findings}\n\n"
    "Write a well-structured report that answers the original question."
)
final_report = report_result.text
```

**Why only KnowledgeSearcher has MCP tools**: Giving MCP tools to all agents is wasteful and confusing. Only the agent that actually needs to search gets the tool. The others only reason about text.

---

### Pattern 2: Concurrent Workflow (`concurrent.py`)

**Concept**: Run two searches in parallel using `asyncio.gather`, then combine with a synthesis agent.

```python
# Two SEPARATE MCPStreamableHTTPTool instances — one per parallel agent
# This avoids concurrent writes on a single HTTP session
entity_mcp_tool = create_mcp_tool(mcp_url)
themes_mcp_tool = create_mcp_tool(mcp_url)

# Parallel execution
entity_task = entity_searcher.run(entity_prompt)
themes_task = themes_searcher.run(themes_prompt)

entity_result, themes_result = await asyncio.gather(entity_task, themes_task)
```

**Why two MCP tool instances**: `asyncio.gather` runs both coroutines concurrently. If both used the same `MCPStreamableHTTPTool` connection object, concurrent writes to the same HTTP session could interleave or fail. Two instances ensure independent connections.

**Speed reality**: `local_search` takes ~5–15s (vector similarity + 1 LLM call), but `global_search` takes **60–140s** (map-reduce over all 32 community reports ≈ 32 LLM calls). The parallel benefit applies to the _overlap_ between the two searches:

```
Sequential (without concurrent):   │── local (10s) ──│── global (90s) ──│ = 100s
Concurrent (with asyncio.gather):   │── local (10s)  ──│                  = 90s
                                    │── global (90s) ──│
```

The wall-clock saving is real (~10s), but the total is still dominated by `global_search`. This makes concurrent the **slowest** of the three patterns in absolute terms, since sequential and handoff can avoid `global_search` entirely for entity-focused queries.

---

### Pattern 3: Handoff Workflow (`handoff.py`)

**Concept**: A Router agent classifies the query as `entity`, `themes`, or `both`, then the appropriate specialist handles it.

```python
# Step 1: Router (no MCP tools — pure text classification)
router = Agent(client=client, name="router",
               instructions=ROUTER_PROMPT, tools=[])

# The Router's system prompt constrains it to return a single word
route = await router.run(f"Classify this query: {query}")
decision = parse_route(route.text)  # "entity" | "themes" | "both"

# Step 2: Hand off to specialist
if decision in ("entity", "both"):
    answer = await entity_expert.run(query)
if decision in ("themes", "both"):
    answer = await themes_expert.run(query)
```

**Router output design**: The Router prompt explicitly asks for a single word (`entity`, `themes`, or `both`) with no punctuation. `_parse_route()` handles the rare case where the model adds extra text anyway.

**Why not just use the system prompt (Part 3 approach)**: In Part 3, GPT-4o decides which MCP tool to call implicitly via its system prompt — this is fast but not auditable. In Part 4, the routing decision is a logged step in `WorkflowResult.steps`, making it explicit and testable. You can inspect which queries were routed to which specialist.

---

## WorkflowResult Design

Every workflow returns:

```python
@dataclass
class WorkflowResult:
    answer: str                     # Final answer
    workflow_type: WorkflowType     # sequential | concurrent | handoff
    steps: list[WorkflowStep]       # Full trace of intermediate steps
    total_elapsed_seconds: float    # Wall-clock time
    query: str                      # Original question
```

The `steps` list is the key feature — it gives you a full trace:

```python
result = await workflow.run("Who leads Project Alpha?")

for step in result.steps:
    print(f"{step.agent_name} ({step.elapsed_seconds:.1f}s): {step.input_summary}")

# Output (handoff example):
# Router (0.8s): Classify: "Who leads Project Alpha?"
# EntityExpert (4.2s): Entity-focused search for specific facts
```

---

## Comparison: When to Use Which Pattern

| Scenario                                         | Recommended Pattern              | Speed           | Reason                                           |
| ------------------------------------------------ | -------------------------------- | --------------- | ------------------------------------------------ |
| "Who leads Project Alpha?"                       | Handoff (or Part 3 single agent) | Fast (~15s)     | Simple entity query → `local_search` only        |
| "What are the main strategic themes?"            | Handoff                          | Slow (~90s)     | Single expert with `global_search`               |
| "What are the projects and who leads them?"      | Concurrent                       | Slowest (~140s) | Both perspectives, but `global_search` dominates |
| "Comprehensive report on TechVenture technology" | Sequential                       | Medium (~80s)   | Prefers `local_search`; structured decomposition |
| Real-time chat                                   | Part 3 single agent              | Fastest (~10s)  | Lowest latency, single search call               |
| Research/report generation                       | Sequential                       | Medium (~80s)   | Structured output with full step trace           |

> **Performance note**: Any workflow that triggers `global_search` will take 60–140s due to
> map-reduce over all community reports (~32 LLM calls). `local_search` uses vector similarity
> with a single LLM call (~5–15s). Sequential and handoff are optimized to prefer `local_search`
> via prompt engineering, making them faster for entity-focused questions.

---

## Performance Optimizations

Several optimizations were applied to keep workflow execution practical:

1. **Prompt engineering (CRITICAL RULES)**: Each search agent's system prompt includes strict rules:
   - EntitySearcher/EntityExpert: "Call `local_search` exactly once — NEVER more than once"
   - ThemesSearcher/ThemesExpert: "Call `global_search` exactly once — very slow, one call is the maximum"
   - Without these, agents were calling search tools 2–5 times per step, multiplying latency.

2. **QueryAnalyzer prefers local_search**: The sequential workflow's planner prompt says "Prefer local whenever the question mentions specific entities" — this avoids triggering `global_search` unnecessarily.

3. **`settings.yaml` tuning**:
   - `global_search.map_max_parallel: 5` — limits concurrent LLM calls during map-reduce
   - `global_search.reduce_max_tokens: 2000` — shorter reduce phase
   - `global_search.max_data_tokens: 8000` — caps context window per map step
   - `local_search.max_data_tokens: 12000` — reduces "Reached token limit" truncation warnings

4. **Independent MCP cleanup** (`concurrent.py`): The `__aexit__` method closes each `MCPStreamableHTTPTool` independently with `try/except` to prevent one cleanup failure from cascading.

5. **Logging suppression**: `run_workflow.py` sets noisy loggers (`agent_framework`, `graphrag.query`, `asyncio`) to ERROR/CRITICAL level to suppress non-fatal warnings (cancel scope cleanup, token limit, JSON decode).

---

## What Was Deferred

| Feature                                   | Deferred To     | Reason                                                   |
| ----------------------------------------- | --------------- | -------------------------------------------------------- |
| `agent_framework_orchestrations` builders | Future refactor | Beta API; direct composition is more stable for tutorial |
| Checkpointing across workflow steps       | Part 8          | Production concern                                       |
| Parallel synthesis in sequential          | Part 8          | Optimization                                             |
| Human approval gates between steps        | Part 6          | Human-in-the-Loop pattern                                |
| Evaluating workflow quality               | Part 5          | Agent Evaluation pattern                                 |

---

## Dependencies

No new dependencies were added for Part 4. All workflow patterns use:

```toml
# Already in pyproject.toml from Part 3
agent-framework-core = "^1.0.0rc2"
agent-framework-orchestrations = "^1.0.0b260225"
```

Key imports:

- `from agents.supervisor import create_azure_client, create_mcp_tool` — shared factory functions
- `from agent_framework import Agent, MCPStreamableHTTPTool` (behind `TYPE_CHECKING` guard)
- `from workflows.base import WorkflowResult, WorkflowStep, WorkflowType`
- Standard `asyncio.gather` for concurrent execution
