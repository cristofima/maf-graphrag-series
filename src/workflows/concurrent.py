"""Concurrent workflow pattern powered by WorkflowBuilder instrumentation."""

import logging
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Literal

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

from agents.supervisor import create_azure_client, create_mcp_tool
from workflows.base import (
    InstrumentedAgentExecutor,
    StepTelemetry,
    WorkflowGraphSupport,
    WorkflowResult,
    WorkflowType,
    collect_tool_names,
    ensure_text,
)

if TYPE_CHECKING:
    from agent_framework import Agent

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
    mcp_url: str | None = None,
) -> tuple["Agent", "Agent", "Agent"]:
    """Create the two parallel search agents and the synthesis agent.

    Each parallel agent gets its own MCP tool instance with a unique
    ``tool_name_prefix`` to avoid concurrent access issues on a single
    HTTP connection and prevent duplicate tool-name errors (rc5+).

    Returns:
        tuple: (entity_searcher, themes_searcher, answer_synthesizer)
    """
    from agent_framework import Agent

    client = create_azure_client()
    entity_mcp_tool = create_mcp_tool(mcp_url)
    entity_mcp_tool.tool_name_prefix = "entity"
    themes_mcp_tool = create_mcp_tool(mcp_url)
    themes_mcp_tool.tool_name_prefix = "themes"

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


@dataclass(slots=True)
class SearchResultStage:
    """Payload emitted by search executors before final synthesis."""

    query: str
    result_type: Literal["entity", "themes"]
    findings: str
    tool_names: tuple[str, ...] = ()


class _QueryBroadcastExecutor(Executor):
    """Entry executor that fans the query out to both searchers."""

    def __init__(self) -> None:
        super().__init__(id="query_broadcast")

    @handler
    async def process(self, query: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(query)


class _EntitySearchExecutor(InstrumentedAgentExecutor):
    """Executes local_search plan and streams telemetry."""

    def __init__(self, agent: "Agent", record_step: Callable[[StepTelemetry], None]) -> None:
        super().__init__(executor_id="EntitySearcher", display_name="EntitySearcher", record_step=record_step)
        self._agent = agent

    @handler
    async def process(self, query: str, ctx: WorkflowContext[SearchResultStage]) -> None:
        prompt = (
            f"Find specific entity details that answer this question:\n\n{query}\n\n"
            "Focus on people, projects, teams, and their direct relationships."
        )
        start = time.perf_counter()
        response = await self._agent.run(prompt)
        elapsed = time.perf_counter() - start
        findings = ensure_text(response)
        tool_names = collect_tool_names(self._agent)

        metadata = {"parallel": True, "search_type": "local"}
        if tool_names:
            metadata["tools"] = tool_names

        self._emit_step(
            input_summary=f'Entity search for "{query[:60]}..."' if len(query) > 60 else f'Entity search for "{query}"',
            output=findings,
            elapsed=elapsed,
            metadata=metadata,
        )

        await ctx.send_message(
            SearchResultStage(
                query=query,
                result_type="entity",
                findings=findings,
                tool_names=tuple(tool_names),
            )
        )


class _ThemesSearchExecutor(InstrumentedAgentExecutor):
    """Executes global_search plan and streams telemetry."""

    def __init__(self, agent: "Agent", record_step: Callable[[StepTelemetry], None]) -> None:
        super().__init__(executor_id="ThemesSearcher", display_name="ThemesSearcher", record_step=record_step)
        self._agent = agent

    @handler
    async def process(self, query: str, ctx: WorkflowContext[SearchResultStage]) -> None:
        prompt = (
            f"Find organizational themes and patterns related to this question:\n\n{query}\n\n"
            "Focus on strategic goals, cross-cutting initiatives, and structural patterns."
        )
        start = time.perf_counter()
        response = await self._agent.run(prompt)
        elapsed = time.perf_counter() - start
        findings = ensure_text(response)
        tool_names = collect_tool_names(self._agent)

        metadata = {"parallel": True, "search_type": "global"}
        if tool_names:
            metadata["tools"] = tool_names

        self._emit_step(
            input_summary=f'Themes search for "{query[:60]}..."' if len(query) > 60 else f'Themes search for "{query}"',
            output=findings,
            elapsed=elapsed,
            metadata=metadata,
        )

        await ctx.send_message(
            SearchResultStage(
                query=query,
                result_type="themes",
                findings=findings,
                tool_names=tuple(tool_names),
            )
        )


class _AnswerSynthesizerExecutor(InstrumentedAgentExecutor):
    """Combines search findings into the final report."""

    def __init__(self, agent: "Agent", record_step: Callable[[StepTelemetry], None]) -> None:
        super().__init__(executor_id="AnswerSynthesizer", display_name="AnswerSynthesizer", record_step=record_step)
        self._agent = agent

    @handler
    async def process(self, payloads: list[SearchResultStage], ctx: WorkflowContext[list[SearchResultStage], str]) -> None:
        entity_payload = next((p for p in payloads if p.result_type == "entity"), None)
        themes_payload = next((p for p in payloads if p.result_type == "themes"), None)

        query = (entity_payload or themes_payload).query if (entity_payload or themes_payload) else ""
        entity_findings = entity_payload.findings if entity_payload else "No entity findings."
        themes_findings = themes_payload.findings if themes_payload else "No thematic findings."

        prompt = (
            f"Original question: {query}\n\n"
            f"## Entity Details (from local search)\n{entity_findings}\n\n"
            f"## Organizational Themes (from global search)\n{themes_findings}\n\n"
            "Synthesize both perspectives into a single comprehensive answer."
        )

        start = time.perf_counter()
        response = await self._agent.run(prompt)
        elapsed = time.perf_counter() - start
        final_answer = ensure_text(response)

        sources = [payload.result_type for payload in payloads if payload.findings.strip()]
        tool_names = sorted({tool for payload in payloads for tool in payload.tool_names})
        metadata: dict[str, Any] = {"sources": sources}
        if tool_names:
            metadata["tools"] = tool_names

        self._emit_step(
            input_summary="Merge entity details with thematic patterns",
            output=final_answer,
            elapsed=elapsed,
            metadata=metadata,
        )

        await ctx.yield_output(final_answer)


class ParallelSearchWorkflow(WorkflowGraphSupport):
    """Concurrent workflow that surfaces DevUI-friendly telemetry."""

    def __init__(self, mcp_url: str | None = None) -> None:
        super().__init__(workflow_type=WorkflowType.CONCURRENT)
        self._mcp_url = mcp_url
        self._entity_searcher: Agent | None = None
        self._themes_searcher: Agent | None = None
        self._answer_synthesizer: Agent | None = None
        self._exit_stack: AsyncExitStack | None = None

    async def __aenter__(self) -> "ParallelSearchWorkflow":
        self._entity_searcher, self._themes_searcher, self._answer_synthesizer = _create_parallel_agents(self._mcp_url)

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.enter_async_context(self._entity_searcher)
        await self._exit_stack.enter_async_context(self._themes_searcher)
        await self._exit_stack.enter_async_context(self._answer_synthesizer)
        self._initialize_workflow()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if self._exit_stack:
            await self._exit_stack.aclose()

    def _initialize_workflow(self) -> None:
        assert self._entity_searcher is not None
        assert self._themes_searcher is not None
        assert self._answer_synthesizer is not None

        broadcast = _QueryBroadcastExecutor()
        entity_executor = _EntitySearchExecutor(self._entity_searcher, self._record_step)
        themes_executor = _ThemesSearchExecutor(self._themes_searcher, self._record_step)
        synth_executor = _AnswerSynthesizerExecutor(self._answer_synthesizer, self._record_step)

        builder = WorkflowBuilder(
            start_executor=broadcast,
            output_from=[synth_executor],
            intermediate_output_from="all_other",
        )
        builder.add_fan_out_edges(broadcast, [entity_executor, themes_executor])
        builder.add_fan_in_edges([entity_executor, themes_executor], synth_executor)

        workflow = builder.build()
        self._set_workflow(workflow, [broadcast, entity_executor, themes_executor, synth_executor])

    async def run(self, query: str) -> WorkflowResult:
        if self._workflow is None:
            if not all((self._entity_searcher, self._themes_searcher, self._answer_synthesizer)):
                raise RuntimeError("Workflow not connected. Use 'async with ParallelSearchWorkflow()'")
            self._initialize_workflow()

        normalized_query = self.prepare_run(query)
        logger.info("Executing concurrent workflow via WorkflowBuilder graph")

        run_started = time.perf_counter()
        run_result = await self._workflow.run(normalized_query, include_status_events=True)
        total_elapsed = time.perf_counter() - run_started
        return self.build_workflow_result(
            normalized_query=normalized_query,
            run_result=run_result,
            total_elapsed=total_elapsed,
        )
