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
from typing import TYPE_CHECKING

from agents.supervisor import create_azure_client, create_mcp_tool
from dotenv import load_dotenv

from workflows.base import WorkflowResult, WorkflowStep, WorkflowType

if TYPE_CHECKING:
    from agent_framework import Agent, MCPStreamableHTTPTool

load_dotenv()

logger = logging.getLogger(__name__)

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


class ResearchPipelineWorkflow:
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
        self._mcp_url = mcp_url
        self._mcp_tool: MCPStreamableHTTPTool | None = None
        self._query_analyzer: Agent | None = None
        self._knowledge_searcher: Agent | None = None
        self._report_writer: Agent | None = None

    async def __aenter__(self) -> "ResearchPipelineWorkflow":
        """Connect to MCP server and create agents."""
        self._mcp_tool = create_mcp_tool(self._mcp_url)
        await self._mcp_tool.__aenter__()

        self._query_analyzer, self._knowledge_searcher, self._report_writer = (
            _create_sequential_agents(self._mcp_tool)
        )
        return self

    async def __aexit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        """Disconnect from MCP server."""
        if self._mcp_tool:
            await self._mcp_tool.__aexit__(exc_type, exc_val, exc_tb)

    async def run(self, query: str) -> WorkflowResult:
        """Execute the full 3-step research pipeline.

        Args:
            query: The complex question to research.

        Returns:
            WorkflowResult with the final report and all intermediate steps.

        Raises:
            RuntimeError: If the workflow has not been entered as a context manager.
        """
        if not self._mcp_tool:
            raise RuntimeError(
                "Workflow not connected. Use 'async with ResearchPipelineWorkflow()'"
            )
        assert self._query_analyzer is not None
        assert self._knowledge_searcher is not None
        assert self._report_writer is not None

        steps: list[WorkflowStep] = []
        workflow_start = time.time()

        # ------------------------------------------------------------------
        # Step 1: Analyze the query → structured research plan
        # ------------------------------------------------------------------
        logger.info("Step 1/3: QueryAnalyzer — decomposing query...")
        step1_start = time.time()
        analysis_result = await self._query_analyzer.run(
            f"Analyze this research question and produce a search plan:\n\n{query}"
        )
        step1_elapsed = time.time() - step1_start
        research_plan = analysis_result.text
        logger.info("Step 1/3: QueryAnalyzer completed (%.1fs)", step1_elapsed)

        steps.append(WorkflowStep(
            agent_name="QueryAnalyzer",
            input_summary=f'Decompose: "{query[:60]}..."' if len(query) > 60 else f'Decompose: "{query}"',
            output=research_plan,
            elapsed_seconds=step1_elapsed,
        ))

        # ------------------------------------------------------------------
        # Step 2: Search the knowledge graph using the plan
        # ------------------------------------------------------------------
        logger.info("Step 2/3: KnowledgeSearcher — executing MCP searches...")
        step2_start = time.time()
        search_prompt = (
            f"Original question: {query}\n\n"
            f"Research plan:\n{research_plan}\n\n"
            "Execute all relevant searches and return the raw findings."
        )
        search_result = await self._knowledge_searcher.run(search_prompt)
        step2_elapsed = time.time() - step2_start
        raw_findings = search_result.text
        logger.info("Step 2/3: KnowledgeSearcher completed (%.1fs)", step2_elapsed)

        steps.append(WorkflowStep(
            agent_name="KnowledgeSearcher",
            input_summary="Execute MCP searches from research plan",
            output=raw_findings,
            elapsed_seconds=step2_elapsed,
        ))

        # ------------------------------------------------------------------
        # Step 3: Synthesize findings into a structured report
        # ------------------------------------------------------------------
        logger.info("Step 3/3: ReportWriter — synthesizing report...")
        step3_start = time.time()
        synthesis_prompt = (
            f"Original question: {query}\n\n"
            f"Research plan:\n{research_plan}\n\n"
            f"Raw search findings:\n{raw_findings}\n\n"
            "Write a well-structured report that answers the original question."
        )
        report_result = await self._report_writer.run(synthesis_prompt)
        step3_elapsed = time.time() - step3_start
        final_report = report_result.text
        logger.info("Step 3/3: ReportWriter completed (%.1fs)", step3_elapsed)

        steps.append(WorkflowStep(
            agent_name="ReportWriter",
            input_summary="Synthesize findings into structured report",
            output=final_report,
            elapsed_seconds=step3_elapsed,
        ))

        total_elapsed = time.time() - workflow_start

        return WorkflowResult(
            answer=final_report,
            workflow_type=WorkflowType.SEQUENTIAL,
            steps=steps,
            total_elapsed_seconds=total_elapsed,
            query=query,
        )
