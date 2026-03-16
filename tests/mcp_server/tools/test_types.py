"""Unit tests for mcp_server/tools/types.py — input validation and error handling decorator."""

from mcp_server.tools.types import (
    MAX_ENTITY_NAME_LENGTH,
    MAX_LIMIT,
    MAX_QUERY_LENGTH,
    handle_tool_errors,
    validate_community_level,
    validate_entity_name,
    validate_limit,
    validate_query,
)


class TestValidateQuery:
    def test_empty_string_returns_error(self):
        result = validate_query("")
        assert result is not None
        assert "empty" in result["error"].lower()

    def test_whitespace_only_returns_error(self):
        result = validate_query("   ")
        assert result is not None
        assert "empty" in result["error"].lower()

    def test_valid_query_returns_none(self):
        assert validate_query("Who leads Project Alpha?") is None

    def test_single_character_query_is_valid(self):
        assert validate_query("A") is None

    def test_query_at_max_length_returns_none(self):
        assert validate_query("a" * MAX_QUERY_LENGTH) is None

    def test_query_exceeds_max_length_returns_error(self):
        result = validate_query("a" * (MAX_QUERY_LENGTH + 1))
        assert result is not None
        assert str(MAX_QUERY_LENGTH) in result["error"]

    def test_error_is_tool_error_typed_dict(self):
        result = validate_query("")
        assert "error" in result


class TestValidateCommunityLevel:
    def test_none_is_valid(self):
        assert validate_community_level(None) is None

    def test_zero_is_valid(self):
        assert validate_community_level(0) is None

    def test_two_is_valid(self):
        assert validate_community_level(2) is None

    def test_max_valid_level_four_is_valid(self):
        assert validate_community_level(4) is None

    def test_negative_one_returns_error(self):
        result = validate_community_level(-1)
        assert result is not None
        assert "community_level" in result["error"]

    def test_level_five_returns_error(self):
        result = validate_community_level(5)
        assert result is not None

    def test_large_value_returns_error(self):
        result = validate_community_level(99)
        assert result is not None


class TestValidateLimit:
    def test_one_is_valid(self):
        assert validate_limit(1) is None

    def test_max_limit_is_valid(self):
        assert validate_limit(MAX_LIMIT) is None

    def test_mid_range_is_valid(self):
        assert validate_limit(50) is None

    def test_zero_returns_error(self):
        result = validate_limit(0)
        assert result is not None
        assert str(MAX_LIMIT) in result["error"]

    def test_over_max_returns_error(self):
        result = validate_limit(MAX_LIMIT + 1)
        assert result is not None

    def test_negative_returns_error(self):
        result = validate_limit(-5)
        assert result is not None


class TestValidateEntityName:
    def test_none_is_valid(self):
        assert validate_entity_name(None) is None

    def test_short_name_is_valid(self):
        assert validate_entity_name("Dr. Emily") is None

    def test_name_at_max_length_is_valid(self):
        assert validate_entity_name("a" * MAX_ENTITY_NAME_LENGTH) is None

    def test_name_over_max_length_returns_error(self):
        result = validate_entity_name("a" * (MAX_ENTITY_NAME_LENGTH + 1))
        assert result is not None
        assert str(MAX_ENTITY_NAME_LENGTH) in result["error"]

    def test_empty_string_is_valid(self):
        # empty string is not over length limit — validation only checks length
        assert validate_entity_name("") is None


class TestHandleToolErrors:
    async def test_success_passthrough(self):
        @handle_tool_errors("Test")
        async def my_tool() -> dict:
            return {"answer": "ok"}

        result = await my_tool()
        assert result == {"answer": "ok"}

    async def test_file_not_found_returns_knowledge_graph_error(self):
        @handle_tool_errors("Test")
        async def my_tool() -> dict:
            raise FileNotFoundError("output/entities.parquet not found")

        result = await my_tool()
        assert "error" in result
        assert "Knowledge graph not found" in result["error"]

    async def test_file_not_found_includes_details(self):
        @handle_tool_errors("Test")
        async def my_tool() -> dict:
            raise FileNotFoundError("specific file missing")

        result = await my_tool()
        assert "details" in result
        assert "specific file missing" in result["details"]

    async def test_generic_exception_returns_tool_name_in_error(self):
        @handle_tool_errors("Local search")
        async def failing_tool() -> dict:
            raise ValueError("something went wrong")

        result = await failing_tool()
        assert "error" in result
        assert "Local search failed" in result["error"]

    async def test_generic_exception_includes_message(self):
        @handle_tool_errors("Global search")
        async def failing_tool() -> dict:
            raise RuntimeError("connection refused")

        result = await failing_tool()
        assert "connection refused" in result["error"]

    async def test_tool_receives_arguments_correctly(self):
        @handle_tool_errors("Test")
        async def my_tool(query: str, level: int = 2) -> dict:
            return {"q": query, "level": level}

        result = await my_tool("who is Emily?", level=1)
        assert result == {"q": "who is Emily?", "level": 1}
