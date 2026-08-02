"""
Sequential Workflow - Research Pipeline

Implements a 3-step sequential workflow where each agent's output becomes
the context for the next agent. This pattern is ideal for complex questions
that benefit from structured decomposition before searching.

Pipeline:
    1. QueryAnalyzer   → Decomposes the query into a structured research plan
    2. KnowledgeSearcher → Executes searches via MCP based on the plan
    3. ReportWriter    → Synthesizes findings into a well-structured report

Usage:
    from workflows.sequential import ResearchPipelineWorkflow

    async with ResearchPipelineWorkflow() as workflow:
        result = await workflow.run("What are the leadership and technology strategy of Project Alpha?")
        print(result.answer)
        print(result.step_summary())

When to Use This Pattern:
    - Complex, multi-part questions that need upfront decomposition
    - When you want clear traceability through each reasoning step
    - When you need a structured report rather than a conversational reply
    - Research-style queries that blend entity facts with thematic context

Contrast with Single-Agent (Part 3):
    | Aspect          | Part 3 (Single Agent)    | Part 4 Sequential          |
    |-----------------|--------------------------|----------------------------|
    | Steps           | 1 (direct Q&A)           | 3 (analyze → search → write)|
    | Traceability    | Black box                | Full step log              |
    | Output format   | Conversational           | Structured report          |
    | Best for        | Quick questions          | Complex research queries   |
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from agent_framework import WorkflowBuilder, WorkflowContext, handler

from agents.supervisor import create_azure_client
from workflows.base import (
    InstrumentedAgentExecutor,
    MCPWorkflowBase,
    StepTelemetry,
    WorkflowResult,
    WorkflowType,
    ensure_text,
)

_InstrumentedAgentExecutor = InstrumentedAgentExecutor

if TYPE_CHECKING:
    from agent_framework import Agent, MCPStreamableHTTPTool

logger = logging.getLogger(__name__)


def _summarize(text: str, limit: int = 80) -> str:
    """Return a compact summary of *text* capped to *limit* characters."""

    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: max(0, limit - 3)]}..."


@dataclass(slots=True)
class QueryAnalysisStage:
    """Structured payload handed from query analysis to the search executor."""

    query: str
    plan: str


@dataclass(slots=True)
class SearchAggregationStage:
    """Structured payload handed from search executor to the report writer."""

    query: str
    plan: str
    findings: str


class _QueryAnalyzerExecutor(_InstrumentedAgentExecutor):
    """Executor that produces a research plan from the original query."""

    def __init__(self, agent: "Agent", record_step: Callable[[StepTelemetry], None]) -> None:
        super().__init__(executor_id="QueryAnalyzer", display_name="QueryAnalyzer", record_step=record_step)
        self._agent = agent

    @handler
    async def process(self, query: str, ctx: WorkflowContext[QueryAnalysisStage]) -> None:
        prompt = f"Analyze this research question and produce a search plan:\n\n{query}"
        start = time.perf_counter()
        response = await self._agent.run(prompt)
        elapsed = time.perf_counter() - start
        plan_text = ensure_text(response)

        self._emit_step(
            input_summary=f"Decompose query: {_summarize(query)}",
            output=plan_text,
            elapsed=elapsed,
        )

        await ctx.send_message(QueryAnalysisStage(query=query, plan=plan_text))


class _KnowledgeSearchExecutor(_InstrumentedAgentExecutor):
    """Executor that executes MCP searches based on the research plan."""

    def __init__(self, agent: "Agent", record_step: Callable[[StepTelemetry], None]) -> None:
        super().__init__(executor_id="KnowledgeSearcher", display_name="KnowledgeSearcher", record_step=record_step)
        self._agent = agent

    @handler
    async def process(
        self,
        analysis: QueryAnalysisStage,
        ctx: WorkflowContext[SearchAggregationStage],
    ) -> None:
        prompt = (
            f"Original question: {analysis.query}\n\n"
            f"Research plan:\n{analysis.plan}\n\n"
            "Execute all relevant searches and return the raw findings."
        )
        start = time.perf_counter()
        response = await self._agent.run(prompt)
        elapsed = time.perf_counter() - start
        findings = ensure_text(response)

        tool_names = []
        for tool in getattr(self._agent, "tools", []):
            name = getattr(tool, "name", None)
            tool_names.append(name if isinstance(name, str) else tool.__class__.__name__)

        metadata: dict[str, Any] | None = None
        if tool_names:
            metadata = {"tools": tool_names}

        self._emit_step(
            input_summary="Execute MCP searches from research plan",
            output=findings,
            elapsed=elapsed,
            metadata=metadata,
        )

        await ctx.send_message(SearchAggregationStage(query=analysis.query, plan=analysis.plan, findings=findings))


class _ReportWriterExecutor(_InstrumentedAgentExecutor):
    """Executor that synthesizes the final report from collected findings."""

    def __init__(self, agent: "Agent", record_step: Callable[[StepTelemetry], None]) -> None:
        super().__init__(executor_id="ReportWriter", display_name="ReportWriter", record_step=record_step)
        self._agent = agent

    @handler
    async def process(self, payload: SearchAggregationStage, ctx: WorkflowContext[None, str]) -> None:
        prompt = (
            f"Original question: {payload.query}\n\n"
            f"Research plan:\n{payload.plan}\n\n"
            f"Raw search findings:\n{payload.findings}\n\n"
            "Write a well-structured report that answers the original question."
        )
        start = time.perf_counter()
        response = await self._agent.run(prompt)
        elapsed = time.perf_counter() - start
        report = ensure_text(response)

        self._emit_step(
            input_summary="Synthesize findings into structured report",
            output=report,
            elapsed=elapsed,
        )

        await ctx.yield_output(report)


# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

_QUERY_ANALYZER_PROMPT = """You are a Research Planner. Your job is to analyze a user's question and
produce a structured search plan for querying a knowledge graph about TechVenture Inc.

## Your Output Format

Return a concise JSON-like plan with these fields:
- **primary_question**: The core question to answer
- **search_type**: "local" (specific entities) or "global" (themes/patterns) or "both"
- **entities_of_interest**: List of specific entity names to focus on (people, projects, etc.)
- **sub_questions**: 1-3 specific sub-questions that together answer the main query

## Rules
- Be specific about entity names when the question mentions them
- Prefer "local" whenever the question mentions specific entities, projects, people, or technologies
- Only recommend "global" for very broad organizational/strategic overview questions
- Recommend "both" sparingly — only when the question clearly needs both entity details AND broad themes
- Keep sub-questions short and search-friendly

## Example Output
Primary question: What are the leadership and technology strategy of Project Alpha?
Search type: local
Entities of interest: Project Alpha, Dr. Emily Harrison
Sub-questions:
  1. Who leads Project Alpha and what is their role?
  2. What technologies are used in Project Alpha?
  3. What is the strategic goal of Project Alpha?"""


_KNOWLEDGE_SEARCHER_PROMPT = """You are a Knowledge Graph Searcher. You receive a research plan and
execute searches against the GraphRAG knowledge graph about TechVenture Inc.

## Available Tools
- **local_search**: Fast, entity-focused search. Use for questions about specific people, projects,
  teams, technologies, and their relationships. Preferred for most queries.
- **global_search**: Slow (map-reduce across all communities). Use ONLY for broad organizational
  overview questions that cannot be answered by local_search.

## Instructions
1. Read the research plan carefully
2. **Strongly prefer local_search** — it handles most questions well, including listing projects
   and tech stacks, finding relationships, and entity details
3. Only use global_search if the question explicitly asks for organizational-wide themes,
   strategic patterns, or cross-cutting insights that local_search cannot answer
4. **Never call global_search more than once** — it is expensive and slow
5. Combine sub-questions into a single well-crafted search query when possible,
   rather than making separate calls for each sub-question
6. Include specific entity names, relationships, and quotes from the knowledge graph

## Output Format
Return all search findings as structured text with clear sections per sub-question.
Label each section with the sub-question it answers."""


_REPORT_WRITER_PROMPT = """You are a Report Writer. You receive a user's original question,
a research plan, and raw search findings from a knowledge graph about TechVenture Inc.

## Instructions
1. Read the original question and research plan
2. Synthesize the raw findings into a clear, well-structured report
3. Organize information logically (not just copying search output)
4. Use markdown headings and bullet points for clarity
5. Include a brief Executive Summary at the top
6. Cite specific entities and relationships that support your conclusions

## Output Format
## Executive Summary
[2-3 sentence summary of the key findings]

## [Topic Section 1]
[Details...]

## [Topic Section 2]
[Details...]

## Key Takeaways
[Bullet list of the most important insights]"""


# ---------------------------------------------------------------------------
# Workflow Implementation
# ---------------------------------------------------------------------------


def _create_sequential_agents(
    mcp_tool: "MCPStreamableHTTPTool",
) -> tuple["Agent", "Agent", "Agent"]:
    """Create the three agents for the sequential pipeline.

    All three agents are created once and share the same MCP tool instance.
    Only the KnowledgeSearcher actually calls MCP tools; the others use
    their system prompts to reason over text.

    Returns:
        tuple: (query_analyzer, knowledge_searcher, report_writer)
    """
    from agent_framework import Agent

    client = create_azure_client()

    # Step 1: Analyzes query → returns structured research plan
    # No MCP tools needed — pure reasoning
    query_analyzer = Agent(
        client=client,
        name="query_analyzer",
        instructions=_QUERY_ANALYZER_PROMPT,
        tools=[],
    )

    # Step 2: Executes the research plan against the knowledge graph
    # Has MCP tools to call local_search, global_search, etc.
    knowledge_searcher = Agent(
        client=client,
        name="knowledge_searcher",
        instructions=_KNOWLEDGE_SEARCHER_PROMPT,
        tools=[mcp_tool],
    )

    # Step 3: Synthesizes findings into a structured report
    # No MCP tools needed — pure synthesis
    report_writer = Agent(
        client=client,
        name="report_writer",
        instructions=_REPORT_WRITER_PROMPT,
        tools=[],
    )

    return query_analyzer, knowledge_searcher, report_writer


class ResearchPipelineWorkflow(MCPWorkflowBase):
    """Three-step sequential research pipeline.

    Chains three specialized agents:
        1. QueryAnalyzer  - Decomposes complex queries into a search plan
        2. KnowledgeSearcher - Executes MCP search calls based on the plan
        3. ReportWriter   - Synthesizes findings into a structured report

    This pattern provides full traceability: every intermediate step is
    recorded in ``WorkflowResult.steps``.

    Example:
        async with ResearchPipelineWorkflow() as workflow:
            result = await workflow.run("What are the key projects and who leads them?")
            print(result.answer)
            print(result.step_summary())  # Shows all 3 steps with timing
    """

    def __init__(self, mcp_url: str | None = None):
        """Initialize the workflow.

        Args:
            mcp_url: Optional override for the MCP server URL.
        """
        super().__init__(mcp_url=mcp_url, workflow_type=WorkflowType.SEQUENTIAL)
        self._query_analyzer: Agent | None = None
        self._knowledge_searcher: Agent | None = None
        self._report_writer: Agent | None = None

    def _create_agents(self, mcp_tool: "MCPStreamableHTTPTool") -> None:
        """Create the three sequential pipeline agents."""
        self._query_analyzer, self._knowledge_searcher, self._report_writer = _create_sequential_agents(mcp_tool)
        self._initialize_workflow()

    def _initialize_workflow(self) -> None:
        """Construct the Agent Framework workflow graph with instrumentation."""

        assert self._query_analyzer is not None
        assert self._knowledge_searcher is not None
        assert self._report_writer is not None

        query_executor = _QueryAnalyzerExecutor(self._query_analyzer, self._record_step)
        search_executor = _KnowledgeSearchExecutor(self._knowledge_searcher, self._record_step)
        report_executor = _ReportWriterExecutor(self._report_writer, self._record_step)

        builder = WorkflowBuilder(start_executor=query_executor)
        builder.add_chain([query_executor, search_executor, report_executor])

        workflow = builder.build()
        self._set_workflow(workflow, [query_executor, search_executor, report_executor])

    async def run(self, query: str) -> WorkflowResult:
        """Execute the workflow graph and return structured telemetry."""

        workflow = self._workflow
        if workflow is None:
            if not all((self._query_analyzer, self._knowledge_searcher, self._report_writer)):
                raise RuntimeError("Workflow not connected. Use 'async with ResearchPipelineWorkflow()'")
            self._initialize_workflow()
            workflow = self._workflow
        if workflow is None:
            raise RuntimeError("Workflow graph initialization failed")

        normalized_query = self.prepare_run(query)
        logger.info("Executing sequential workflow via WorkflowBuilder graph")

        run_started = time.perf_counter()
        run_result = await workflow.run(normalized_query, include_status_events=True)
        total_elapsed = time.perf_counter() - run_started
        return self.build_workflow_result(
            normalized_query=normalized_query,
            run_result=run_result,
            total_elapsed=total_elapsed,
        )
