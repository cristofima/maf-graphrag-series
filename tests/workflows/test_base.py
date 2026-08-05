"""Unit tests for workflows/base.py — WorkflowStep, WorkflowResult, WorkflowType."""

import pytest

from workflows.base import (
    MCPWorkflowBase,
    MCPWorkflowRunner,
    WorkflowGraphSupport,
    WorkflowResult,
    WorkflowStep,
    WorkflowType,
    build_workflow_blueprint,
    collect_tool_names,
    ensure_text,
)


class TestWorkflowStep:
    def test_default_values(self):
        step = WorkflowStep(
            agent_name="TestAgent",
            input_summary="test input",
            output="test output",
        )
        assert step.agent_name == "TestAgent"
        assert step.input_summary == "test input"
        assert step.output == "test output"
        assert step.elapsed_seconds == pytest.approx(0.0)
        assert step.metadata == {}

    def test_with_timing_and_metadata(self):
        step = WorkflowStep(
            agent_name="Searcher",
            input_summary="search query",
            output="results",
            elapsed_seconds=1.5,
            metadata={"search_type": "local"},
        )
        assert step.elapsed_seconds == pytest.approx(1.5)
        assert step.metadata["search_type"] == "local"

    def test_metadata_is_not_shared(self):
        """Each step should have an independent metadata dict."""
        step1 = WorkflowStep("A", "in", "out")
        step2 = WorkflowStep("B", "in", "out")
        step1.metadata["key"] = "value"
        assert "key" not in step2.metadata


class TestWorkflowResult:
    def test_basic_construction(self):
        result = WorkflowResult(
            answer="final answer",
            workflow_type=WorkflowType.SEQUENTIAL,
        )
        assert result.answer == "final answer"
        assert result.workflow_type == WorkflowType.SEQUENTIAL
        assert result.steps == []
        assert result.total_elapsed_seconds == pytest.approx(0.0)
        assert result.query == ""

    def test_with_steps(self):
        steps = [
            WorkflowStep("Agent1", "input1", "output1", elapsed_seconds=0.5),
            WorkflowStep("Agent2", "input2", "output2", elapsed_seconds=1.0),
        ]
        result = WorkflowResult(
            answer="answer",
            workflow_type=WorkflowType.CONCURRENT,
            steps=steps,
            total_elapsed_seconds=1.5,
            query="test query",
        )
        assert len(result.steps) == 2
        assert result.total_elapsed_seconds == pytest.approx(1.5)
        assert result.query == "test query"

    def test_step_summary_format(self):
        steps = [
            WorkflowStep("QueryAnalyzer", "Decompose query", "plan", elapsed_seconds=0.3),
            WorkflowStep("Searcher", "Execute search", "results", elapsed_seconds=0.7),
        ]
        result = WorkflowResult(
            answer="done",
            workflow_type=WorkflowType.SEQUENTIAL,
            steps=steps,
            total_elapsed_seconds=1.0,
        )
        summary = result.step_summary()
        assert "sequential" in summary
        assert "1.0s" in summary
        assert "QueryAnalyzer" in summary
        assert "Searcher" in summary
        assert "Step 1" in summary
        assert "Step 2" in summary

    def test_steps_list_not_shared(self):
        """Each WorkflowResult should have its own steps list."""
        r1 = WorkflowResult(answer="a", workflow_type=WorkflowType.HANDOFF)
        r2 = WorkflowResult(answer="b", workflow_type=WorkflowType.HANDOFF)
        r1.steps.append(WorkflowStep("X", "in", "out"))
        assert len(r2.steps) == 0


class TestWorkflowType:
    def test_values(self):
        assert WorkflowType.SEQUENTIAL == "sequential"
        assert WorkflowType.CONCURRENT == "concurrent"
        assert WorkflowType.HANDOFF == "handoff"

    def test_is_str_enum(self):
        assert isinstance(WorkflowType.SEQUENTIAL, str)


class _ToolWithName:
    name = "search_knowledge_graph"


class _ToolWithoutName:
    pass


class _ObjWithText:
    def __init__(self, text: str) -> None:
        self.text = text


class _ObjWithContent:
    def __init__(self, content: object) -> None:
        self.content = content


class _FakeWorkflow:
    def __init__(self) -> None:
        self._executors = ["A", "B"]

    def clone(self):
        return self

    def to_dict(self):
        return {"id": "wf-1"}

    def get_executors_list(self):
        return self._executors


class _FakeRunResult:
    def __init__(self, outputs: list[object], statuses: list[object]) -> None:
        self._outputs = outputs
        self._statuses = statuses

    def get_outputs(self):
        return self._outputs

    def status_timeline(self):
        return self._statuses


class _FakeStatus:
    def __init__(self, state: object) -> None:
        self.state = state


class _FakeState:
    def __init__(self, value: str) -> None:
        self.value = value


class TestBaseUtilities:
    def test_ensure_text_handles_content_and_text_shapes(self):
        assert ensure_text("plain") == "plain"
        assert ensure_text(_ObjWithContent("content-str")) == "content-str"
        assert ensure_text(_ObjWithContent([{"text": "chunk1"}, _ObjWithText("chunk2")])) == "chunk1\nchunk2"
        assert ensure_text(_ObjWithText("text-attr")) == "text-attr"

    def test_collect_tool_names_uses_name_or_class_name(self):
        agent = type("Agent", (), {"tools": [_ToolWithName(), _ToolWithoutName()]})

        names = collect_tool_names(agent)

        assert names == ["search_knowledge_graph", "_ToolWithoutName"]

    def test_build_workflow_blueprint_contains_expected_shape(self):
        blueprint = build_workflow_blueprint(
            WorkflowType.SEQUENTIAL,
            name="Sequential Workflow",
            description="pipeline",
        )

        assert blueprint["name"] == "Sequential Workflow"
        assert blueprint["description"] == "pipeline"
        assert blueprint["start_executor_id"] == "QueryAnalyzer"
        assert isinstance(blueprint["edge_groups"], list)
        assert "QueryAnalyzer" in blueprint["executors"]


class TestWorkflowGraphSupport:
    def test_prepare_run_resets_telemetry(self):
        support = WorkflowGraphSupport(workflow_type=WorkflowType.SEQUENTIAL)
        support._record_step(  # noqa: SLF001 - intentional white-box test
            telemetry=type(
                "Telemetry",
                (),
                {
                    "agent_name": "A",
                    "input_summary": "in",
                    "output": "out",
                    "elapsed_seconds": 0.1,
                    "metadata": {},
                },
            )()
        )

        normalized = support.prepare_run(" query ")

        assert normalized == " query "
        assert list(support.iter_step_telemetry()) == []

    def test_set_workflow_and_to_dict(self):
        support = WorkflowGraphSupport(workflow_type=WorkflowType.SEQUENTIAL)
        workflow = _FakeWorkflow()

        support._set_workflow(workflow)

        assert support.get_workflow() is workflow
        assert support.get_executors_list() == ["A", "B"]
        assert support.to_dict() == {"id": "wf-1"}

    def test_build_workflow_result_attaches_status(self):
        support = WorkflowGraphSupport(workflow_type=WorkflowType.SEQUENTIAL)
        support._record_step(  # noqa: SLF001 - intentional white-box test
            telemetry=type(
                "Telemetry",
                (),
                {
                    "agent_name": "Searcher",
                    "input_summary": "ask",
                    "output": "draft",
                    "elapsed_seconds": 0.2,
                    "metadata": {},
                },
            )()
        )

        result = support.build_workflow_result(
            normalized_query="q",
            run_result=_FakeRunResult(
                outputs=["final answer"],
                statuses=[_FakeStatus(_FakeState("started")), _FakeStatus("completed")],
            ),
            total_elapsed=0.4,
        )

        assert result.answer == "final answer"
        assert result.workflow_type == WorkflowType.SEQUENTIAL
        assert result.steps[-1].metadata["status"] == ["started", "completed"]


class _FakeEventStream:
    def __init__(self, events: list[object], final_result: WorkflowResult) -> None:
        self._events = list(events)
        self._final_result = final_result

    def __aiter__(self):
        self._iter = iter(self._events)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def get_final_response(self) -> WorkflowResult:
        return self._final_result


class _FakeWorkflowForRunner:
    def prepare_run(self, query: str) -> str:
        return query.strip()

    def create_stream(self, normalized_query: str, include_status_events: bool = True, **run_kwargs):
        del run_kwargs
        final = WorkflowResult(
            answer=f"answer:{normalized_query}",
            workflow_type=WorkflowType.SEQUENTIAL,
            steps=[WorkflowStep("A", normalized_query, "done")],
            total_elapsed_seconds=0.1,
            query=normalized_query,
        )
        stream = _FakeEventStream(
            events=[{"event": "progress", "include_status_events": include_status_events}],
            final_result=final,
        )

        async def finalize() -> WorkflowResult:
            return await stream.get_final_response()

        return stream, finalize

    async def run(self, message: str, include_status_events: bool = True, **run_kwargs) -> WorkflowResult:
        del include_status_events, run_kwargs
        return WorkflowResult(
            answer=f"structured:{message}",
            workflow_type=WorkflowType.SEQUENTIAL,
            steps=[],
            total_elapsed_seconds=0.1,
            query=message,
        )


class _FakeWorkflowContext:
    async def __aenter__(self):
        return _FakeWorkflowForRunner()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class _MinimalMCPWorkflow(MCPWorkflowBase):
    def __init__(self) -> None:
        super().__init__(mcp_url=None, workflow_type=WorkflowType.SEQUENTIAL)
        self._set_workflow(_FakeWorkflow())

    def _create_agents(self, mcp_tool):
        del mcp_tool


class TestMCPWorkflowRunner:
    @pytest.mark.asyncio
    async def test_run_streaming_mode_and_final_response(self):
        runner = MCPWorkflowRunner(
            lambda _mcp_url: _FakeWorkflowContext(),
            workflow_type=WorkflowType.SEQUENTIAL,
            name="Seq",
        )

        stream = runner.run("  hello  ", stream=True)
        events = []
        async for event in stream:
            events.append(event)

        result = await stream.get_final_response()
        structured = stream.get_structured_result()

        assert len(events) >= 1
        assert result.answer == "answer:hello"
        assert structured.answer == "answer:hello"

    @pytest.mark.asyncio
    async def test_run_structured_returns_task(self):
        runner = MCPWorkflowRunner(
            lambda _mcp_url: _FakeWorkflowContext(),
            workflow_type=WorkflowType.SEQUENTIAL,
        )

        task = runner.run_structured("query")
        result = await task

        assert result.answer == "structured:query"

    def test_to_dict_router_uses_static_blueprint(self):
        runner = MCPWorkflowRunner(
            lambda _mcp_url: _FakeWorkflowContext(),
            workflow_type=WorkflowType.ROUTER,
            name="Router",
            description="router-flow",
        )

        first = runner.to_dict()
        second = runner.to_dict()

        assert first["name"] == "Router"
        assert first["description"] == "router-flow"
        assert first["id"] == "maf-workflow-router"
        assert first == second

    def test_to_dict_falls_back_to_static_blueprint_on_dynamic_error(self):
        runner = MCPWorkflowRunner(
            lambda _mcp_url: object(),
            workflow_type=WorkflowType.SEQUENTIAL,
            name="Sequential",
        )

        blueprint = runner.to_dict()

        assert blueprint["name"] == "Sequential"
        assert blueprint["id"] == "maf-workflow-sequential"

    def test_build_dynamic_blueprint_uses_mcp_workflow_base(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("agents.supervisor.create_mcp_tool", lambda _mcp_url=None: object())

        runner = MCPWorkflowRunner(
            lambda _mcp_url: _MinimalMCPWorkflow(),
            workflow_type=WorkflowType.SEQUENTIAL,
        )

        blueprint = runner.to_dict()

        assert blueprint["name"] == "Sequential Workflow"
        assert blueprint["id"] == "wf-1"
