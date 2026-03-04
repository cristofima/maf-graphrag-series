"""
Handoff Workflow - Expert Routing

A Router agent classifies the incoming query and hands off to the most
suitable specialist. Unlike Part 3's system-prompt routing (where GPT-4o
decides within a single agent), here the routing decision is a discrete,
logged step performed by a dedicated Router agent.

Pipeline:
    1. Router      → Classifies query as "entity", "themes", or "both"
    2a. EntityExpert  (if "entity") → in-depth entity analysis via local_search
    2b. ThemesExpert  (if "themes") → broad thematic analysis via global_search
    2c. Both experts  (if "both")   → run sequentially, then combine

Usage:
    from workflows.handoff import ExpertHandoffWorkflow

    async with ExpertHandoffWorkflow() as workflow:
        result = await workflow.run("Who leads Project Alpha?")
        # Routes to EntityExpert (entity question)

        result = await workflow.run("What are the main strategic initiatives?")
        # Routes to ThemesExpert (themes question)

When to Use This Pattern:
    - When you have multiple specialist agents with different capabilities
    - When routing logic should be explicit and auditable
    - When specialist agents have very different configurations/tools/prompts
    - When you want to add new specialists without changing existing ones

Contrast with Part 3 (Single Agent):
    | Aspect            | Part 3 Single Agent          | Part 4 Handoff               |
    |-------------------|------------------------------|------------------------------|
    | Routing           | Implicit via system prompt   | Explicit Router agent step   |
    | Specialist depth  | Generalist                   | Dedicated specialist prompts |
    | Traceability      | None (black box)             | Router decision is logged    |
    | Adding experts    | Change system prompt         | Add new specialist class     |

Why This Matters:
    In production multi-agent systems with many specialists (SQL, GraphRAG,
    web search, internal APIs), an explicit Router makes routing auditable
    and extensible without growing a monolithic system prompt.
"""

import logging
import time
from typing import TYPE_CHECKING, Literal

from agents.supervisor import create_azure_client, create_mcp_tool
from dotenv import load_dotenv

from workflows.base import WorkflowResult, WorkflowStep, WorkflowType

if TYPE_CHECKING:
    from agent_framework import Agent, MCPStreamableHTTPTool

load_dotenv()

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
Return ONLY a single word: entity, themes, or both.
No explanation. No punctuation. Just the category word."""


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


class ExpertHandoffWorkflow:
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
        self._mcp_url = mcp_url
        self._mcp_tool: MCPStreamableHTTPTool | None = None
        self._router: Agent | None = None
        self._entity_expert: Agent | None = None
        self._themes_expert: Agent | None = None

    async def __aenter__(self) -> "ExpertHandoffWorkflow":
        """Connect to MCP server and create agents."""
        self._mcp_tool = create_mcp_tool(self._mcp_url)
        await self._mcp_tool.__aenter__()

        self._router, self._entity_expert, self._themes_expert = (
            _create_router_and_experts(self._mcp_tool)
        )
        return self

    async def __aexit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        """Disconnect from MCP server."""
        if self._mcp_tool:
            await self._mcp_tool.__aexit__(exc_type, exc_val, exc_tb)

    async def run(self, query: str) -> WorkflowResult:
        """Route the query to the appropriate specialist and return the answer.

        Args:
            query: Any question about TechVenture Inc.

        Returns:
            WorkflowResult including the Router's decision and the expert's answer.

        Raises:
            RuntimeError: If the workflow has not been entered as a context manager.
        """
        if not self._mcp_tool:
            raise RuntimeError(
                "Workflow not connected. Use 'async with ExpertHandoffWorkflow()'"
            )
        assert self._router is not None
        assert self._entity_expert is not None
        assert self._themes_expert is not None

        steps: list[WorkflowStep] = []
        workflow_start = time.time()

        # ------------------------------------------------------------------
        # Step 1: Router classifies the query
        # ------------------------------------------------------------------
        logger.info("Step 1: Router — classifying query...")
        step1_start = time.time()
        route_result = await self._router.run(
            f"Classify this query: {query}"
        )
        step1_elapsed = time.time() - step1_start
        route_decision = _parse_route(route_result.text)
        logger.info("Step 1: Router decided '%s' (%.1fs)", route_decision, step1_elapsed)

        steps.append(WorkflowStep(
            agent_name="Router",
            input_summary=f'Classify: "{query[:60]}..."' if len(query) > 60 else f'Classify: "{query}"',
            output=f"Decision: {route_decision} (raw: '{route_result.text.strip()}')",
            elapsed_seconds=step1_elapsed,
            metadata={"route": route_decision},
        ))

        # ------------------------------------------------------------------
        # Step 2: Handoff to specialist(s)
        # ------------------------------------------------------------------
        final_answer_parts: list[str] = []

        if route_decision in ("entity", "both"):
            logger.info("Step 2: EntityExpert — local search...")
            step2_start = time.time()
            entity_result = await self._entity_expert.run(query)
            step2_elapsed = time.time() - step2_start
            final_answer_parts.append(entity_result.text)
            logger.info("Step 2: EntityExpert completed (%.1fs)", step2_elapsed)

            steps.append(WorkflowStep(
                agent_name="EntityExpert",
                input_summary="Entity-focused search for specific facts",
                output=entity_result.text,
                elapsed_seconds=step2_elapsed,
                metadata={"handoff_from": "Router", "search_type": "local"},
            ))

        if route_decision in ("themes", "both"):
            logger.info("Step %d: ThemesExpert — global search...", len(steps) + 1)
            step3_start = time.time()
            themes_result = await self._themes_expert.run(query)
            step3_elapsed = time.time() - step3_start
            final_answer_parts.append(themes_result.text)
            logger.info("Step %d: ThemesExpert completed (%.1fs)", len(steps) + 1, step3_elapsed)

            steps.append(WorkflowStep(
                agent_name="ThemesExpert",
                input_summary="Thematic search for organizational patterns",
                output=themes_result.text,
                elapsed_seconds=step3_elapsed,
                metadata={"handoff_from": "Router", "search_type": "global"},
            ))

        # Combine answers when both specialists ran
        if route_decision == "both" and len(final_answer_parts) == 2:
            final_answer = (
                "## Entity Details\n\n"
                + final_answer_parts[0]
                + "\n\n## Organizational Themes\n\n"
                + final_answer_parts[1]
            )
        else:
            final_answer = final_answer_parts[0] if final_answer_parts else "No results found."

        total_elapsed = time.time() - workflow_start

        return WorkflowResult(
            answer=final_answer,
            workflow_type=WorkflowType.HANDOFF,
            steps=steps,
            total_elapsed_seconds=total_elapsed,
            query=query,
        )
