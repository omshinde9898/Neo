"""CLI interface for Neo."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from neo import __version__
from neo.agent import Agent
from neo.config import Config
from neo.llm.client import OpenAIClient
from neo.llm.mock import MockOpenAIClient
from neo.memory.project import ProjectMemory
from neo.tools.code import AnalyzeFileTool, FindSymbolTool
from neo.tools.file import EditFileTool, GlobTool, ListDirTool, ReadFileTool, WriteFileTool
from neo.tools.git import GitAddTool, GitCommitTool, GitDiffTool, GitLogTool, GitStatusTool
from neo.tools.registry import ToolRegistry
from neo.tools.search import SearchCodeTool, ViewCodeTool
from neo.tools.shell import RunShellTool
from neo.tools.system import GetSystemInfoTool
from neo.utils.path import find_project_root

console = Console()


def create_tool_registry() -> ToolRegistry:
    """Create and register all tools."""
    registry = ToolRegistry()

    # File tools
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(ListDirTool())
    registry.register(GlobTool())

    # Code tools
    registry.register(AnalyzeFileTool())
    registry.register(FindSymbolTool())

    # Search tools
    registry.register(SearchCodeTool())
    registry.register(ViewCodeTool())

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


@click.group(invoke_without_command=True)
@click.option("--model", "-m", help="Model to use (gpt-4o-mini, gpt-4o)")
@click.option("--project", "-p", type=click.Path(), help="Project path")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx: click.Context, model: str | None, project: str | None, verbose: bool) -> None:
    """Neo - Local coding agent powered by OpenAI."""
    # Ensure context object exists
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

    # Check for mock mode
    is_mock_mode = config.mock_mode or not config.openai_api_key

    # Show banner
    banner_text = (
        f"[bold blue]Neo[/bold blue] v{__version__} - Coding Assistant\n"
        f"Model: [green]{config.model if not is_mock_mode else 'mock'}[/green]\n"
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

    # Initialize components
    if is_mock_mode:
        llm = MockOpenAIClient(model="mock")
    else:
        llm = OpenAIClient(
            api_key=config.openai_api_key,
            model=config.model,
            base_url=config.base_url,
        )
    tools = create_tool_registry()
    agent = Agent(llm=llm, tools=tools, project_path=project_path, config=config)

    # Interactive loop
    while True:
        try:
            # Get user input
            user_input = console.input("\n[bold green]>[/bold green] ").strip()

            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                cmd = user_input[1:].lower()

                if cmd == "exit" or cmd == "quit":
                    console.print("[dim]Goodbye![/dim]")
                    break
                elif cmd == "status":
                    status = agent.get_status()
                    console.print("[bold]Status:[/bold]")
                    console.print(f"  Model: {status['model']}")
                    console.print(f"  Project: {status['project']}")
                    console.print(f"  Memory: {status['memory_turns']}/{status['max_turns']} turns")
                    tokens = status['tokens']
                    console.print(f"  Tokens: {tokens['total_tokens']} (prompt: {tokens['total_prompt_tokens']}, completion: {tokens['total_completion_tokens']})")
                    continue
                elif cmd == "reset":
                    agent.reset_memory()
                    console.print("[dim]Memory cleared[/dim]")
                    continue
                elif cmd == "help":
                    console.print("[bold]Commands:[/bold]")
                    console.print("  /status  - Show status")
                    console.print("  /reset   - Clear memory")
                    console.print("  /exit    - Quit")
                    console.print("  /help    - Show this help")
                    continue
                else:
                    console.print(f"[red]Unknown command: /{cmd}[/red]")
                    continue

            # Run agent
            try:
                response = asyncio.run(agent.run(user_input))
                console.print(response)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

        except KeyboardInterrupt:
            console.print("\n[dim]Use /exit to quit[/dim]")
        except EOFError:
            break


@cli.command()
@click.argument("query")
@click.option("--model", "-m", help="Model to use")
@click.pass_context
def ask(ctx: click.Context, query: str, model: str | None) -> None:
    """Ask a single question."""
    config: Config = ctx.obj["config"]
    project_path: Path = ctx.obj["project_path"]

    if model:
        config.model = model

    # Initialize components
    if config.mock_mode or not config.openai_api_key:
        if not config.openai_api_key:
            console.print(
                "[yellow]Warning: No OpenAI API key found.[/yellow]\n"
                "Running in [bold]MOCK MODE[/bold] - tools will work but LLM is simulated.\n"
                "Set OPENAI_API_KEY in .env file for full functionality."
            )
        llm = MockOpenAIClient(model="mock")
    else:
        llm = OpenAIClient(
            api_key=config.openai_api_key,
            model=config.model,
            base_url=config.base_url,
        )
    tools = create_tool_registry()
    agent = Agent(llm=llm, tools=tools, project_path=project_path, config=config)

    # Run agent
    try:
        response = asyncio.run(agent.run(query))
        console.print(response)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.argument("tool_name")
@click.argument("args", nargs=-1)
def tool(tool_name: str, args: tuple[str, ...]) -> None:
    """Execute a tool directly."""
    registry = create_tool_registry()

    if tool_name not in registry:
        console.print(f"[red]Tool not found: {tool_name}[/red]")
        console.print(f"Available tools: {', '.join(t.name for t in registry.get_all())}")
        return

    # Parse arguments as key=value pairs
    params: dict[str, str] = {}
    for arg in args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            params[key] = value
        else:
            console.print(f"[red]Invalid argument format: {arg}. Use key=value[/red]")
            return

    # Execute tool
    async def run_tool():
        result = await registry.execute(tool_name, params)
        if result.success:
            console.print(result.output)
        else:
            console.print(f"[red]Error: {result.error}[/red]")

    asyncio.run(run_tool())


@cli.command()
@click.option("--path", "-p", type=click.Path(), default=".")
def init(path: str) -> None:
    """Initialize a new Neo project."""
    project_path = Path(path).resolve()

    # Create .neo directory
    neo_dir = project_path / ".neo"
    neo_dir.mkdir(exist_ok=True)

    # Create project config
    config_file = neo_dir / "project.json"
    if not config_file.exists():
        config_file.write_text("{}\n")

    # Initialize project memory
    project = ProjectMemory(project_path)
    project.scan_project()

    console.print(f"[green]Initialized Neo project at {project_path}[/green]")
    console.print(f"Languages detected: {', '.join(project.languages) or 'None'}")


@cli.command()
def version() -> None:
    """Show version information."""
    console.print(f"Neo version {__version__}")


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
