"""Main Textual app for Neo."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, Static

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
from neo.tui.widgets import ChatMessage, CodeView, DiffView, FileTree, InputArea, StatusBar, ToolCall
from neo.utils.path import find_project_root


class CommandPalette(ModalScreen):
    """Command palette for quick access to commands."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]

    COMMANDS = {
        "status": "Show agent status",
        "cost": "Show token usage and cost",
        "reset": "Clear conversation memory",
        "diff": "Show git diff",
        "tree": "Refresh file tree",
        "help": "Show help",
        "quit": "Exit Neo",
    }

    def compose(self) -> ComposeResult:
        """Compose the command palette."""
        yield Label("Command Palette", id="palette-title")
        yield Input(placeholder="Type a command...", id="palette-input")
        yield Container(id="commands-list")

    def on_mount(self) -> None:
        """Mount the palette."""
        self._show_commands("")
        self.query_one("#palette-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        self._show_commands(event.value)

    def _show_commands(self, filter_text: str) -> None:
        """Show filtered commands.

        Args:
            filter_text: Filter text
        """
        container = self.query_one("#commands-list", Container)
        container.remove_children()

        for cmd, desc in self.COMMANDS.items():
            if filter_text.lower() in cmd.lower() or filter_text.lower() in desc.lower():
                row = Horizontal(
                    Label(f"/{cmd}", classes="command-name"),
                    Label(desc, classes="command-desc"),
                    classes="command-row",
                )
                container.mount(row)

    def on_key(self, event) -> None:
        """Handle key events."""
        if event.key == "enter":
            input_widget = self.query_one("#palette-input", Input)
            cmd = input_widget.value
            if cmd:
                self.dismiss(cmd)


class NeoApp(App):
    """Main Textual app for Neo."""

    CSS = """
    /* Main layout */
    Screen {
        align: center middle;
    }

    /* Sidebar */
    #sidebar {
        width: 25%;
        height: 100%;
        border-right: solid $primary;
        padding: 1;
    }

    #file-tree {
        height: 1fr;
        width: 100%;
    }

    /* Main area */
    #main-area {
        width: 75%;
        height: 100%;
    }

    /* Chat area */
    #chat-container {
        height: 1fr;
        width: 100%;
        overflow-y: auto;
    }

    ChatMessage {
        margin: 1 0;
    }

    ToolCall {
        height: auto;
        margin: 0 0 0 4;
    }

    /* Input area */
    #input-container {
        height: auto;
        max-height: 30%;
        width: 100%;
        border-top: solid $primary;
        padding: 1;
    }

    #input-area {
        height: auto;
        width: 100%;
    }

    /* Status bar */
    #status-bar {
        height: 1;
        width: 100%;
    }

    /* Command palette */
    CommandPalette {
        align: center middle;
    }

    CommandPalette > Container {
        width: 60;
        height: auto;
        max-height: 20;
        border: solid $primary;
        background: $surface;
    }

    #palette-title {
        text-align: center;
        padding: 1;
    }

    .command-row {
        height: 1;
        width: 100%;
        padding: 0 1;
    }

    .command-name {
        width: 15;
        text-align: left;
        color: $primary;
    }

    .command-desc {
        width: 1fr;
        text-align: left;
    }

    /* Scrollbar */
    * {
        scrollbar-size: 1 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+k", "command_palette", "Command Palette"),
        Binding("ctrl+r", "refresh_tree", "Refresh Tree"),
        Binding("ctrl+d", "show_diff", "Show Diff"),
        Binding("ctrl+g", "git_status", "Git Status"),
        Binding("ctrl+slash", "focus_input", "Focus Input"),
    ]

    TITLE = f"Neo v{__version__}"

    def __init__(self, project_path: Path | None = None, config: Config | None = None):
        """Initialize the app.

        Args:
            project_path: Path to project
            config: Optional config
        """
        super().__init__()
        self.config = config or Config.load()
        self.project_path = project_path or find_project_root()
        self.project = ProjectMemory(self.project_path)

        # Initialize components
        self._init_agent()

        # State
        self.messages: list[ChatMessage] = []
        self.current_streaming_message: ChatMessage | None = None

    def _init_agent(self) -> None:
        """Initialize the Neo agent."""
        # Create LLM client
        if self.config.mock_mode or not self.config.openai_api_key:
            self.llm = MockOpenAIClient(model="mock")
        else:
            self.llm = OpenAIClient(
                api_key=self.config.openai_api_key,
                model=self.config.model,
                base_url=self.config.base_url,
            )

        # Create tools
        self.tools = self._create_tool_registry()

        # Create agent
        self.agent = Agent(
            llm=self.llm,
            tools=self.tools,
            project_path=self.project_path,
            config=self.config,
        )

    def _create_tool_registry(self) -> ToolRegistry:
        """Create and register all tools.

        Returns:
            Tool registry with all tools
        """
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

    def compose(self) -> ComposeResult:
        """Compose the UI."""
        # Header
        yield Header()

        # Main horizontal split
        with Horizontal():
            # Sidebar with file tree
            with Vertical(id="sidebar"):
                yield Label("📂 Project", id="sidebar-title")
                yield FileTree(self.project_path, id="file-tree")

            # Main area
            with Vertical(id="main-area"):
                # Chat container
                with Vertical(id="chat-container"):
                    yield Label(
                        f"Welcome to Neo v{__version__}!",
                        id="welcome-message",
                        classes="welcome",
                    )
                    yield Label(
                        "Type a message and press Enter to send, or Ctrl+K for commands",
                        id="welcome-hint",
                        classes="welcome dim",
                    )

                # Input area
                with Container(id="input-container"):
                    yield InputArea(id="input-area")

        # Status bar
        yield StatusBar(id="status-bar")

        # Footer
        yield Footer()

    def on_mount(self) -> None:
        """Handle app mount."""
        # Update status bar
        status = self.query_one("#status-bar", StatusBar)
        status.model = self.config.model
        status.status = "Ready"

        # Focus input
        self._focus_input()

    def _focus_input(self) -> None:
        """Focus the input area."""
        input_area = self.query_one("#input-area", InputArea)
        input_area.focus_input()

    def action_focus_input(self) -> None:
        """Focus input action."""
        self._focus_input()

    def action_command_palette(self) -> None:
        """Show command palette."""
        def handle_command(cmd: str | None) -> None:
            """Handle command selection."""
            if cmd:
                self._handle_command(cmd)

        self.push_screen(CommandPalette(), handle_command)

    def action_refresh_tree(self) -> None:
        """Refresh file tree."""
        tree = self.query_one("#file-tree", FileTree)
        tree.refresh_tree()
        self.notify("File tree refreshed")

    def action_show_diff(self) -> None:
        """Show git diff."""
        asyncio.create_task(self._run_agent_query("/diff"))

    def action_git_status(self) -> None:
        """Show git status."""
        asyncio.create_task(self._run_agent_query("/status"))

    def _handle_command(self, cmd: str) -> None:
        """Handle slash commands.

        Args:
            cmd: Command string
        """
        if cmd == "quit" or cmd == "exit":
            self.exit()
        elif cmd == "status":
            asyncio.create_task(self._run_agent_query("/status"))
        elif cmd == "cost":
            self._show_cost()
        elif cmd == "reset":
            self.agent.reset_memory()
            self.notify("Memory cleared")
        elif cmd == "diff":
            asyncio.create_task(self._run_agent_query("/diff"))
        elif cmd == "tree":
            self.action_refresh_tree()
        elif cmd == "help":
            self._show_help()
        else:
            self.notify(f"Unknown command: /{cmd}", severity="warning")

    def _show_help(self) -> None:
        """Show help message."""
        help_text = """Neo Help

Commands:
  /status  - Show agent status
  /cost    - Show token usage and cost
  /reset   - Clear memory
  /diff    - Show git diff
  /tree    - Refresh file tree
  /help    - Show this help
  /exit    - Quit Neo

Keyboard Shortcuts:
  Ctrl+C   - Quit
  Ctrl+K   - Command Palette
  Ctrl+R   - Refresh Tree
  Ctrl+D   - Show Diff
  Ctrl+G   - Git Status
  Ctrl+/   - Focus Input
"""
        self._add_system_message(help_text)

    def _show_cost(self) -> None:
        """Show cost and token usage report."""
        cost_report = self.llm.format_cost_report()
        self._add_system_message(cost_report)

    def _add_user_message(self, text: str) -> None:
        """Add a user message to the chat.

        Args:
            text: Message text
        """
        msg = ChatMessage(content=text, is_user=True)
        self.messages.append(msg)
        chat = self.query_one("#chat-container", Vertical)

        # Remove welcome message if present
        welcome = chat.query("#welcome-message")
        if welcome:
            for w in welcome:
                w.remove()
        welcome_hint = chat.query("#welcome-hint")
        if welcome_hint:
            for w in welcome_hint:
                w.remove()

        chat.mount(msg)
        chat.scroll_end()

    def _add_assistant_message(self) -> ChatMessage:
        """Add an assistant message (for streaming).

        Returns:
            The chat message widget
        """
        msg = ChatMessage(content="", is_user=False, is_streaming=True)
        self.messages.append(msg)
        self.current_streaming_message = msg
        chat = self.query_one("#chat-container", Vertical)
        chat.mount(msg)
        chat.scroll_end()
        return msg

    def _add_system_message(self, text: str) -> None:
        """Add a system message.

        Args:
            text: Message text
        """
        from textual.widgets import Label
        msg = Label(f"[dim]{text}[/dim]", classes="system-message")
        chat = self.query_one("#chat-container", Vertical)
        chat.mount(msg)
        chat.scroll_end()

    def _update_streaming_message(self, text: str) -> None:
        """Update the currently streaming message.

        Args:
            text: Text to append
        """
        if self.current_streaming_message:
            self.current_streaming_message.content += text
            self.call_later(self.current_streaming_message.refresh)

    def _add_tool_call(self, tool_name: str, inputs: dict[str, Any]) -> None:
        """Add a tool call display to the chat.

        Args:
            tool_name: Name of the tool
            inputs: Tool inputs
        """
        chat = self.query_one("#chat-container", Vertical)
        tool_display = ToolCall(tool_name, inputs)

        # Insert before the current streaming message if it exists
        if self.current_streaming_message:
            chat.mount(tool_display, before=self.current_streaming_message)
        else:
            chat.mount(tool_display)
        chat.scroll_end()

    def _finish_streaming_message(self) -> None:
        """Mark the current message as finished streaming."""
        if self.current_streaming_message:
            self.current_streaming_message.is_streaming = False
            self.current_streaming_message = None

    def _handle_input_submit(self) -> None:
        """Handle input submission."""
        input_area = self.query_one("#input-area", InputArea)
        text = input_area.get_text().strip()

        if not text:
            return

        # Clear input
        input_area.clear()

        # Handle slash commands
        if text.startswith("/"):
            self._handle_command(text[1:].lower())
            return

        # Add user message
        self._add_user_message(text)

        # Run agent
        asyncio.create_task(self._run_agent_query(text))

    async def _run_agent_query(self, query: str) -> None:
        """Run a query through the agent.

        Args:
            query: User query
        """
        # Lock input while processing
        input_area = self.query_one("#input-area", InputArea)
        input_area.set_disabled(True)

        # Update status
        status = self.query_one("#status-bar", StatusBar)
        status.status = "Thinking..."

        # Add streaming message (starts with thinking indicator)
        self.call_later(self._add_assistant_message)

        try:
            # Run the agent with streaming and tool callbacks
            response = await self.agent.run(
                query,
                streaming_callback=self._update_streaming_message,
                tool_callback=lambda name, inputs: self.call_later(
                    lambda: self._add_tool_call(name, inputs)
                ),
            )

            # Update message with final response if streaming didn't populate it
            if self.current_streaming_message and not self.current_streaming_message.content:
                self.current_streaming_message.content = response

            # Finish streaming
            self.call_later(self._finish_streaming_message)

            # Update status
            status.tokens = self.llm.get_token_stats()["total_tokens"]
            status.status = "Ready"

        except Exception as e:
            self.call_later(self._finish_streaming_message)
            self._add_system_message(f"Error: {e}")
            status.status = "Error"

        finally:
            # Re-enable input
            input_area.set_disabled(False)
            input_area.focus_input()

    def on_input_area_submitted(self, event: InputArea.Submitted) -> None:
        """Handle input area submission.

        Args:
            event: Submit event with text
        """
        self._handle_input_submit()

    def on_key(self, event) -> None:
        """Handle key events at app level."""
        pass

    def action_quit(self) -> None:
        """Quit the app."""
        self.exit()


def run_tui(project_path: Path | None = None, config: Config | None = None) -> None:
    """Run the Neo TUI.

    Args:
        project_path: Optional project path
        config: Optional config
    """
    app = NeoApp(project_path=project_path, config=config)
    app.run()
