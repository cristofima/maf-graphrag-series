"""Agent-style facade for the production router workflow."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from agent_framework import CheckpointStorage

from maf_graphrag.agents.session_store import SessionRecord
from maf_graphrag.workflows.base import WorkflowResult
from maf_graphrag.workflows.router import RouterWorkflow, create_router_workflow

RouterWorkflowFactory = Callable[[str | None], RouterWorkflow]


class RouterWorkflowAgentAdapter:
    """Expose RouterWorkflow through a reusable agent-style invocation surface."""

    def __init__(
        self,
        mcp_url: str | None = None,
        *,
        workflow_factory: RouterWorkflowFactory = create_router_workflow,
        checkpoint_storage: CheckpointStorage | None = None,
    ) -> None:
        self._mcp_url = mcp_url
        self._workflow_factory = workflow_factory
        self._checkpoint_storage = checkpoint_storage

    async def run(
        self,
        message: object,
        *,
        session_record: SessionRecord | None = None,
        session_telemetry: Mapping[str, object] | None = None,
        **run_kwargs: Any,
    ) -> WorkflowResult:
        """Run the router for an agent-style caller without owning session storage."""

        telemetry = self._resolve_session_telemetry(session_record, session_telemetry)
        delegated_kwargs = dict(run_kwargs)
        if self._checkpoint_storage is not None:
            delegated_kwargs.setdefault("checkpoint_storage", self._checkpoint_storage)
        async with self._workflow_factory(self._mcp_url) as workflow:
            normalized_query = workflow.prepare_run(message)
            return await workflow.run(
                normalized_query,
                session_telemetry=telemetry,
                **delegated_kwargs,
            )

    async def create_stream(
        self,
        message: object,
        *,
        session_record: SessionRecord | None = None,
        session_telemetry: Mapping[str, object] | None = None,
        **run_kwargs: Any,
    ) -> tuple[Any, Callable[[], Any]]:
        """Create a router stream for an agent-style caller."""

        telemetry = self._resolve_session_telemetry(session_record, session_telemetry)
        delegated_kwargs = dict(run_kwargs)
        if self._checkpoint_storage is not None:
            delegated_kwargs.setdefault("checkpoint_storage", self._checkpoint_storage)
        workflow = self._workflow_factory(self._mcp_url)
        await workflow.__aenter__()
        try:
            normalized_query = workflow.prepare_run(message)
            stream, finalize_inner = await workflow.create_stream(
                normalized_query,
                session_telemetry=telemetry,
                **delegated_kwargs,
            )

            async def finalize() -> WorkflowResult:
                try:
                    return await finalize_inner()
                finally:
                    await workflow.__aexit__(None, None, None)

            return stream, finalize
        except BaseException:
            await workflow.__aexit__(None, None, None)
            raise

    @staticmethod
    def _resolve_session_telemetry(
        session_record: SessionRecord | None,
        session_telemetry: Mapping[str, object] | None,
    ) -> Mapping[str, object] | None:
        if session_record is None:
            return session_telemetry

        telemetry = dict(session_telemetry or {})
        telemetry.setdefault("session_id", session_record.session_id)
        telemetry.setdefault("turn_index", session_record.turn_index + 1)
        telemetry.setdefault("memory_hits", len(session_record.history_groups))
        telemetry.setdefault("compaction_events", 0)
        return telemetry
