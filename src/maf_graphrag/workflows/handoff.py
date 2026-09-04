"""Handoff workflow with WorkflowBuilder-driven telemetry traces."""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from agent_framework import WorkflowBuilder, WorkflowContext, handler

from maf_graphrag.agents.supervisor import create_azure_client
from maf_graphrag.core.classification_utils import normalize_confidence_score
from maf_graphrag.workflows.base import (
    InstrumentedAgentExecutor,
    MCPWorkflowBase,
    StepTelemetry,
    WorkflowResult,
    WorkflowType,
    collect_tool_names,
    ensure_text,
)

if TYPE_CHECKING:
    from agent_framework import Agent, MCPStreamableHTTPTool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Routing Literals
# ---------------------------------------------------------------------------

RouteDecision = Literal["entity", "themes", "both"]

# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

_ROUTER_PROMPT = """You are a Query Router for a knowledge graph system about TechVenture Inc.

Your ONLY job is to classify an incoming query into one of three categories:
- **entity**: The question is about specific people, projects, teams, technologies, or their direct relationships.
  Examples: "Who leads Project Alpha?", "What does Alex Turner do?", "What team works on Project Beta?"
- **themes**: The question is about organizational patterns, strategic direction, or cross-cutting insights.
  Examples: "What are the main initiatives?", "Summarize the technology strategy", "What are the key trends?"
- **both**: The question requires both entity details AND organizational context.
  Examples: "What are the projects and who leads them?", "Describe the leadership and strategy of TechVenture"

## Output Format
Return ONLY compact JSON with this schema:
{
    "route": "entity" | "themes" | "both",
    "confidence_score": integer from 0 to 100,
    "reason": "short explanation (<=30 words)"
}
No markdown. No extra text outside the JSON object."""


_ENTITY_EXPERT_PROMPT = """You are the Entity Expert for TechVenture Inc's knowledge graph.
Your specialty is deep, accurate information about specific entities: people, projects, teams,
and technologies.

## Your Strengths
- Finding who leads what
- Mapping relationships between people and projects
- Identifying team compositions
- Tracking specific technologies used in specific projects

## CRITICAL RULES
- Call **local_search exactly once** — a single call with one comprehensive query.
- **Never call local_search more than once.** Combine all aspects into one query.

## Instructions
1. Craft one comprehensive query that covers all entity aspects of the user's question
2. Include the entity's name, role, key relationships, and relevant facts
3. If multiple related entities are mentioned, cover each one in your answer
4. Organize your answer by entity when multiple entities are involved

## Tone
Precise, factual, entity-focused. Reference specific names and relationships."""


_THEMES_EXPERT_PROMPT = """You are the Themes Expert for TechVenture Inc's knowledge graph.
Your specialty is revealing organizational patterns, strategic themes, and cross-cutting insights.

## Your Strengths
- Identifying strategic priorities across the organization
- Finding cross-team patterns and shared goals
- Summarizing technology adoption trends
- Describing organizational culture and direction

## Instructions
1. Call **global_search exactly once** with:
   - A well-crafted query covering the user's question
   - `response_type=\"Single Paragraph\"` (keep output concise)
2. Global search is **very slow** (map-reduce across all communities) — one call maximum.
3. **Never call global_search more than once** — consolidate everything into one query.
4. Identify recurring themes across multiple entities and communities
5. Connect individual observations to broader organizational trends
6. Highlight what the patterns mean strategically

## Tone
Analytical, strategic, pattern-focused. Connect dots across the organization."""


# ---------------------------------------------------------------------------
# Workflow Implementation
# ---------------------------------------------------------------------------


def _create_router_and_experts(
    mcp_tool: "MCPStreamableHTTPTool",
) -> tuple["Agent", "Agent", "Agent"]:
    """Create the Router agent and specialist agents.

    The Router needs no MCP tools (pure classification). Both experts
    share the same MCP tool instance since only one runs at a time.

    Returns:
        tuple: (router, entity_expert, themes_expert)
    """
    from agent_framework import Agent

    client = create_azure_client()

    router = Agent(
        client=client,
        name="router",
        instructions=_ROUTER_PROMPT,
        tools=[],
    )

    entity_expert = Agent(
        client=client,
        name="entity_expert",
        instructions=_ENTITY_EXPERT_PROMPT,
        tools=[mcp_tool],
    )

    themes_expert = Agent(
        client=client,
        name="themes_expert",
        instructions=_THEMES_EXPERT_PROMPT,
        tools=[mcp_tool],
    )

    return router, entity_expert, themes_expert


def _parse_route(router_output: str) -> RouteDecision:
    """Parse the router's single-word output into a routing decision.

    Falls back to "both" if the output is ambiguous, to ensure the question
    is answered even if routing is uncertain.

    Args:
        router_output: Raw text from the Router agent.

    Returns:
        RouteDecision: "entity", "themes", or "both".
    """
    cleaned = router_output.strip().lower().rstrip(".,;")
    if "entity" in cleaned and "themes" not in cleaned and "both" not in cleaned:
        return "entity"
    if "themes" in cleaned and "entity" not in cleaned and "both" not in cleaned:
        return "themes"
    # Default to "both" for safety when ambiguous
    return "both"


def _normalize_query_text(value: object) -> str:
    """Return a clean query string from WorkflowBuilder payload shapes."""

    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        for key in ("input", "query", "question", "text"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        return ensure_text(value)

    return ensure_text(value)


@dataclass(slots=True)
class RouteClassification:
    """Parsed handoff router output with optional confidence signals."""

    decision: RouteDecision
    confidence_score: int | None = None
    reason: str | None = None


def _parse_route_classification(router_output: str) -> RouteClassification:
    """Parse router output as JSON first, then fall back to legacy word parsing."""

    payload = router_output.strip()
    try:
        parsed = json.loads(payload)
    except Exception:
        return RouteClassification(decision=_parse_route(router_output))

    if not isinstance(parsed, dict):
        return RouteClassification(decision=_parse_route(router_output))

    route_value = parsed.get("route")
    decision = _parse_route(route_value if isinstance(route_value, str) else router_output)
    confidence_score = normalize_confidence_score(parsed.get("confidence_score"))
    if confidence_score is None:
        confidence_score = normalize_confidence_score(parsed.get("confidence"))
    raw_reason = parsed.get("reason")
    reason = raw_reason.strip() if isinstance(raw_reason, str) and raw_reason.strip() else None
    return RouteClassification(decision=decision, confidence_score=confidence_score, reason=reason)


@dataclass(slots=True)
class RouteDecisionStage:
    """Router output passed to specialist executors."""

    query: str
    decision: RouteDecision
    raw_output: str
    confidence_score: int | None = None
    reason: str | None = None


@dataclass(slots=True)
class ExpertFindingStage:
    """Payload emitted by specialists ahead of the composer."""

    query: str
    decision: RouteDecision
    expert_type: Literal["entity", "themes"]
    content: str
    ran: bool
    tool_names: tuple[str, ...] = ()


class _RouterExecutor(InstrumentedAgentExecutor):
    """Router agent executor that records decision telemetry."""

    def __init__(self, agent: "Agent", record_step: Callable[[StepTelemetry], None]) -> None:
        super().__init__(executor_id="Router", display_name="Router", record_step=record_step)
        self._agent = agent

    @handler
    async def process(self, query: object, ctx: WorkflowContext[RouteDecisionStage]) -> None:
        normalized_query = _normalize_query_text(query)
        prompt = f"Classify this query: {normalized_query}"
        start = time.perf_counter()
        response = await self._agent.run(prompt)
        elapsed = time.perf_counter() - start
        raw_output = ensure_text(response)
        classification = _parse_route_classification(raw_output)
        metadata: dict[str, object] = {"route": classification.decision}
        if classification.confidence_score is not None:
            metadata["route_confidence_score"] = classification.confidence_score
        if classification.reason:
            metadata["route_reason"] = classification.reason

        self._emit_step(
            input_summary=(
                f'Classify "{normalized_query[:60]}..."'
                if len(normalized_query) > 60
                else f'Classify "{normalized_query}"'
            ),
            output=f"Decision: {classification.decision} (raw: '{raw_output.strip()}')",
            elapsed=elapsed,
            metadata=metadata,
        )

        await ctx.send_message(
            RouteDecisionStage(
                query=normalized_query,
                decision=classification.decision,
                raw_output=raw_output,
                confidence_score=classification.confidence_score,
                reason=classification.reason,
            )
        )


class _EntityExpertExecutor(InstrumentedAgentExecutor):
    """Runs the entity specialist when routing requires it."""

    def __init__(self, agent: "Agent", record_step: Callable[[StepTelemetry], None]) -> None:
        super().__init__(executor_id="EntityExpert", display_name="EntityExpert", record_step=record_step)
        self._agent = agent

    @handler
    async def process(self, stage: RouteDecisionStage, ctx: WorkflowContext[ExpertFindingStage]) -> None:
        should_run = stage.decision in ("entity", "both")
        tool_names = collect_tool_names(self._agent)
        metadata: dict[str, Any]

        if should_run:
            start = time.perf_counter()
            response = await self._agent.run(stage.query)
            elapsed = time.perf_counter() - start
            content = ensure_text(response)
            metadata = {
                "handoff_from": "Router",
                "search_type": "local",
                "route": stage.decision,
                "tools": tool_names,
            }
        else:
            elapsed = 0.0
            content = f"Skipped because router selected '{stage.decision}'."
            metadata = {
                "handoff_from": "Router",
                "search_type": "local",
                "route": stage.decision,
                "skipped": True,
            }

        self._emit_step(
            input_summary="Entity specialist analysis",
            output=content,
            elapsed=elapsed,
            metadata=metadata,
        )

        await ctx.send_message(
            ExpertFindingStage(
                query=stage.query,
                decision=stage.decision,
                expert_type="entity",
                content=content,
                ran=should_run,
                tool_names=tuple(tool_names),
            )
        )


class _ThemesExpertExecutor(InstrumentedAgentExecutor):
    """Runs the themes specialist when routing requires it."""

    def __init__(self, agent: "Agent", record_step: Callable[[StepTelemetry], None]) -> None:
        super().__init__(executor_id="ThemesExpert", display_name="ThemesExpert", record_step=record_step)
        self._agent = agent

    @handler
    async def process(self, stage: RouteDecisionStage, ctx: WorkflowContext[ExpertFindingStage]) -> None:
        should_run = stage.decision in ("themes", "both")
        tool_names = collect_tool_names(self._agent)
        metadata: dict[str, Any]

        if should_run:
            start = time.perf_counter()
            response = await self._agent.run(stage.query)
            elapsed = time.perf_counter() - start
            content = ensure_text(response)
            metadata = {
                "handoff_from": "Router",
                "search_type": "global",
                "route": stage.decision,
                "tools": tool_names,
            }
        else:
            elapsed = 0.0
            content = f"Skipped because router selected '{stage.decision}'."
            metadata = {
                "handoff_from": "Router",
                "search_type": "global",
                "route": stage.decision,
                "skipped": True,
            }

        self._emit_step(
            input_summary="Themes specialist analysis",
            output=content,
            elapsed=elapsed,
            metadata=metadata,
        )

        await ctx.send_message(
            ExpertFindingStage(
                query=stage.query,
                decision=stage.decision,
                expert_type="themes",
                content=content,
                ran=should_run,
                tool_names=tuple(tool_names),
            )
        )


class _HandoffComposerExecutor(InstrumentedAgentExecutor):
    """Composes specialist outputs into the final answer."""

    def __init__(self, record_step: Callable[[StepTelemetry], None]) -> None:
        super().__init__(executor_id="HandoffComposer", display_name="AnswerComposer", record_step=record_step)

    @handler
    async def process(
        self, payloads: list[ExpertFindingStage], ctx: WorkflowContext[list[ExpertFindingStage], str]
    ) -> None:
        decision = payloads[0].decision if payloads else "both"
        entity_payload = next((p for p in payloads if p.expert_type == "entity"), None)
        themes_payload = next((p for p in payloads if p.expert_type == "themes"), None)

        final_answer = self._compose_answer(decision, entity_payload, themes_payload)
        elapsed = 0.0
        experts_ran = [payload.expert_type for payload in payloads if payload.ran]

        self._emit_step(
            input_summary="Assemble router-selected findings",
            output=final_answer,
            elapsed=elapsed,
            metadata={"decision": decision, "experts_ran": experts_ran},
        )

        await ctx.yield_output(final_answer)

    @staticmethod
    def _compose_answer(
        decision: RouteDecision,
        entity_payload: ExpertFindingStage | None,
        themes_payload: ExpertFindingStage | None,
    ) -> str:
        entity_content = (
            entity_payload.content
            if entity_payload and entity_payload.ran and entity_payload.content.strip()
            else "No entity findings."
        )
        themes_content = (
            themes_payload.content
            if themes_payload and themes_payload.ran and themes_payload.content.strip()
            else "No thematic findings."
        )

        if decision == "entity":
            return entity_content
        if decision == "themes":
            return themes_content
        return "## Entity Details\n\n" + entity_content + "\n\n## Organizational Themes\n\n" + themes_content


class ExpertHandoffWorkflow(MCPWorkflowBase):
    """Router-based expert handoff workflow.

    A dedicated Router agent examines each query and decides which
    specialist to invoke. The routing decision is logged as a step,
    making it auditable and extensible.

    Specialists:
        - EntityExpert: Uses ``local_search`` for entity-focused questions
        - ThemesExpert: Uses ``global_search`` for organizational questions

    When the Router returns "both", both specialists run sequentially and
    their outputs are concatenated into the final answer.

    Example:
        async with ExpertHandoffWorkflow() as workflow:
            result = await workflow.run("Who leads Project Alpha?")
            print(result.answer)
            print(result.step_summary())  # Shows router → expert steps
    """

    def __init__(self, mcp_url: str | None = None):
        """Initialize the workflow.

        Args:
            mcp_url: Optional override for the MCP server URL.
        """
        super().__init__(mcp_url=mcp_url, workflow_type=WorkflowType.HANDOFF)
        self._router: Agent | None = None
        self._entity_expert: Agent | None = None
        self._themes_expert: Agent | None = None

    def _create_agents(self, mcp_tool: "MCPStreamableHTTPTool") -> None:
        """Create the router and specialist agents."""
        self._router, self._entity_expert, self._themes_expert = _create_router_and_experts(mcp_tool)
        self._initialize_workflow()

    def _initialize_workflow(self) -> None:
        """Build the WorkflowBuilder graph with instrumented executors."""

        assert self._router is not None
        assert self._entity_expert is not None
        assert self._themes_expert is not None

        router_executor = _RouterExecutor(self._router, self._record_step)
        entity_executor = _EntityExpertExecutor(self._entity_expert, self._record_step)
        themes_executor = _ThemesExpertExecutor(self._themes_expert, self._record_step)
        composer_executor = _HandoffComposerExecutor(self._record_step)

        builder = WorkflowBuilder(
            name="handoff",
            start_executor=router_executor,
            output_from=[composer_executor],
            intermediate_output_from="all_other",
        )
        builder.add_fan_out_edges(router_executor, [entity_executor, themes_executor])
        builder.add_fan_in_edges([entity_executor, themes_executor], composer_executor)

        workflow = builder.build()
        self._set_workflow(
            workflow,
            [router_executor, entity_executor, themes_executor, composer_executor],
        )

    async def run(
        self,
        query: object,
        *,
        include_status_events: bool = True,
        **run_kwargs: Any,
    ) -> WorkflowResult:
        """Execute the WorkflowBuilder graph and return routed telemetry."""

        workflow = self._workflow
        if workflow is None:
            if not all((self._router, self._entity_expert, self._themes_expert)):
                raise RuntimeError("Workflow not connected. Use 'async with ExpertHandoffWorkflow()'")
            self._initialize_workflow()
            workflow = self._workflow
        if workflow is None:
            raise RuntimeError("Workflow graph initialization failed")

        normalized_query = self.prepare_run(_normalize_query_text(query))
        logger.info("Executing handoff workflow via WorkflowBuilder graph")

        run_started = time.perf_counter()
        run_result = await workflow.run(
            normalized_query,
            include_status_events=include_status_events,
            **run_kwargs,
        )
        total_elapsed = time.perf_counter() - run_started
        return self.build_workflow_result(
            normalized_query=normalized_query,
            run_result=run_result,
            total_elapsed=total_elapsed,
        )
