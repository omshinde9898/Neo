"""Enhanced CLI interface for Neo with multi-agent support."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.tree import Tree

from neo import __version__
from neo.agent import Agent
from neo.agents import AgentResult, AgentTask, GeneralAgent
from neo.agents.explore import ExploreAgent
from neo.agents.plan import PlanAgent
from neo.agents.code_review import CodeReviewAgent
from neo.config import Config
from neo.llm.client import OpenAIClient
from neo.llm.mock import MockOpenAIClient
from neo.memory.code_indexer import CodeIndexer
from neo.memory.context_retriever import ContextRetriever
from neo.memory.project import ProjectMemory
from neo.tools.code import AnalyzeFileTool, FindSymbolTool
from neo.tools.file import EditFileTool, GlobTool, ListDirTool, ReadFileTool, WriteFileTool
from neo.tools.git import GitAddTool, GitCommitTool, GitDiffTool, GitLogTool, GitStatusTool
from neo.tools.registry import ToolRegistry
from neo.tools.search import SearchCodeTool, ViewCodeTool
from neo.tools.shell import RunShellTool
from neo.tools.system import GetSystemInfoTool
from neo.tui.app import run_tui
from neo.utils.path import find_project_root
from neo.utils.transaction import TransactionManager
from neo.logger import logger, log_exception

console = Console()

# Global transaction manager for undo/redo
_transaction_manager: TransactionManager | None = None


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
    """Neo - Advanced coding agent with multi-agent system."""
    logger.info("Neo CLI starting up")
    logger.debug("Arguments: model=%s, project=%s, verbose=%s", model, project, verbose)

    if ctx.obj is None:
        ctx.obj = {}

    # Load config
    config = Config.load()
    logger.debug("Config loaded: model=%s, mock_mode=%s", config.model, config.mock_mode)
    if model:
        config.model = model
        logger.info("Model overridden via CLI: %s", model)

    ctx.obj["config"] = config
    ctx.obj["verbose"] = verbose

    # Find project root
    if project:
        project_path = Path(project).resolve()
        logger.debug("Using project path from CLI: %s", project_path)
    else:
        project_path = find_project_root()
        logger.debug("Found project root: %s", project_path)

    ctx.obj["project_path"] = project_path
    logger.info("Project path set to: %s", project_path)

    # If no subcommand, run interactive mode
    if ctx.invoked_subcommand is None:
        ctx.invoke(interactive)


@cli.command()
@click.pass_context
def interactive(ctx: click.Context) -> None:
    """Run in enhanced interactive mode."""
    logger.info("Starting interactive mode")
    config: Config = ctx.obj["config"]
    project_path: Path = ctx.obj["project_path"]

    is_mock_mode = config.mock_mode or not config.openai_api_key
    logger.info("Mock mode: %s", is_mock_mode)

    # Show enhanced banner
    banner_text = (
        f"[bold blue]Neo[/bold blue] v{__version__} - Advanced Coding Assistant\n"
        f"Model: [green]{config.model if not is_mock_mode else 'mock'}[/green] | "
        f"Project: [cyan]{project_path.name}[/cyan]\n"
        f"[dim]Try 'neo tui' for the visual interface[/dim]"
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

    console.print("\n[dim]Enhanced commands:[/dim]")
    console.print("  /agent [explore|plan|review] - Use specific agent")
    console.print("  /search [query]              - Semantic code search")
    console.print("  /undo                        - Undo last file change")
    console.print("  /index                       - Index codebase for search")
    console.print("  Type /help for all commands\n")

    # Initialize components
    logger.debug("Initializing agent components")
    llm, tools, agent = _init_agent(config, project_path)

    # Initialize context retriever
    logger.debug("Initializing context retriever")
    context_retriever = ContextRetriever(project_path)

    # Interactive loop
    logger.info("Entering interactive loop")
    while True:
        try:
            user_input = console.input("\n[bold green]>[/bold green] ").strip()

            if not user_input:
                continue

            logger.debug("User input received: %s", user_input[:100])

            # Handle slash commands
            if user_input.startswith("/"):
                cmd_parts = user_input[1:].split(maxsplit=1)
                cmd = cmd_parts[0].lower()
                args = cmd_parts[1] if len(cmd_parts) > 1 else ""
                logger.info("Command executed: /%s", cmd)

                if cmd in ("exit", "quit"):
                    logger.info("User requested exit")
                    console.print("[dim]Goodbye![/dim]")
                    break
                elif cmd == "status":
                    _show_status(agent, context_retriever)
                    continue
                elif cmd == "reset":
                    logger.info("Resetting agent memory")
                    agent.reset_memory()
                    console.print("[dim]Memory cleared[/dim]")
                    continue
                elif cmd == "help":
                    _show_help()
                    continue
                elif cmd == "agent":
                    logger.info("Running specific agent: %s", args)
                    _run_specific_agent(args, config, project_path, llm, tools)
                    continue
                elif cmd == "search":
                    logger.info("Semantic search: %s", args)
                    _semantic_search(args, project_path)
                    continue
                elif cmd == "index":
                    logger.info("Indexing codebase")
                    _index_codebase(project_path)
                    continue
                elif cmd == "undo":
                    logger.info("Undo requested")
                    _undo_change(project_path)
                    continue
                elif cmd == "redo":
                    logger.info("Redo requested")
                    _redo_change(project_path)
                    continue
                elif cmd == "history":
                    _show_history(project_path)
                    continue
                elif cmd == "logs":
                    logger.info("Showing recent logs")
                    _show_logs(args)
                    continue
                else:
                    console.print(f"[red]Unknown command: /{cmd}[/red]")
                    continue

            # Show context if available
            if not is_mock_mode and len(user_input) > 20:
                try:
                    context = context_retriever.get_context_for_query(user_input, max_chunks=3, max_files=2)
                    if context.relevant_files:
                        console.print(f"[dim]Context: {', '.join(context.relevant_files)}[/dim]")
                        logger.debug("Retrieved context for files: %s", context.relevant_files)
                except Exception as e:
                    logger.warning("Failed to get context: %s", e)
                    pass

            # Run agent with streaming
            try:
                logger.info("Running agent with user input")
                _run_with_streaming(agent, user_input)
                logger.info("Agent response completed")
            except Exception as e:
                logger.exception("Error running agent: %s", e)
                console.print(f"[red]Error: {e}[/red]")

        except KeyboardInterrupt:
            console.print("\n[dim]Use /exit to quit[/dim]")
        except EOFError:
            break


def _init_agent(config: Config, project_path: Path) -> tuple[Any, ToolRegistry, Agent]:
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
    logger.debug("Created tool registry with %d tools", len(tools.tools))

    agent = Agent(llm=llm, tools=tools, project_path=project_path, config=config)
    logger.info("Agent initialized successfully")

    return llm, tools, agent


def _show_status(agent: Agent, context_retriever: ContextRetriever) -> None:
    """Show detailed agent status."""
    status = agent.get_status()

    console.print("\n[bold blue]Agent Status[/bold blue]")
    console.print(f"  Model: {status.get('model', 'unknown')}")
    console.print(f"  Active Agents: {status.get('active_agents', 0)}")
    console.print(f"  Task History: {status.get('task_history', 0)}")
    console.print(f"  Memory: {status.get('memory_turns', 0)} turns")

    tokens = status.get('tokens', {})
    console.print(f"  Tokens: {tokens.get('total_tokens', 0):,} total")

    # Show index status
    try:
        count = context_retriever.indexer.vector_store.count()
        console.print(f"  Code Index: {count} chunks indexed")
    except Exception:
        console.print("  Code Index: Not indexed")

    # Show undo status
    txn_mgr = get_transaction_manager(Path(status.get('project', '.')))
    if txn_mgr.can_undo():
        console.print(f"  Undo: {len(txn_mgr.get_undo_summary())} operation(s) available")

    console.print()


def _show_help() -> None:
    """Show comprehensive help."""
    help_text = """
[bold blue]Neo Commands[/bold blue]

[bold]Basic Commands:[/bold]
  /status       - Show agent status and token usage
  /reset        - Clear conversation history
  /help         - Show this help message
  /exit, /quit  - Exit Neo

[bold]Multi-Agent Commands:[/bold]
  /agent explore [query]  - Fast codebase exploration
  /agent plan [task]      - Create implementation plan
  /agent review [file]  - Code review and analysis

[bold]Code Intelligence:[/bold]
  /search [query]         - Semantic code search
  /index                  - Index codebase for search
  /index --force          - Force re-index

[bold]File Operations:[/bold]
  /undo                   - Undo last file change
  /redo                   - Redo last undone change
  /history                - Show operation history
  /logs [N]               - Show last N log lines (default 50)

[bold]Examples:[/bold]
  /agent explore "find all API endpoints"
  /agent plan "refactor auth module"
  /agent review src/main.py
  /search "how to handle errors"

[bold]Keyboard Shortcuts:[/bold]
  Ctrl+C - Cancel current operation
  Up/Down - Navigate command history
"""
    console.print(help_text)


def _run_specific_agent(
    args: str,
    config: Config,
    project_path: Path,
    llm: OpenAIClient,
    tools: ToolRegistry,
) -> None:
    """Run a specific agent type."""
    if not args:
        console.print("[red]Usage: /agent [explore|plan|review] [query][/red]")
        return

    parts = args.split(maxsplit=1)
    agent_type = parts[0].lower()
    query = parts[1] if len(parts) > 1 else ""

    if not query:
        console.print(f"[red]Please provide a query for {agent_type} agent[/red]")
        return

    agent_map = {
        "explore": ExploreAgent,
        "plan": PlanAgent,
        "review": CodeReviewAgent,
    }

    if agent_type not in agent_map:
        console.print(f"[red]Unknown agent: {agent_type}. Use: explore, plan, review[/red]")
        return

    agent_class = agent_map[agent_type]
    agent = agent_class(llm=llm, tools=tools, project_path=project_path, config=config)

    task = AgentTask(
        id=f"cli_{agent_type}",
        type=agent_type,
        description=query,
        max_iterations=10,
    )

    console.print(f"[dim]Running {agent_type} agent...[/dim]\n")

    try:
        result = asyncio.run(agent.execute(task))

        if result.success:
            # Format output based on agent type
            if agent_type == "plan" and result.data:
                _format_plan_output(result)
            elif agent_type == "review" and result.data:
                _format_review_output(result)
            else:
                console.print(result.content)
        else:
            console.print(f"[red]Error: {result.error}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def _format_plan_output(result: AgentResult) -> None:
    """Format plan agent output."""
    console.print("\n[bold blue]Implementation Plan[/bold blue]\n")
    console.print(result.content)

    if result.data and "steps" in result.data:
        console.print("\n[bold]Steps:[/bold]")
        for step in result.data["steps"]:
            console.print(f"  {step.get('order', '?')}. {step.get('action', 'Unknown')}")


def _format_review_output(result: AgentResult) -> None:
    """Format review agent output with highlighting."""
    console.print("\n[bold blue]Code Review[/bold blue]\n")

    # Parse and highlight issues
    lines = result.content.split("\n")
    for line in lines:
        if "🔴" in line or "Critical" in line:
            console.print(f"[bold red]{line}[/bold red]")
        elif "🟡" in line or "Warning" in line:
            console.print(f"[bold yellow]{line}[/bold yellow]")
        elif "🟢" in line or "Suggestion" in line:
            console.print(f"[bold green]{line}[/bold green]")
        elif line.startswith("```"):
            continue
        else:
            console.print(line)


def _semantic_search(query: str, project_path: Path) -> None:
    """Perform semantic code search."""
    if not query:
        console.print("[red]Usage: /search [query][/red]")
        return

    indexer = CodeIndexer(project_path)

    # Index if needed
    if indexer.vector_store.count() == 0:
        console.print("[dim]Indexing codebase...[/dim]")
        try:
            stats = indexer.index_project()
            console.print(f"[green]Indexed {stats['files_indexed']} files[/green]\n")
        except Exception as e:
            console.print(f"[red]Failed to index: {e}[/red]")
            return

    console.print(f"[dim]Searching for: {query}[/dim]\n")

    try:
        results = indexer.search(query, n_results=10)

        if not results:
            console.print("[yellow]No results found[/yellow]")
            return

        console.print(f"[bold]{len(results)} results:[/bold]\n")

        for i, chunk in enumerate(results, 1):
            # Show file path with line numbers
            console.print(
                f"[bold cyan]{i}. {chunk.file_path}:{chunk.start_line}-{chunk.end_line}[/bold cyan] "
                f"([dim]{chunk.chunk_type}[/dim])"
            )

            # Show code snippet
            code = chunk.content[:300] + "..." if len(chunk.content) > 300 else chunk.content
            syntax = Syntax(code, chunk.language, theme="monokai", line_numbers=False)
            console.print(Panel(syntax, border_style="dim"))

    except Exception as e:
        console.print(f"[red]Search error: {e}[/red]")


def _index_codebase(project_path: Path, force: bool = False) -> None:
    """Index the codebase for semantic search."""
    indexer = CodeIndexer(project_path)

    console.print("[dim]Indexing codebase...[/dim]")

    try:
        stats = indexer.index_project(force=force)
        console.print(f"[green]Indexing complete![/green]")
        console.print(f"  Files indexed: {stats['files_indexed']}")
        console.print(f"  Chunks created: {stats['chunks_created']}")
        console.print(f"  Total vectors: {stats['vector_count']}")
    except Exception as e:
        console.print(f"[red]Indexing failed: {e}[/red]")


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
        console.print(f"[red]Undo failed: {result.error if result else 'Unknown error'}[/red]")


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
        console.print(f"[red]Redo failed: {result.error if result else 'Unknown error'}[/red]")


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


def _show_logs(lines_str: str) -> None:
    """Show recent log entries."""
    from neo.logger import get_log_dir

    log_dir = get_log_dir()
    log_file = log_dir / "neo.log"

    if not log_file.exists():
        console.print(f"[dim]No log file found at {log_file}[/dim]")
        return

    # Parse number of lines to show (default 50)
    try:
        num_lines = int(lines_str) if lines_str else 50
    except ValueError:
        num_lines = 50

    try:
        with open(log_file, encoding="utf-8") as f:
            all_lines = f.readlines()

        # Get last N lines
        recent_lines = all_lines[-num_lines:]

        console.print(f"\n[bold]Recent Logs (last {len(recent_lines)} lines):[/bold]")
        console.print(f"[dim]Log file: {log_file}[/dim]\n")

        for line in recent_lines:
            # Strip newline and print
            console.print(line.rstrip())

    except Exception as e:
        console.print(f"[red]Error reading logs: {e}[/red]")


def _run_with_streaming(agent: Agent, user_input: str) -> None:
    """Run agent with streaming output."""
    content_parts: list[str] = []

    def stream_callback(token: str) -> None:
        content_parts.append(token)
        # Print token immediately
        console.print(token, end="")

    # Use Rich Live for updating display
    with Live(console=console, refresh_per_second=10) as live:
        response = asyncio.run(
            agent.run(user_input, streaming_callback=stream_callback)
        )
        live.update(Text(response))

    console.print()  # New line after streaming


@cli.command()
@click.argument("query")
@click.option("--model", "-m", help="Model to use")
@click.option("--agent-type", "-a", type=click.Choice(["general", "explore", "plan", "review"]),
              default="general", help="Agent type to use")
@click.option("--context", "-c", is_flag=True, help="Show relevant context")
@click.pass_context
def ask(ctx: click.Context, query: str, model: str | None, agent_type: str, context: bool) -> None:
    """Ask a question with optional agent type."""
    config: Config = ctx.obj["config"]
    project_path: Path = ctx.obj["project_path"]

    if model:
        config.model = model

    llm, tools, agent = _init_agent(config, project_path)

    # Show context if requested
    if context:
        try:
            retriever = ContextRetriever(project_path)
            ctx_data = retriever.get_context_for_query(query)
            if ctx_data.relevant_files:
                console.print(f"[dim]Context from: {', '.join(ctx_data.relevant_files)}[/dim]\n")
        except Exception:
            pass

    # Use specific agent if requested
    if agent_type != "general":
        agent_map = {
            "explore": ExploreAgent,
            "plan": PlanAgent,
            "review": CodeReviewAgent,
        }
        agent_class = agent_map.get(agent_type, GeneralAgent)
        agent = agent_class(llm=llm, tools=tools, project_path=project_path, config=config)

    # Run with progress spinner
    with console.status(f"[bold green]{agent_type.capitalize()} agent thinking..."):
        try:
            response = asyncio.run(agent.run(query))
            console.print(response)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@cli.command(name="explore")
@click.argument("query")
@click.pass_context
def explore_cmd(ctx: click.Context, query: str) -> None:
    """Fast codebase exploration (ExploreAgent)."""
    config: Config = ctx.obj["config"]
    project_path: Path = ctx.obj["project_path"]

    llm, tools, _ = _init_agent(config, project_path)
    agent = ExploreAgent(llm=llm, tools=tools, project_path=project_path, config=config)

    task = AgentTask(id="cli_explore", type="explore", description=query)

    with console.status("[bold green]Exploring codebase..."):
        try:
            result = asyncio.run(agent.execute(task))
            if result.success:
                console.print(result.content)
            else:
                console.print(f"[red]Error: {result.error}[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@cli.command(name="plan")
@click.argument("task_description")
@click.option("--files", "-f", help="Files to analyze (comma-separated)")
@click.pass_context
def plan_cmd(ctx: click.Context, task_description: str, files: str | None) -> None:
    """Create implementation plan (PlanAgent)."""
    config: Config = ctx.obj["config"]
    project_path: Path = ctx.obj["project_path"]

    llm, tools, _ = _init_agent(config, project_path)
    agent = PlanAgent(llm=llm, tools=tools, project_path=project_path, config=config)

    files_list = files.split(",") if files else []
    task = AgentTask(
        id="cli_plan",
        type="plan",
        description=task_description,
        context={"files_to_explore": files_list},
    )

    with console.status("[bold green]Creating plan..."):
        try:
            result = asyncio.run(agent.execute(task))
            if result.success:
                _format_plan_output(result)
            else:
                console.print(f"[red]Error: {result.error}[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@cli.command(name="review")
@click.argument("file_path", type=click.Path())
@click.pass_context
def review_cmd(ctx: click.Context, file_path: str) -> None:
    """Review code for quality (CodeReviewAgent)."""
    config: Config = ctx.obj["config"]
    project_path: Path = ctx.obj["project_path"]

    llm, tools, _ = _init_agent(config, project_path)
    agent = CodeReviewAgent(llm=llm, tools=tools, project_path=project_path, config=config)

    full_path = project_path / file_path
    if not full_path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return

    task = AgentTask(
        id="cli_review",
        type="review",
        description=f"Review the code in {file_path}",
        context={"file_path": file_path},
    )

    with console.status("[bold green]Reviewing code..."):
        try:
            result = asyncio.run(agent.execute(task))
            if result.success:
                _format_review_output(result)
            else:
                console.print(f"[red]Error: {result.error}[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@cli.command(name="search")
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Number of results")
@click.option("--index", "-i", is_flag=True, help="Force re-index before search")
@click.pass_context
def search_cmd(ctx: click.Context, query: str, limit: int, index: bool) -> None:
    """Semantic code search."""
    project_path: Path = ctx.obj["project_path"]

    if index:
        _index_codebase(project_path, force=True)

    _semantic_search(query, project_path)


@cli.command(name="index")
@click.option("--force", "-f", is_flag=True, help="Force re-index")
@click.pass_context
def index_cmd(ctx: click.Context, force: bool) -> None:
    """Index codebase for semantic search."""
    project_path: Path = ctx.obj["project_path"]
    _index_codebase(project_path, force=force)


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

    # Suggest indexing
    console.print("\n[dim]Tip: Run 'neo index' to enable semantic code search[/dim]")


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
@click.pass_context
def tui(ctx: click.Context) -> None:
    """Launch the Textual TUI interface."""
    config: Config = ctx.obj["config"]
    project_path: Path = ctx.obj["project_path"]

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
