"""
Run Workflow Patterns - Interactive CLI (Part 4)

Interactive CLI to explore the three workflow patterns introduced in Part 4.
Each pattern queries the same GraphRAG MCP Server from Part 2, but routes
through different multi-agent pipelines.

Workflow Patterns:
    sequential  - Research Pipeline: QueryAnalyzer → KnowledgeSearcher → ReportWriter
    concurrent  - Parallel Search:   EntitySearcher + ThemesSearcher → Synthesis
    handoff     - Expert Routing:    Router → EntityExpert | ThemesExpert

Prerequisites:
    1. Knowledge graph built:   poetry run python -m core.index
    2. MCP Server running:      poetry run python run_mcp_server.py

Usage:
    # Interactive mode (choose workflow + query)
    poetry run python run_workflow.py

    # Direct mode
    poetry run python run_workflow.py sequential "What are the key projects and their tech stack?"
    poetry run python run_workflow.py concurrent "Who leads Project Alpha and what are the themes?"
    poetry run python run_workflow.py handoff    "Who leads Project Alpha?"

Environment Variables:
    AZURE_OPENAI_ENDPOINT         - Azure OpenAI endpoint
    AZURE_OPENAI_API_KEY          - Azure OpenAI API key
    AZURE_OPENAI_CHAT_DEPLOYMENT  - Deployment name (default: gpt-4o)
    MCP_SERVER_URL                - MCP server URL (default: http://127.0.0.1:8011/mcp)
"""

import asyncio
import sys
import time
from pathlib import Path

# Add src/ to path for package imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

console = Console()

# ---------------------------------------------------------------------------
# Example queries for each workflow type (used in interactive mode)
# ---------------------------------------------------------------------------

EXAMPLE_QUERIES = {
    "sequential": [
        "What are the leadership structure, technology choices, and strategic goals of Project Alpha?",
        "Give me a comprehensive overview of TechVenture Inc's engineering practices and team structure.",
        "How does Project Beta connect to the broader organizational strategy?",
    ],
    "concurrent": [
        "What are the main projects and who leads them?",
        "Who are the technical leads and what technologies does TechVenture focus on?",
        "Describe the team structure and the strategic initiatives at TechVenture Inc.",
    ],
    "handoff": [
        "Who leads Project Alpha?",
        "What are the main strategic initiatives at TechVenture Inc?",
        "Tell me about the technology stack used across all projects.",
    ],
}

WORKFLOW_DESCRIPTIONS = {
    "sequential": "Research Pipeline — 3-step chain: Analyze → Search → Write",
    "concurrent": "Parallel Search — Entity + Themes in parallel, then Synthesize",
    "handoff": "Expert Routing — Router classifies, then hands off to specialist",
}


# ---------------------------------------------------------------------------
# Workflow runners
# ---------------------------------------------------------------------------


async def run_sequential(query: str) -> None:
    """Run the Sequential Research Pipeline workflow."""
    from workflows.sequential import ResearchPipelineWorkflow

    console.print("\n[dim]Running [bold]Sequential[/bold] Research Pipeline...[/dim]")

    async with ResearchPipelineWorkflow() as workflow:
        result = await workflow.run(query)

    _display_result(result)


async def run_concurrent(query: str) -> None:
    """Run the Concurrent Parallel Search workflow."""
    from workflows.concurrent import ParallelSearchWorkflow

    console.print("\n[dim]Running [bold]Concurrent[/bold] Parallel Search...[/dim]")

    async with ParallelSearchWorkflow() as workflow:
        result = await workflow.run(query)

    _display_result(result)


async def run_handoff(query: str) -> None:
    """Run the Expert Handoff Router workflow."""
    from workflows.handoff import ExpertHandoffWorkflow

    console.print("\n[dim]Running [bold]Handoff[/bold] Expert Router...[/dim]")

    async with ExpertHandoffWorkflow() as workflow:
        result = await workflow.run(query)

    _display_result(result)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _display_result(result) -> None:
    """Render a WorkflowResult with rich formatting."""
    # Step trace table
    step_table = Table(title="Workflow Steps", show_header=True, header_style="bold cyan")
    step_table.add_column("Step", style="dim", width=4)
    step_table.add_column("Agent", style="bold")
    step_table.add_column("Action")
    step_table.add_column("Time", justify="right", style="dim")

    for i, step in enumerate(result.steps, 1):
        parallel_tag = " [yellow](parallel)[/yellow]" if step.metadata.get("parallel") else ""
        step_table.add_row(
            str(i),
            step.agent_name,
            step.input_summary + parallel_tag,
            f"{step.elapsed_seconds:.1f}s",
        )

    console.print()
    console.print(step_table)
    console.print()

    # Final answer
    console.print(Panel(
        Markdown(result.answer),
        title=f"[bold green]{result.workflow_type.value.capitalize()} Workflow Result[/bold green]",
        subtitle=f"[dim]{result.total_elapsed_seconds:.1f}s total · {len(result.steps)} steps[/dim]",
        border_style="green",
    ))
    console.print()


def _print_workflow_menu() -> None:
    """Print the workflow selection panel."""
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Command", style="bold")
    table.add_column("Pattern")
    table.add_column("Steps")
    table.add_column("Best For")

    table.add_row(
        "sequential",
        "Research Pipeline",
        "Analyze → Search → Write",
        "Complex multi-part questions",
    )
    table.add_row(
        "concurrent",
        "Parallel Search",
        "Entity + Themes ∥ → Synthesize",
        "Dual-perspective questions",
    )
    table.add_row(
        "handoff",
        "Expert Routing",
        "Route → Specialist",
        "Specific entity or themes queries",
    )

    console.print(Panel(
        table,
        title="[bold blue]Part 4: Workflow Patterns[/bold blue]",
        subtitle="[dim]All workflows connect to the same GraphRAG MCP Server[/dim]",
    ))


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------


async def run_interactive() -> None:
    """Run interactive workflow selection mode."""
    _print_workflow_menu()
    console.print()
    console.print("[dim]Type a workflow name (sequential / concurrent / handoff) or 'exit' to quit.[/dim]\n")

    while True:
        workflow_choice = Prompt.ask(
            "[bold cyan]Workflow[/bold cyan]",
            choices=["sequential", "concurrent", "handoff", "exit"],
            default="handoff",
        )

        if workflow_choice == "exit":
            console.print("[yellow]Goodbye![/yellow]")
            break

        # Show example queries for chosen workflow
        examples = EXAMPLE_QUERIES.get(workflow_choice, [])
        if examples:
            console.print("\n[dim]Example queries:[/dim]")
            for i, ex in enumerate(examples, 1):
                console.print(f"  [dim]{i}.[/dim] {ex}")
            console.print()

        query = Prompt.ask("[bold cyan]Query[/bold cyan]").strip()
        if not query:
            continue

        try:
            if workflow_choice == "sequential":
                await run_sequential(query)
            elif workflow_choice == "concurrent":
                await run_concurrent(query)
            elif workflow_choice == "handoff":
                await run_handoff(query)
        except ConnectionError as e:
            console.print(f"\n[red]Connection Error:[/red] {e}")
            console.print("[yellow]Hint:[/yellow] Is the MCP server running?")
            console.print("      Run: [bold]poetry run python run_mcp_server.py[/bold]\n")

        console.print()


# ---------------------------------------------------------------------------
# Single-query mode (non-interactive)
# ---------------------------------------------------------------------------


async def run_single(workflow_type: str, query: str) -> None:
    """Run a single query with the specified workflow type."""
    runners = {
        "sequential": run_sequential,
        "concurrent": run_concurrent,
        "handoff": run_handoff,
    }

    runner = runners.get(workflow_type.lower())
    if runner is None:
        console.print(f"[red]Unknown workflow type:[/red] {workflow_type}")
        console.print("Available: sequential, concurrent, handoff")
        sys.exit(1)

    try:
        await runner(query)
    except ConnectionError as e:
        console.print(f"\n[red]Connection Error:[/red] {e}")
        console.print("[yellow]Hint:[/yellow] Is the MCP server running?")
        console.print("      Run: [bold]poetry run python run_mcp_server.py[/bold]\n")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the workflow CLI."""
    args = sys.argv[1:]

    if len(args) == 0:
        # Interactive mode
        asyncio.run(run_interactive())
    elif len(args) == 1:
        # Usage error — need both workflow type and query
        workflow_type = args[0].lower()
        if workflow_type in ("sequential", "concurrent", "handoff"):
            console.print(f"[yellow]Usage:[/yellow] poetry run python run_workflow.py {workflow_type} \"your query\"")
        else:
            console.print("[red]Usage:[/red] poetry run python run_workflow.py [sequential|concurrent|handoff] \"query\"")
        sys.exit(1)
    elif len(args) >= 2:
        # Non-interactive: workflow_type + query
        workflow_type = args[0]
        query = " ".join(args[1:])
        asyncio.run(run_single(workflow_type, query))


if __name__ == "__main__":
    main()
