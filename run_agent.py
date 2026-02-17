"""
Run Knowledge Captain Agent - Interactive CLI

Interactive CLI to chat with the Knowledge Captain agent, which queries
the GraphRAG knowledge graph via MCP.

Prerequisites:
    1. MCP Server must be running: poetry run python run_mcp_server.py
    2. Knowledge graph must be built: poetry run python -m core.index

Usage:
    poetry run python run_agent.py
    
    # Or with a single query (non-interactive)
    poetry run python run_agent.py "Who leads Project Alpha?"

Environment Variables:
    AZURE_OPENAI_ENDPOINT - Azure OpenAI endpoint
    AZURE_OPENAI_API_KEY - Azure OpenAI API key
    AZURE_OPENAI_CHAT_DEPLOYMENT - Deployment name (default: gpt-4o)
    MCP_SERVER_URL - MCP server URL (default: http://127.0.0.1:8011/mcp)
"""

import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()


async def run_interactive():
    """Run interactive chat mode with conversation memory."""
    from agents.supervisor import KnowledgeCaptainRunner
    
    console.print(Panel.fit(
        "[bold blue]Knowledge Captain[/bold blue] - GraphRAG Agent\n\n"
        "Ask questions about TechVenture Inc's knowledge graph.\n"
        "The agent uses MCP to query GraphRAG (local/global search).\n"
        "[dim]Conversation history is maintained for follow-up questions.[/dim]\n\n"
        "Commands:\n"
        "  [bold]clear[/bold] - Clear conversation history\n"
        "  [bold]quit[/bold]  - Exit the chat\n",
        title="🤖 Part 3: Supervisor Agent Pattern"
    ))
    
    try:
        async with KnowledgeCaptainRunner() as runner:
            console.print("\n[green]✓[/green] Connected to MCP Server\n")
            
            while True:
                try:
                    # Get user input
                    user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
                    
                    if not user_input:
                        continue
                    
                    if user_input.lower() in ('quit', 'exit', 'q'):
                        console.print("\n[yellow]Goodbye![/yellow]\n")
                        break
                    
                    if user_input.lower() == 'clear':
                        runner.clear_history()
                        console.print("[green]✓[/green] Conversation history cleared.\n")
                        continue
                    
                    # Process query with timing
                    console.print("[dim]Thinking...[/dim]")
                    start_time = time.time()
                    
                    response = await runner.ask(user_input)
                    
                    elapsed = time.time() - start_time
                    
                    # Display response
                    console.print(Panel(
                        Markdown(response.text),
                        title="[bold green]Agent[/bold green]",
                        subtitle=f"[dim]{elapsed:.1f}s[/dim]",
                        border_style="green"
                    ))
                    console.print()
                    
                except KeyboardInterrupt:
                    console.print("\n\n[yellow]Interrupted. Goodbye![/yellow]\n")
                    break
                    
    except ConnectionError as e:
        console.print(f"\n[red]Connection Error:[/red] {e}")
        console.print("[yellow]Hint:[/yellow] Is the MCP server running?")
        console.print("      Run: [bold]poetry run python run_mcp_server.py[/bold]\n")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}\n")
        sys.exit(1)


async def run_single_query(query: str):
    """Run a single query and exit."""
    from agents.supervisor import KnowledgeCaptainRunner
    
    console.print(f"[bold]Query:[/bold] {query}\n")
    
    try:
        async with KnowledgeCaptainRunner() as runner:
            start_time = time.time()
            response = await runner.ask(query)
            elapsed = time.time() - start_time
            
            console.print(Panel(
                Markdown(response.text),
                title="[bold green]Answer[/bold green]",
                subtitle=f"[dim]{elapsed:.1f}s[/dim]",
                border_style="green"
            ))
            
    except ConnectionError as e:
        console.print(f"[red]Connection Error:[/red] {e}")
        console.print("[yellow]Hint:[/yellow] Is the MCP server running?\n")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}\n")
        sys.exit(1)


def main():
    """Entry point for CLI."""
    if len(sys.argv) > 1:
        # Single query mode
        query = " ".join(sys.argv[1:])
        asyncio.run(run_single_query(query))
    else:
        # Interactive mode
        asyncio.run(run_interactive())


if __name__ == "__main__":
    main()
