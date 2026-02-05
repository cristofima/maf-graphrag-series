"""
Example: Using the core module for GraphRAG searches.

This script demonstrates how to use the refactored core module
to perform local and global searches against the knowledge graph.

Usage:
    poetry run python -m core.example "Your question here"
    
    # Or with search type:
    poetry run python -m core.example --type global "What are the main themes?"
"""

import argparse
import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from core import load_all, local_search, global_search
from core.data_loader import get_entity_count, get_relationship_count, list_entity_types


console = Console()


async def run_search(query: str, search_type: str = "local") -> None:
    """Run a search and display results."""
    
    console.print(f"\n[bold blue]{'🔍 Local' if search_type == 'local' else '🌍 Global'} Search[/bold blue]\n")
    console.print(f"[dim]Query:[/dim] {query}\n")
    
    # Load data
    with console.status("[bold green]Loading knowledge graph..."):
        try:
            data = load_all()
        except FileNotFoundError as e:
            console.print(f"[red]❌ Error:[/red] {e}")
            console.print("\n[yellow]Run indexing first:[/yellow] poetry run python -m core.index")
            sys.exit(1)
    
    # Show graph stats
    console.print(Panel(
        f"📊 [bold]Graph Statistics[/bold]\n\n"
        f"  Entities: {get_entity_count(data):,}\n"
        f"  Relationships: {get_relationship_count(data):,}\n"
        f"  Entity Types: {', '.join(list_entity_types(data))}",
        title="Knowledge Graph",
        border_style="blue"
    ))
    
    # Perform search
    with console.status(f"[bold green]Running {search_type} search..."):
        if search_type == "local":
            response, context = await local_search(query, data)
        else:
            response, context = await global_search(query, data)
    
    # Display results
    console.print("\n")
    console.print(Panel(
        Markdown(response),
        title="📝 Response",
        border_style="green"
    ))
    
    # Show context info
    if isinstance(context, dict):
        context_summary = []
        for key, value in context.items():
            if hasattr(value, '__len__'):
                context_summary.append(f"{key}: {len(value)} items")
        if context_summary:
            console.print(f"\n[dim]Context: {', '.join(context_summary)}[/dim]")


def main():
    parser = argparse.ArgumentParser(
        description="Search the GraphRAG knowledge graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m core.example "Who leads Project Alpha?"
  python -m core.example --type global "What are the main themes?"
  python -m core.example --type local "What technologies does Sarah use?"
        """
    )
    parser.add_argument(
        "query",
        help="The question to ask"
    )
    parser.add_argument(
        "--type", "-t",
        choices=["local", "global"],
        default="local",
        help="Search type: local (entity-focused) or global (thematic)"
    )
    
    args = parser.parse_args()
    
    asyncio.run(run_search(args.query, args.type))


if __name__ == "__main__":
    main()
