"""
Concurrent Workflow - Parallel Search

Runs local search and global search simultaneously using ``asyncio.gather``,
then passes both result sets to a synthesis agent for a comprehensive answer.

Pipeline:
                     ┌─────────────────────┐
                     │  User Query         │
                     └─────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                                 ▼
   ┌──────────────────┐             ┌──────────────────────┐
   │  EntitySearcher  │             │  ThemesSearcher      │
   │  (local_search)  │             │  (global_search)     │
   │  entity details  │             │  organizational view │
   └──────────┬───────┘             └──────────┬───────────┘
              │   asyncio.gather()              │
              └────────────────┬────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │  AnswerSynthesizer  │
                    │  Merges both views  │
                    └─────────────────────┘

Usage:
    from workflows.concurrent import ParallelSearchWorkflow

    async with ParallelSearchWorkflow() as workflow:
        result = await workflow.run("What are the main projects and who leads them?")
        print(result.answer)
        # result.steps[0] = EntitySearcher result
        # result.steps[1] = ThemesSearcher result
        # result.steps[2] = Synthesis result

When to Use This Pattern:
    - Questions that span both entity details AND organizational themes
    - When you need speed: parallel steps are faster than sequential
    - When a single search type does not give a complete picture
    - "What are X and who does Y?" style questions

Contrast with Sequential (Part 4):
    | Aspect          | Sequential               | Concurrent                  |
    |-----------------|--------------------------|-----------------------------|
    | Flow            | Step 1 → 2 → 3           | Steps 1+2 in parallel → 3  |
    | Speed           | Slower (waits for each)  | Faster (parallel I/O)       |
    | Use case        | Complex decomposed plan  | Dual-perspective synthesis  |
    | Steps           | 3 sequential             | 2 parallel + 1 synthesis   |
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from agents.supervisor import create_azure_client, create_mcp_tool
from workflows.base import WorkflowResult, WorkflowStep, WorkflowType

if TYPE_CHECKING:
    from agent_framework import Agent, MCPStreamableHTTPTool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

_ENTITY_SEARCHER_PROMPT = """You are an Entity Specialist for a knowledge graph about TechVenture Inc.
Your role is to find specific, detailed information about named entities: people, projects, teams,
technologies, and their direct relationships.

## CRITICAL RULES
- Call **local_search exactly once** — a single call with one comprehensive query.
- **Never call local_search more than once.** Combine all aspects into one query.
- Pass `response_type="Single Paragraph"` (your output is an intermediate step, not the final answer).

## Instructions
- Craft one broad query that covers ALL entity aspects the user is asking about
- Focus on names, roles, responsibilities, and direct relationships
- Return structured facts: "Entity X has role Y in Project Z"

## Output Format
Return entity findings as structured bullet points grouped by entity type."""


_THEMES_SEARCHER_PROMPT = """You are a Themes Specialist for a knowledge graph about TechVenture Inc.
Your role is to identify organizational patterns, strategic themes, and cross-cutting insights
that span multiple entities.

## Instructions
- Call **global_search exactly once** with:
  - A well-crafted query that covers the user's question
  - `response_type="Single Paragraph"` (your output is an intermediate step, not the final answer)
- Global search is **very slow** (map-reduce across all communities). One call is the maximum.
- **Never call global_search more than once** — consolidate everything into one query.
- Focus on strategic goals, team structures, technology trends, and initiatives
- Identify patterns that connect multiple entities or departments
- Return thematic insights that a single entity search wouldn't reveal

## Output Format
Return thematic findings as structured sections, one per major theme identified."""


_ANSWER_SYNTHESIZER_PROMPT = """You are an Answer Synthesizer. You receive both entity-level details
AND organizational-level themes about TechVenture Inc, then produce a single comprehensive answer.

## Instructions
1. Read both the entity details and the thematic findings
2. Identify where they complement each other
3. Build a unified answer that weaves together both perspectives
4. Do not simply concatenate — synthesize into a coherent narrative
5. Highlight connections between specific entities and broader themes

## Output Format
Provide a direct, well-structured answer in markdown.
Start with a one-paragraph summary, then organize supporting details clearly.
End with "Entity-Theme Connections" section that explicitly links both perspectives."""


# ---------------------------------------------------------------------------
# Workflow Implementation
# ---------------------------------------------------------------------------


def _create_parallel_agents(
    entity_mcp_tool: "MCPStreamableHTTPTool",
    themes_mcp_tool: "MCPStreamableHTTPTool",
) -> tuple["Agent", "Agent", "Agent"]:
    """Create the two parallel search agents and the synthesis agent.

    Each parallel agent gets its own MCP tool instance to avoid concurrent
    access issues on a single HTTP connection.

    Returns:
        tuple: (entity_searcher, themes_searcher, answer_synthesizer)
    """
    from agent_framework import Agent

    client = create_azure_client()

    entity_searcher = Agent(
        client=client,
        name="entity_searcher",
        instructions=_ENTITY_SEARCHER_PROMPT,
        tools=[entity_mcp_tool],
    )

    themes_searcher = Agent(
        client=client,
        name="themes_searcher",
        instructions=_THEMES_SEARCHER_PROMPT,
        tools=[themes_mcp_tool],
    )

    # Synthesis agent needs no MCP tools — pure reasoning over text
    answer_synthesizer = Agent(
        client=client,
        name="answer_synthesizer",
        instructions=_ANSWER_SYNTHESIZER_PROMPT,
        tools=[],
    )

    return entity_searcher, themes_searcher, answer_synthesizer


class ParallelSearchWorkflow:
    """Concurrent dual-search workflow with synthesis.

    Runs entity search and thematic search in parallel using
    ``asyncio.gather``, then combines both result sets with a synthesis agent.

    Two separate ``MCPStreamableHTTPTool`` connections are maintained — one
    per parallel agent — to ensure safe concurrent HTTP access.

    Example:
        async with ParallelSearchWorkflow() as workflow:
            result = await workflow.run("What are the main projects and who leads them?")
            print(result.answer)
            print(result.step_summary())  # Shows parallel steps + synthesis
    """

    def __init__(self, mcp_url: str | None = None):
        """Initialize the workflow.

        Args:
            mcp_url: Optional override for the MCP server URL.
        """
        self._mcp_url = mcp_url
        self._entity_mcp_tool: MCPStreamableHTTPTool | None = None
        self._themes_mcp_tool: MCPStreamableHTTPTool | None = None
        self._entity_searcher: Agent | None = None
        self._themes_searcher: Agent | None = None
        self._answer_synthesizer: Agent | None = None

    async def __aenter__(self) -> "ParallelSearchWorkflow":
        """Connect two MCP tool instances and create agents."""
        # Two separate connections — one per concurrent agent
        self._entity_mcp_tool = create_mcp_tool(self._mcp_url)
        self._themes_mcp_tool = create_mcp_tool(self._mcp_url)

        await self._entity_mcp_tool.__aenter__()
        await self._themes_mcp_tool.__aenter__()

        self._entity_searcher, self._themes_searcher, self._answer_synthesizer = _create_parallel_agents(
            self._entity_mcp_tool, self._themes_mcp_tool
        )
        return self

    async def __aexit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        """Disconnect both MCP tool instances.

        Each tool is closed independently so that a cancel-scope error
        on one connection does not prevent the other from cleaning up.
        """
        for tool in (self._entity_mcp_tool, self._themes_mcp_tool):
            if tool:
                try:
                    await tool.__aexit__(None, None, None)
                except Exception:
                    pass  # Cleanup errors are non-fatal; resources are GC'd

    async def run(self, query: str) -> WorkflowResult:
        """Run entity and thematic searches in parallel, then synthesize.

        Args:
            query: The question to answer using both search perspectives.

        Returns:
            WorkflowResult with merged answer and parallel step details.

        Raises:
            RuntimeError: If the workflow has not been entered as a context manager.
        """
        if not self._entity_mcp_tool:
            raise RuntimeError("Workflow not connected. Use 'async with ParallelSearchWorkflow()'")
        assert self._entity_searcher is not None
        assert self._themes_searcher is not None
        assert self._answer_synthesizer is not None

        steps: list[WorkflowStep] = []
        workflow_start = time.time()

        # ------------------------------------------------------------------
        # Steps 1+2 (parallel): Entity search AND thematic search
        # ------------------------------------------------------------------
        logger.info("Steps 1+2: EntitySearcher + ThemesSearcher running in parallel...")
        entity_prompt = (
            f"Find specific entity details that answer this question:\n\n{query}\n\n"
            "Focus on people, projects, teams, and their direct relationships."
        )
        themes_prompt = (
            f"Find organizational themes and patterns related to this question:\n\n{query}\n\n"
            "Focus on strategic goals, cross-cutting initiatives, and structural patterns."
        )

        parallel_start = time.time()
        entity_task = self._entity_searcher.run(entity_prompt)
        themes_task = self._themes_searcher.run(themes_prompt)

        entity_result, themes_result = await asyncio.gather(entity_task, themes_task)
        parallel_elapsed = time.time() - parallel_start

        entity_findings = entity_result.text
        themes_findings = themes_result.text
        logger.info("Steps 1+2: Parallel searches completed (%.1fs)", parallel_elapsed)

        # Record both parallel steps with the shared elapsed time
        steps.append(
            WorkflowStep(
                agent_name="EntitySearcher",
                input_summary=f'Entity search: "{query[:50]}..."' if len(query) > 50 else f'Entity search: "{query}"',
                output=entity_findings,
                elapsed_seconds=parallel_elapsed,
                metadata={"parallel": True, "search_type": "local"},
            )
        )
        steps.append(
            WorkflowStep(
                agent_name="ThemesSearcher",
                input_summary=f'Themes search: "{query[:50]}..."' if len(query) > 50 else f'Themes search: "{query}"',
                output=themes_findings,
                elapsed_seconds=parallel_elapsed,
                metadata={"parallel": True, "search_type": "global"},
            )
        )

        # ------------------------------------------------------------------
        # Step 3: Synthesize both perspectives into one answer
        # ------------------------------------------------------------------
        logger.info("Step 3: AnswerSynthesizer — merging perspectives...")
        step3_start = time.time()
        synthesis_prompt = (
            f"Original question: {query}\n\n"
            f"## Entity Details (from local search)\n{entity_findings}\n\n"
            f"## Organizational Themes (from global search)\n{themes_findings}\n\n"
            "Synthesize both perspectives into a single comprehensive answer."
        )
        synthesis_result = await self._answer_synthesizer.run(synthesis_prompt)
        step3_elapsed = time.time() - step3_start
        final_answer = synthesis_result.text
        logger.info("Step 3: AnswerSynthesizer completed (%.1fs)", step3_elapsed)

        steps.append(
            WorkflowStep(
                agent_name="AnswerSynthesizer",
                input_summary="Merge entity details + thematic patterns",
                output=final_answer,
                elapsed_seconds=step3_elapsed,
            )
        )

        total_elapsed = time.time() - workflow_start

        return WorkflowResult(
            answer=final_answer,
            workflow_type=WorkflowType.CONCURRENT,
            steps=steps,
            total_elapsed_seconds=total_elapsed,
            query=query,
        )
