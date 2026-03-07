"""Simplified CLI interface for Neo - Claude Code style."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from neo import __version__
from neo.agent import Agent
from neo.config import Config
from neo.llm.client import OpenAIClient
from neo.llm.mock import MockOpenAIClient
from neo.logger import get_logger
from neo.tools.code import AnalyzeFileTool, FindSymbolTool
from neo.tools.file import EditFileTool, GlobTool, GrepTool, ListDirTool, ReadFileTool, WriteFileTool
from neo.tools.git import GitAddTool, GitCommitTool, GitDiffTool, GitLogTool, GitStatusTool
from neo.tools.shell import RunShellTool
from neo.tools.system import GetSystemInfoTool
from neo.utils.path import find_project_root
from neo.utils.transaction import TransactionManager

console = Console()
logger = get_logger(__name__)

# Global transaction manager for undo/redo
_transaction_manager: TransactionManager | None = None


def create_tool_registry() -> Any:
    """Create and register all tools."""
    from neo.tools.registry import ToolRegistry

    registry = ToolRegistry()

    # File tools (core tools)
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(ListDirTool())
    registry.register(GlobTool())
    registry.register(GrepTool())

    # Code tools
    registry.register(AnalyzeFileTool())
    registry.register(FindSymbolTool())

    # Git tools
    registry.register(GitStatusTool())
    registry.register(GitDiffTool())
    registry.register(GitAddTool())
    registry.register(GitCommitTool())
    registry.register(GitLogTool())

    # Shell tools
    registry.register(RunShellTool())

    # System tools
    registry.register(GetSystemInfoTool())

    return registry


def get_transaction_manager(project_path: Path) -> TransactionManager:
    """Get or create transaction manager."""
    global _transaction_manager
    if _transaction_manager is None:
        _transaction_manager = TransactionManager(project_path)
    return _transaction_manager


@click.group(invoke_without_command=True)
@click.option("--model", "-m", help="Model to use (gpt-4o-mini, gpt-4o)")
@click.option("--project", "-p", type=click.Path(), help="Project path")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx: click.Context, model: str | None, project: str | None, verbose: bool) -> None:
    """Neo - Coding assistant (Claude Code style)."""
    logger.info("Neo CLI starting up")

    if ctx.obj is None:
        ctx.obj = {}

    # Load config
    config = Config.load()
    if model:
        config.model = model

    ctx.obj["config"] = config
    ctx.obj["verbose"] = verbose

    # Find project root
    if project:
        project_path = Path(project).resolve()
    else:
        project_path = find_project_root()

    ctx.obj["project_path"] = project_path

    # If no subcommand, run interactive mode
    if ctx.invoked_subcommand is None:
        ctx.invoke(interactive)


@cli.command()
@click.pass_context
def interactive(ctx: click.Context) -> None:
    """Run in interactive mode."""
    config: Config = ctx.obj["config"]
    project_path: Path = ctx.obj["project_path"]

    is_mock_mode = config.mock_mode or not config.openai_api_key

    # Show banner
    banner_text = (
        f"[bold blue]Neo[/bold blue] v{__version__}\n"
        f"Model: [green]{config.model if not is_mock_mode else 'mock'}[/green] | "
        f"Project: [cyan]{project_path.name}[/cyan]"
    )
    if is_mock_mode:
        banner_text += "\n[yellow][MOCK MODE - Set OPENAI_API_KEY for full functionality][/yellow]"

    console.print(
        Panel(
            Text.from_markup(banner_text),
            title="Welcome",
            border_style="blue",
        )
    )

    console.print("\n[dim]Commands:[/dim]")
    console.print("  /reset  - Clear conversation history")
    console.print("  /undo   - Undo last file change")
    console.print("  /status - Show session status")
    console.print("  /exit   - Exit Neo\n")

    # Initialize agent
    logger.debug("Initializing agent")
    llm, tools, agent = _init_agent(config, project_path)

    # Interactive loop
    logger.info("Entering interactive loop")
    while True:
        try:
            user_input = console.input("[bold green]>[/bold green] ").strip()

            if not user_input:
                continue

            logger.debug("User input received: %s", user_input[:100])

            # Handle slash commands
            if user_input.startswith("/"):
                cmd_parts = user_input[1:].split(maxsplit=1)
                cmd = cmd_parts[0].lower()
                args = cmd_parts[1] if len(cmd_parts) > 1 else ""

                if cmd in ("exit", "quit"):
                    console.print("[dim]Goodbye![/dim]")
                    break
                elif cmd == "status":
                    _show_status(agent, project_path)
                    continue
                elif cmd == "reset":
                    agent.reset_memory()
                    console.print("[dim]Memory cleared[/dim]")
                    continue
                elif cmd == "help":
                    _show_help()
                    continue
                elif cmd == "undo":
                    _undo_change(project_path)
                    continue
                elif cmd == "redo":
                    _redo_change(project_path)
                    continue
                elif cmd == "history":
                    _show_history(project_path)
                    continue
                else:
                    console.print(f"[red]Unknown command: /{cmd}[/red]")
                    continue

            # Run agent with streaming
            try:
                _run_with_streaming(agent, user_input)
            except Exception as e:
                logger.exception("Error running agent: %s", e)
                console.print(f"[red]Error: {e}[/red]")

        except KeyboardInterrupt:
            console.print("\n[dim]Use /exit to quit[/dim]")
        except EOFError:
            break


def _init_agent(config: Config, project_path: Path) -> tuple[Any, Any, Agent]:
    """Initialize agent components."""
    logger.debug("Initializing agent for project: %s", project_path)
    is_mock_mode = config.mock_mode or not config.openai_api_key

    if is_mock_mode:
        logger.info("Using mock LLM client")
        llm = MockOpenAIClient(model="mock")
    else:
        logger.info("Using OpenAI client with model: %s", config.model)
        llm = OpenAIClient(
            api_key=config.openai_api_key,
            model=config.model,
            base_url=config.base_url,
        )

    tools = create_tool_registry()
    logger.debug("Created tool registry with %d tools", len(tools))

    agent = Agent(llm=llm, tools=tools, project_path=project_path, config=config)
    logger.info("Agent initialized successfully")

    return llm, tools, agent


def _show_status(agent: Agent, project_path: Path) -> None:
    """Show agent status."""
    status = agent.get_status()

    console.print("\n[bold blue]Session Status[/bold blue]")
    console.print(f"  Model: {status.get('model', 'unknown')}")
    console.print(f"  Memory: {status.get('memory_turns', 0)} turns")

    tokens = status.get('total_tokens', 0)
    console.print(f"  Tokens: {tokens:,} total")

    # Show undo status
    txn_mgr = get_transaction_manager(project_path)
    if txn_mgr.can_undo():
        console.print(f"  Undo: {len(txn_mgr.get_undo_summary())} operation(s) available")

    console.print()


def _show_help() -> None:
    """Show help."""
    help_text = """
[bold blue]Neo Commands[/bold blue]

[bold]Session Commands:[/bold]
  /status       - Show session status and token usage
  /reset        - Clear conversation history
  /help         - Show this help message
  /exit, /quit  - Exit Neo

[bold]File Operations:[/bold]
  /undo         - Undo last file change
  /redo         - Redo last undone change
  /history      - Show operation history

[bold]Tips:[/bold]
  - Neo uses tools automatically to explore and modify code
  - No need to index the project - just ask what you need
  - The agent remembers your conversation within a session
"""
    console.print(help_text)


def _undo_change(project_path: Path) -> None:
    """Undo last file change."""
    txn_mgr = get_transaction_manager(project_path)

    if not txn_mgr.can_undo():
        console.print("[yellow]Nothing to undo[/yellow]")
        return

    result = txn_mgr.undo()
    if result and result.success:
        console.print(f"[green]Undid {result.changes_reverted} change(s)[/green]")
    else:
        console.print(f"[red]Undo failed[/red]")


def _redo_change(project_path: Path) -> None:
    """Redo last undone change."""
    txn_mgr = get_transaction_manager(project_path)

    if not txn_mgr.can_redo():
        console.print("[yellow]Nothing to redo[/yellow]")
        return

    result = txn_mgr.redo()
    if result and result.success:
        console.print(f"[green]Redid {result.changes_applied} change(s)[/green]")
    else:
        console.print(f"[red]Redo failed[/red]")


def _show_history(project_path: Path) -> None:
    """Show operation history."""
    txn_mgr = get_transaction_manager(project_path)
    summaries = txn_mgr.get_undo_summary()

    if not summaries:
        console.print("[dim]No history available[/dim]")
        return

    console.print("\n[bold]Operation History:[/bold]")
    for summary in reversed(summaries):
        console.print(f"  {summary}")


def _run_with_streaming(agent: Agent, user_input: str) -> None:
    """Run agent with streaming output."""
    content_parts: list[str] = []

    def stream_callback(token: str) -> None:
        content_parts.append(token)
        console.print(token, end="")

    # Use Live for updating display
    with Live(console=console, refresh_per_second=10) as live:
        response = asyncio.run(
            agent.run(user_input, streaming_callback=stream_callback)
        )
        live.update(Text(response))

    console.print()  # New line after streaming


@cli.command()
@click.argument("query")
@click.option("--model", "-m", help="Model to use")
@click.pass_context
def ask(ctx: click.Context, query: str, model: str | None) -> None:
    """Ask a question."""
    config: Config = ctx.obj["config"]
    project_path: Path = ctx.obj["project_path"]

    if model:
        config.model = model

    llm, tools, agent = _init_agent(config, project_path)

    # Run with progress spinner
    with console.status("[bold green]Thinking..."):
        try:
            response = asyncio.run(agent.run(query))
            console.print(response)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@cli.command(name="init")
@click.option("--path", "-p", type=click.Path(), default=".")
def init_cmd(path: str) -> None:
    """Initialize a new Neo project."""
    project_path = Path(path).resolve()

    # Create .neo directory
    neo_dir = project_path / ".neo"
    neo_dir.mkdir(exist_ok=True)

    # Create project config
    config_file = neo_dir / "project.json"
    if not config_file.exists():
        config_file.write_text("{}\n")

    console.print(f"[green]Initialized Neo project at {project_path}[/green]")


@cli.command()
@click.pass_context
def tui(ctx: click.Context) -> None:
    """Launch the Textual TUI interface."""
    config: Config = ctx.obj["config"]
    project_path: Path = ctx.obj["project_path"]

    from neo.tui.app import run_tui
    run_tui(project_path=project_path, config=config)


@cli.command()
def version() -> None:
    """Show version information."""
    console.print(f"Neo version {__version__}")


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
