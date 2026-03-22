"""
Agent Middleware Pipeline.

Three-layer middleware for observability and context management:

- **AgentMiddleware** — wraps the entire agent execution (timing, summarization).
- **ChatMiddleware** — intercepts LLM calls (token counting, query rewriting).
- **FunctionMiddleware** — wraps tool invocations (logging, timing).

Usage::

    from agents.middleware import TimingAgentMiddleware, LoggingFunctionMiddleware, TokenCountingChatMiddleware

    agent = Agent(
        client=client,
        instructions="...",
        tools=[mcp_tool],
        middleware=[
            TimingAgentMiddleware(),
            LoggingFunctionMiddleware(),
            TokenCountingChatMiddleware(),
        ],
    )
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from agent_framework import AgentMiddleware, ChatMiddleware, FunctionMiddleware

if TYPE_CHECKING:
    from agent_framework import AgentContext, ChatContext, FunctionInvocationContext

logger = logging.getLogger(__name__)


class TimingAgentMiddleware(AgentMiddleware):
    """Track total agent execution time per run.

    Logs elapsed wall-clock time at INFO level after each ``agent.run()``
    completes. Useful for monitoring MCP round-trip and LLM latency.

    Example::

        agent = Agent(..., middleware=[TimingAgentMiddleware()])
        async with agent:
            result = await agent.run("query")
            # INFO  agents.middleware - Agent execution completed in 2.34s
    """

    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Measure and log agent execution time."""
        start = time.perf_counter()
        await call_next()
        elapsed = time.perf_counter() - start
        logger.info("Agent execution completed in %.2fs", elapsed)


class TokenCountingChatMiddleware(ChatMiddleware):
    """Track cumulative token usage across LLM calls.

    After each LLM request, reads ``usage_details`` from the chat response
    and accumulates input/output/total counts. Access counters via the
    ``input_tokens``, ``output_tokens``, and ``total_tokens`` properties.

    Example::

        token_mw = TokenCountingChatMiddleware()
        agent = Agent(..., middleware=[token_mw])
        async with agent:
            await agent.run("query")
            print(f"Total tokens: {token_mw.total_tokens}")
    """

    def __init__(self) -> None:
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._total_tokens: int = 0

    @property
    def input_tokens(self) -> int:
        """Cumulative input tokens across all LLM calls."""
        return self._input_tokens

    @property
    def output_tokens(self) -> int:
        """Cumulative output tokens across all LLM calls."""
        return self._output_tokens

    @property
    def total_tokens(self) -> int:
        """Cumulative total tokens across all LLM calls."""
        return self._total_tokens

    def reset(self) -> None:
        """Reset all counters to zero."""
        self._input_tokens = 0
        self._output_tokens = 0
        self._total_tokens = 0

    async def process(
        self,
        context: ChatContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Count tokens from each LLM response."""
        await call_next()

        result = context.result
        if result is None:
            return

        usage = getattr(result, "usage_details", None)
        if usage is None:
            return

        self._input_tokens += usage.get("input_token_count", 0) or 0
        self._output_tokens += usage.get("output_token_count", 0) or 0
        self._total_tokens += usage.get("total_token_count", 0) or 0
        logger.debug(
            "LLM call tokens — input: %d, output: %d, total: %d",
            usage.get("input_token_count", 0) or 0,
            usage.get("output_token_count", 0) or 0,
            usage.get("total_token_count", 0) or 0,
        )


class LoggingFunctionMiddleware(FunctionMiddleware):
    """Log tool invocations with timing.

    Emits an INFO log before and after each tool (MCP or local) call,
    including function name, arguments, and elapsed time.

    Example::

        agent = Agent(..., middleware=[LoggingFunctionMiddleware()])
        async with agent:
            await agent.run("query")
            # INFO  agents.middleware - Invoking tool: local_search(query='...')
            # INFO  agents.middleware - Tool local_search completed in 1.23s
    """

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Log tool call name, arguments, and execution time."""
        func_name = context.function.name
        args = context.arguments
        logger.info("Invoking tool: %s(%s)", func_name, args)

        start = time.perf_counter()
        await call_next()
        elapsed = time.perf_counter() - start

        logger.info("Tool %s completed in %.2fs", func_name, elapsed)


class QueryRewritingChatMiddleware(ChatMiddleware):
    """Resolve anaphora in follow-up queries before they reach the LLM.

    When conversation history exists, this middleware inspects the latest
    user message for pronouns and ambiguous references (e.g. "tell me
    more about them", "what does she work on?"). If detected, it prepends
    a contextual instruction reminding the LLM to resolve references to
    full entity names before calling any tools.

    This is a lightweight, zero-extra-LLM-call approach. The LLM still
    performs the actual resolution — this middleware just ensures it
    receives an explicit nudge to do so.

    Args:
        min_history_turns: Minimum number of prior messages (excluding
            system) before rewriting kicks in. Defaults to 2.

    Example::

        agent = Agent(
            ...,
            middleware=[QueryRewritingChatMiddleware(), TokenCountingChatMiddleware()],
        )
    """

    # Patterns that suggest the message references earlier conversation
    _ANAPHORA_TOKENS: frozenset[str] = frozenset(
        {
            "he",
            "she",
            "they",
            "them",
            "it",
            "its",
            "their",
            "his",
            "her",
            "this",
            "that",
            "these",
            "those",
            "the same",
            "previous",
            "above",
            "said",
            "mentioned",
            "earlier",
            "more about",
        }
    )

    _REWRITE_INSTRUCTION: str = (
        "[CONTEXT] The user's latest message may reference entities from the conversation history. "
        "Before calling any tool, resolve all pronouns and references (he, she, they, it, this, "
        "that, etc.) to their full entity names. Use the full names in tool call arguments — "
        "never pass pronouns to search tools."
    )

    def __init__(self, min_history_turns: int = 2) -> None:
        self._min_history_turns = min_history_turns

    async def process(
        self,
        context: ChatContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Inject a rewriting instruction when anaphora is detected."""
        messages = context.messages
        if messages and len(messages) > self._min_history_turns:
            last_msg = messages[-1]
            last_text = getattr(last_msg, "text", "") or ""
            if self._needs_rewriting(last_text):
                from agent_framework import Message

                rewrite_msg = Message("system", text=self._REWRITE_INSTRUCTION)
                # Insert the instruction just before the last user message
                context.messages = [*messages[:-1], rewrite_msg, messages[-1]]
                logger.debug("QueryRewritingChatMiddleware: injected rewriting instruction")

        await call_next()

    def _needs_rewriting(self, text: str) -> bool:
        """Check whether *text* likely contains unresolved references."""
        lowered = text.lower()
        return any(token in lowered for token in self._ANAPHORA_TOKENS)


class SummarizationMiddleware(AgentMiddleware):
    """Compact conversation history when token usage exceeds a threshold.

    Tracks cumulative tokens across agent runs. When ``token_threshold`` is
    exceeded, replaces the session history with a single ``[Summary]`` message
    generated by the same LLM client, then resets the counter.

    Requires a ``TokenCountingChatMiddleware`` in the same middleware list
    to provide token counts (reads from it after each run).

    Args:
        token_counter: A ``TokenCountingChatMiddleware`` instance to read cumulative usage from.
        token_threshold: Trigger summarization when cumulative tokens exceed this value.

    Example::

        token_mw = TokenCountingChatMiddleware()
        summarization_mw = SummarizationMiddleware(token_counter=token_mw, token_threshold=8000)
        agent = Agent(..., middleware=[TimingAgentMiddleware(), token_mw, LoggingFunctionMiddleware(), summarization_mw])
    """

    # InMemoryHistoryProvider stores messages under this key
    _DEFAULT_SOURCE_ID: str = "default"

    def __init__(
        self,
        token_counter: TokenCountingChatMiddleware,
        token_threshold: int = 8000,
    ) -> None:
        self._token_counter = token_counter
        self._token_threshold = token_threshold
        self._last_seen_tokens: int = 0

    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Summarize history when token budget is exceeded, then proceed."""
        session = context.session
        if session is not None and self._token_counter.total_tokens > self._token_threshold:
            await self._compact_history(context)

        await call_next()

        # Update baseline after the run
        self._last_seen_tokens = self._token_counter.total_tokens

    async def _compact_history(self, context: AgentContext) -> None:
        """Replace session messages with a single summary."""
        from agent_framework import Message

        session = context.session
        if session is None:
            return

        state = getattr(session, "state", None)
        if not isinstance(state, dict):
            return

        source_state = state.get(self._DEFAULT_SOURCE_ID)
        if not isinstance(source_state, dict):
            return

        messages: list[object] = source_state.get("messages", [])
        if len(messages) <= 2:
            return

        # Build plain-text conversation log for summarization
        lines: list[str] = []
        for msg in messages:
            role = getattr(msg, "role", "unknown")
            text = getattr(msg, "text", "") or ""
            if text:
                lines.append(f"{role}: {text}")

        conversation_text = "\n".join(lines)

        # Use the agent's own client to summarize
        agent = context.agent
        client = getattr(agent, "client", None) or getattr(agent, "_client", None)
        if client is None:
            logger.warning("SummarizationMiddleware: no client available — skipping compaction")
            return

        summary_prompt = Message(
            "user",
            text=f"Summarize this conversation concisely, preserving key facts:\n\n{conversation_text}",
        )

        try:
            response = await client.get_chat_response(messages=[summary_prompt])
            summary_text = response.text if response else "Previous conversation summary unavailable."
        except Exception:
            logger.exception("SummarizationMiddleware: summarization call failed")
            summary_text = "Previous conversation summary unavailable."

        # Replace history with summary
        source_state["messages"] = [
            Message("assistant", text=f"[Summary]\n{summary_text}"),
        ]

        self._token_counter.reset()
        logger.info(
            "Conversation history compacted — replaced %d messages with summary",
            len(messages),
        )
