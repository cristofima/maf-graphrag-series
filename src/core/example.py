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
import time

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from core import global_search, load_all, local_search
from core.data_loader import get_entity_count, get_relationship_count, list_entity_types

console = Console()


async def run_search(query: str, search_type: str = "local", mode: str = "default") -> None:
    """Run a search and display results.

    Args:
        query: The question to ask
        search_type: "local" or "global"
        mode: "fast" (level 2, ~15s), "detailed" (level 1, ~60s), or "default" (level 2)
    """

    mode_icon = {
        "fast": "⚡",
        "detailed": "🔬",
        "default": "🔍" if search_type == "local" else "🌍"
    }

    mode_desc = {
        "fast": " (Fast Mode - Level 2)",
        "detailed": " (Detailed Mode - Level 1)",
        "default": ""
    }

    console.print(f"\n[bold blue]{mode_icon.get(mode, '🔍')} {search_type.title()} Search{mode_desc.get(mode, '')}[/bold blue]\n")
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

    # Determine community level for global search
    community_level = None
    if search_type == "global":
        if mode == "fast":
            community_level = 2  # 2 communities, ~15s
        elif mode == "detailed":
            community_level = 1  # 22 communities, ~60s
        else:
            community_level = 2  # default to fast

    # Show mode info for global search
    if search_type == "global" and community_level:
        mode_info = {
            2: "[dim]Using Level 2 (2 communities, ~15-20s, 90% quality)[/dim]",
            1: "[dim]Using Level 1 (22 communities, ~60s, 100% quality)[/dim]",
        }
        console.print(f"{mode_info.get(community_level, '')}\n")

    # Perform search
    start_time = time.perf_counter()

    with console.status(f"[bold green]Running {search_type} search..."):
        if search_type == "local":
            response, context = await local_search(query, data)
        else:
            response, context = await global_search(
                query,
                data,
                community_level=community_level
            )

    elapsed_time = time.perf_counter() - start_time

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

    # Show timing
    console.print(f"\n[dim]⏱️  Completed in {elapsed_time:.1f} seconds[/dim]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search the GraphRAG knowledge graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local search (entity-focused)
  python -m core.example "Who leads Project Alpha?"

  # Global search - fast mode (default, ~15s, 90%% quality)
  python -m core.example --type global "What are the main themes?"

  # Global search - detailed mode (~60s, 100%% quality)
  python -m core.example --type global --detailed "What are the main themes?"

  # Explicitly fast mode
  python -m core.example --type global --fast "What are the main projects?"
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
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Fast mode for global search (level 2, ~15s, 90%% quality)"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Detailed mode for global search (level 1, ~60s, 100%% quality)"
    )

    args = parser.parse_args()

    # Determine mode
    mode = "default"
    if args.fast:
        mode = "fast"
    elif args.detailed:
        mode = "detailed"

    # Run search
    asyncio.run(run_search(args.query, args.type, mode))


if __name__ == "__main__":
    main()
