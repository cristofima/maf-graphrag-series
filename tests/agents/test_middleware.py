"""Unit tests for agents/middleware.py — Three-layer middleware pipeline."""

from unittest.mock import AsyncMock, MagicMock, patch

from agents.middleware import (
    LoggingFunctionMiddleware,
    QueryRewritingChatMiddleware,
    SummarizationMiddleware,
    TimingAgentMiddleware,
    TokenCountingChatMiddleware,
)


class TestTimingAgentMiddleware:
    async def test_calls_next_and_logs(self):
        mw = TimingAgentMiddleware()
        context = MagicMock()
        call_next = AsyncMock()

        with patch("agents.middleware.logger") as mock_logger:
            await mw.process(context, call_next)

        call_next.assert_awaited_once()
        mock_logger.info.assert_called_once()
        log_msg = mock_logger.info.call_args[0][0]
        assert "Agent execution completed" in log_msg

    async def test_propagates_exception(self):
        mw = TimingAgentMiddleware()
        context = MagicMock()
        call_next = AsyncMock(side_effect=RuntimeError("boom"))

        try:
            await mw.process(context, call_next)
            raise AssertionError("Should have raised")
        except RuntimeError:
            pass


class TestTokenCountingChatMiddleware:
    def test_initial_counters_are_zero(self):
        mw = TokenCountingChatMiddleware()
        assert mw.input_tokens == 0
        assert mw.output_tokens == 0
        assert mw.total_tokens == 0

    async def test_counts_tokens_from_usage_details(self):
        mw = TokenCountingChatMiddleware()

        context = MagicMock()
        result = MagicMock()
        result.usage_details = {
            "input_token_count": 100,
            "output_token_count": 50,
            "total_token_count": 150,
        }
        context.result = result

        await mw.process(context, AsyncMock())

        assert mw.input_tokens == 100
        assert mw.output_tokens == 50
        assert mw.total_tokens == 150

    async def test_accumulates_across_calls(self):
        mw = TokenCountingChatMiddleware()
        call_next = AsyncMock()

        for _ in range(3):
            context = MagicMock()
            result = MagicMock()
            result.usage_details = {
                "input_token_count": 10,
                "output_token_count": 5,
                "total_token_count": 15,
            }
            context.result = result
            await mw.process(context, call_next)

        assert mw.total_tokens == 45

    async def test_handles_none_result(self):
        mw = TokenCountingChatMiddleware()
        context = MagicMock()
        context.result = None

        await mw.process(context, AsyncMock())

        assert mw.total_tokens == 0

    async def test_handles_none_usage_details(self):
        mw = TokenCountingChatMiddleware()
        context = MagicMock()
        context.result = MagicMock(usage_details=None)

        await mw.process(context, AsyncMock())

        assert mw.total_tokens == 0

    def test_reset_clears_counters(self):
        mw = TokenCountingChatMiddleware()
        mw._input_tokens = 100
        mw._output_tokens = 50
        mw._total_tokens = 150

        mw.reset()

        assert mw.input_tokens == 0
        assert mw.output_tokens == 0
        assert mw.total_tokens == 0


class TestLoggingFunctionMiddleware:
    async def test_logs_function_name_and_timing(self):
        mw = LoggingFunctionMiddleware()
        context = MagicMock()
        context.function.name = "local_search"
        context.arguments = {"query": "test"}
        call_next = AsyncMock()

        with patch("agents.middleware.logger") as mock_logger:
            await mw.process(context, call_next)

        call_next.assert_awaited_once()
        assert mock_logger.info.call_count == 2

        # First call: invoking
        first_msg = mock_logger.info.call_args_list[0][0]
        assert "local_search" in first_msg[1]

        # Second call: completed
        second_msg = mock_logger.info.call_args_list[1][0]
        assert "local_search" in second_msg[1]

    async def test_propagates_exception(self):
        mw = LoggingFunctionMiddleware()
        context = MagicMock()
        context.function.name = "failing_tool"
        context.arguments = {}
        call_next = AsyncMock(side_effect=ValueError("bad"))

        try:
            await mw.process(context, call_next)
            raise AssertionError("Should have raised")
        except ValueError:
            pass


class TestQueryRewritingChatMiddleware:
    def _make_msg(self, role: str, text: str) -> MagicMock:
        """Create a mock message with role and text."""
        msg = MagicMock()
        msg.role = role
        msg.text = text
        return msg

    async def test_no_rewriting_with_short_history(self):
        """Should not inject instruction when history is below threshold."""
        mw = QueryRewritingChatMiddleware(min_history_turns=2)
        context = MagicMock()
        context.messages = [
            self._make_msg("system", "You are helpful."),
            self._make_msg("user", "Tell me about them"),
        ]
        call_next = AsyncMock()

        await mw.process(context, call_next)

        call_next.assert_awaited_once()
        # Messages should not be modified (only 2, threshold is 2)
        assert len(context.messages) == 2

    async def test_injects_instruction_when_anaphora_detected(self):
        """Should inject rewriting instruction for pronouns in follow-up."""
        mw = QueryRewritingChatMiddleware(min_history_turns=2)
        context = MagicMock()
        context.messages = [
            self._make_msg("system", "You are helpful."),
            self._make_msg("user", "Who leads Project Alpha?"),
            self._make_msg("assistant", "Sarah Chen leads it."),
            self._make_msg("user", "What else does she work on?"),
        ]
        call_next = AsyncMock()

        await mw.process(context, call_next)

        call_next.assert_awaited_once()
        # Should have injected a system message before the last user message
        assert len(context.messages) == 5
        injected = context.messages[-2]
        assert injected.role == "system"

    async def test_no_injection_without_anaphora(self):
        """Should not inject instruction when no pronouns detected."""
        mw = QueryRewritingChatMiddleware(min_history_turns=2)
        context = MagicMock()
        context.messages = [
            self._make_msg("system", "You are helpful."),
            self._make_msg("user", "Who leads Project Alpha?"),
            self._make_msg("assistant", "Sarah Chen."),
            self._make_msg("user", "What is Project Beta?"),
        ]
        call_next = AsyncMock()

        await mw.process(context, call_next)

        call_next.assert_awaited_once()
        # No anaphora → no injection
        assert len(context.messages) == 4

    async def test_detects_various_pronouns(self):
        """Should detect multiple pronoun types."""
        mw = QueryRewritingChatMiddleware(min_history_turns=1)
        pronouns = ["he", "she", "they", "them", "it", "their", "his", "her"]

        for pronoun in pronouns:
            context = MagicMock()
            context.messages = [
                self._make_msg("system", "..."),
                self._make_msg("user", "first question"),
                self._make_msg("user", f"What about {pronoun}?"),
            ]
            call_next = AsyncMock()

            await mw.process(context, call_next)

            assert len(context.messages) == 4, f"Failed for pronoun: {pronoun}"

    async def test_detects_reference_words(self):
        """Should detect 'mentioned', 'earlier', 'previous', etc."""
        mw = QueryRewritingChatMiddleware(min_history_turns=1)
        context = MagicMock()
        context.messages = [
            self._make_msg("system", "..."),
            self._make_msg("user", "first"),
            self._make_msg("user", "Tell me more about the previously mentioned project"),
        ]
        call_next = AsyncMock()

        await mw.process(context, call_next)

        assert len(context.messages) == 4  # injected

    async def test_custom_min_history_turns(self):
        """Should respect custom min_history_turns threshold."""
        mw = QueryRewritingChatMiddleware(min_history_turns=5)
        context = MagicMock()
        context.messages = [
            self._make_msg("system", "..."),
            self._make_msg("user", "q1"),
            self._make_msg("assistant", "a1"),
            self._make_msg("user", "What about them?"),
        ]
        call_next = AsyncMock()

        await mw.process(context, call_next)

        # 4 messages < threshold of 5 → no injection
        assert len(context.messages) == 4

    async def test_preserves_original_message_order(self):
        """Injected message should be placed just before the last user message."""
        mw = QueryRewritingChatMiddleware(min_history_turns=2)
        context = MagicMock()
        msg_user_first = self._make_msg("user", "Who is Alice?")
        msg_assistant = self._make_msg("assistant", "Alice is a lead.")
        msg_user_last = self._make_msg("user", "What does she do?")
        context.messages = [
            self._make_msg("system", "..."),
            msg_user_first,
            msg_assistant,
            msg_user_last,
        ]
        call_next = AsyncMock()

        await mw.process(context, call_next)

        # Last message should still be the user's follow-up
        assert context.messages[-1] is msg_user_last
        # Second-to-last should be the injected system message
        assert context.messages[-2].role == "system"

    async def test_handles_empty_text(self):
        """Should not crash on messages with empty text."""
        mw = QueryRewritingChatMiddleware(min_history_turns=1)
        context = MagicMock()
        context.messages = [
            self._make_msg("system", "..."),
            self._make_msg("user", "first"),
            self._make_msg("user", ""),
        ]
        call_next = AsyncMock()

        await mw.process(context, call_next)

        call_next.assert_awaited_once()
        assert len(context.messages) == 3  # no injection on empty


class TestSummarizationMiddleware:
    def _make_mw(self, total_tokens: int = 0, threshold: int = 100) -> tuple:
        """Create a SummarizationMiddleware with a pre-configured token counter."""
        token_counter = TokenCountingChatMiddleware()
        token_counter._total_tokens = total_tokens
        mw = SummarizationMiddleware(token_counter=token_counter, token_threshold=threshold)
        return mw, token_counter

    async def test_no_compaction_below_threshold(self):
        mw, _ = self._make_mw(total_tokens=50, threshold=100)
        context = MagicMock()
        context.session = MagicMock()
        call_next = AsyncMock()

        await mw.process(context, call_next)

        call_next.assert_awaited_once()

    async def test_no_compaction_when_session_is_none(self):
        mw, _ = self._make_mw(total_tokens=200, threshold=100)
        context = MagicMock()
        context.session = None
        call_next = AsyncMock()

        await mw.process(context, call_next)

        call_next.assert_awaited_once()

    async def test_compaction_replaces_history(self):
        mw, token_counter = self._make_mw(total_tokens=200, threshold=100)

        # Build mock session state with messages
        msg1 = MagicMock(role="user", text="Hello")
        msg2 = MagicMock(role="assistant", text="Hi there")
        msg3 = MagicMock(role="user", text="Tell me about Alpha")

        session = MagicMock()
        session.state = {
            "default": {
                "messages": [msg1, msg2, msg3],
            },
        }
        context = MagicMock()
        context.session = session

        # Mock the agent's client
        mock_response = MagicMock()
        mock_response.text = "Summary of conversation"
        mock_client = AsyncMock()
        mock_client.get_chat_response.return_value = mock_response
        context.agent = MagicMock()
        context.agent.client = mock_client

        call_next = AsyncMock()

        await mw.process(context, call_next)

        call_next.assert_awaited_once()
        # History should be replaced with a single summary message
        messages = session.state["default"]["messages"]
        assert len(messages) == 1
        assert "[Summary]" in messages[0].text
        # Token counter should be reset
        assert token_counter.total_tokens == 0

    async def test_skips_compaction_with_too_few_messages(self):
        mw, token_counter = self._make_mw(total_tokens=200, threshold=100)

        msg1 = MagicMock(role="user", text="Hello")
        session = MagicMock()
        session.state = {
            "default": {
                "messages": [msg1],
            },
        }
        context = MagicMock()
        context.session = session
        call_next = AsyncMock()

        await mw.process(context, call_next)

        # Should NOT have compacted — only 1 message
        assert len(session.state["default"]["messages"]) == 1
        # Token counter should NOT be reset
        assert token_counter.total_tokens == 200

    async def test_handles_missing_client_gracefully(self):
        mw, token_counter = self._make_mw(total_tokens=200, threshold=100)

        msg1 = MagicMock(role="user", text="Hello")
        msg2 = MagicMock(role="assistant", text="Hi")
        msg3 = MagicMock(role="user", text="More")

        session = MagicMock()
        session.state = {
            "default": {
                "messages": [msg1, msg2, msg3],
            },
        }
        context = MagicMock()
        context.session = session
        context.agent = MagicMock(client=None, _client=None)
        del context.agent._client  # Ensure getattr returns None
        call_next = AsyncMock()

        with patch("agents.middleware.logger") as mock_logger:
            await mw.process(context, call_next)

        call_next.assert_awaited_once()
        # Should have logged a warning about missing client
        mock_logger.warning.assert_called_once()
