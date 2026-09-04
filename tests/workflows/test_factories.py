"""Unit tests for workflow factory functions."""

from unittest.mock import MagicMock

from maf_graphrag.workflows.base import (
    create_concurrent_workflow,
    create_handoff_workflow,
    create_router_workflow,
    create_sequential_workflow,
)


class TestWorkflowFactoryFunctions:
    """Test factory functions from workflows/base.py (improvement 4.4)."""

    def test_create_sequential_workflow_returns_instance(self):
        from maf_graphrag.workflows.sequential import ResearchPipelineWorkflow

        workflow = create_sequential_workflow()
        assert isinstance(workflow, ResearchPipelineWorkflow)

    def test_create_concurrent_workflow_returns_instance(self):
        from maf_graphrag.workflows.concurrent import ParallelSearchWorkflow

        workflow = create_concurrent_workflow()
        assert isinstance(workflow, ParallelSearchWorkflow)

    def test_create_handoff_workflow_returns_instance(self):
        from maf_graphrag.workflows.handoff import ExpertHandoffWorkflow

        workflow = create_handoff_workflow()
        assert isinstance(workflow, ExpertHandoffWorkflow)

    def test_create_router_workflow_returns_instance(self, monkeypatch):
        from maf_graphrag.workflows.router import RouterWorkflow

        monkeypatch.setattr("maf_graphrag.workflows.router.RouterClassifier", MagicMock(return_value=MagicMock()))
        workflow = create_router_workflow()
        assert isinstance(workflow, RouterWorkflow)

    def test_create_sequential_passes_mcp_url(self):
        workflow = create_sequential_workflow(mcp_url="http://localhost:9999/mcp")
        assert workflow._mcp_url == "http://localhost:9999/mcp"

    def test_create_concurrent_passes_mcp_url(self):
        workflow = create_concurrent_workflow(mcp_url="http://localhost:9999/mcp")
        assert workflow._mcp_url == "http://localhost:9999/mcp"

    def test_create_handoff_passes_mcp_url(self):
        workflow = create_handoff_workflow(mcp_url="http://localhost:9999/mcp")
        assert workflow._mcp_url == "http://localhost:9999/mcp"

    def test_create_router_passes_mcp_url(self, monkeypatch):
        monkeypatch.setattr("maf_graphrag.workflows.router.RouterClassifier", MagicMock(return_value=MagicMock()))
        workflow = create_router_workflow(mcp_url="http://localhost:9999/mcp")
        assert workflow._mcp_url == "http://localhost:9999/mcp"

    def test_each_call_returns_fresh_instance(self):
        w1 = create_sequential_workflow()
        w2 = create_sequential_workflow()
        assert w1 is not w2

    def test_default_mcp_url_is_none(self):
        workflow = create_sequential_workflow()
        assert workflow._mcp_url is None
