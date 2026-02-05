"""
GraphRAG Indexing CLI

Build knowledge graph from documents in input/documents/.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from core.indexer import build_index


console = Console()


async def run_indexing(resume: bool = False, memory_profile: bool = False):
    """Run the indexing pipeline with progress display."""
    
    console.print()
    console.print(Panel.fit(
        "[bold cyan]GraphRAG Indexing[/bold cyan]\n"
        "Building knowledge graph from documents",
        border_style="cyan"
    ))
    console.print()
    
    # Check input directory
    input_dir = Path("input/documents")
    if not input_dir.exists():
        console.print(f"[red]✗ Input directory not found: {input_dir}[/red]")
        sys.exit(1)
    
    doc_count = len(list(input_dir.glob("*.md")))
    if doc_count == 0:
        console.print(f"[yellow]⚠ No .md files found in {input_dir}[/yellow]")
        sys.exit(1)
    
    console.print(f"[green]✓ Found {doc_count} document(s) in {input_dir}[/green]")
    console.print()
    
    if resume:
        console.print("[yellow]Resuming from previous run...[/yellow]")
    
    # Run indexing with progress indicator
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(
            "[cyan]Running GraphRAG indexing pipeline...",
            total=None
        )
        
        try:
            results = await build_index(
                is_resume_run=resume,
                memory_profile=memory_profile
            )
            progress.update(task, completed=True)
        except Exception as e:
            progress.stop()
            console.print()
            console.print(f"[red]✗ Indexing failed: {e}[/red]")
            if "--verbose" in sys.argv or "-v" in sys.argv:
                console.print_exception()
            sys.exit(1)
    
    # Display results
    console.print()
    console.print("[bold green]✓ Indexing completed successfully![/bold green]")
    console.print()
    
    # Create results table
    table = Table(title="Pipeline Results", show_header=True, header_style="bold cyan")
    table.add_column("Workflow", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Duration", justify="right")
    
    for result in results:
        status = "[green]✓ Success[/green]" if not result.errors else f"[red]✗ Failed[/red]"
        duration = f"{result.runtime:.2f}s" if hasattr(result, 'runtime') else "N/A"
        table.add_row(result.workflow, status, duration)
    
    console.print(table)
    console.print()
    
    # Show output location
    console.print("[bold]Output files:[/bold]")
    console.print("  📁 output/create_final_*.parquet")
    console.print("  📁 output/lancedb/")
    console.print()
    console.print("[dim]You can now run queries:[/dim]")
    console.print('  [cyan]poetry run python -m core.example "Your question"[/cyan]')
    console.print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build GraphRAG knowledge graph from documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m core.index
  python -m core.index --resume
  python -m core.index --memory-profile
        """
    )
    
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous interrupted run"
    )
    
    parser.add_argument(
        "--memory-profile",
        action="store_true",
        help="Enable memory profiling"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed error messages"
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run_indexing(
            resume=args.resume,
            memory_profile=args.memory_profile
        ))
    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]⚠ Indexing interrupted by user[/yellow]")
        sys.exit(130)


if __name__ == "__main__":
    main()
