"""Textual widgets for Neo TUI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, Static, TextArea, Tree
from textual.widgets.tree import TreeNode


class ChatMessage(Static):
    """A chat message widget with markdown and code support."""

    content = reactive("")
    is_user = reactive(False)
    is_streaming = reactive(False)

    def __init__(self, content: str = "", is_user: bool = False, is_streaming: bool = False, **kwargs: Any):
        """Initialize chat message.

        Args:
            content: Message content
            is_user: Whether this is a user message
            is_streaming: Whether message is streaming
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self.content = content
        self.is_user = is_user
        self.is_streaming = is_streaming

    def on_mount(self) -> None:
        """Compose the widget."""
        self.update_content()

    def watch_content(self, content: str) -> None:
        """React to content changes."""
        self.update_content()

    def watch_is_streaming(self, is_streaming: bool) -> None:
        """React to streaming state changes."""
        self.update_content()

    def update_content(self) -> None:
        """Update the displayed content."""
        if not self.content:
            return

        # Create styled text
        if self.is_user:
            # User messages - simple, right-aligned
            style = "bold cyan"
            title = "You"
            border_style = "cyan"
        else:
            # Assistant messages
            style = ""
            title = "Neo"
            border_style = "green"

        # Add streaming indicator
        if self.is_streaming:
            title += " [dim](typing...)[/dim]"

        # Render with panel
        renderable = Text.from_markup(self.content)
        panel = Panel(
            renderable,
            title=title,
            border_style=border_style,
            title_align="left",
        )
        self.update(panel)

    def append_text(self, text: str) -> None:
        """Append text to the message (for streaming).

        Args:
            text: Text to append
        """
        self.content += text
        self.refresh()

    def set_streaming(self, streaming: bool) -> None:
        """Set streaming state.

        Args:
            streaming: Whether streaming is active
        """
        self.is_streaming = streaming


class CodeView(Static):
    """A widget for displaying code with syntax highlighting."""

    code = reactive("")
    language = reactive("python")
    filepath = reactive("")

    def __init__(
        self,
        code: str = "",
        language: str = "python",
        filepath: str = "",
        **kwargs: Any,
    ):
        """Initialize code view.

        Args:
            code: Code content
            language: Language for syntax highlighting
            filepath: File path for context
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self.code = code
        self.language = language
        self.filepath = filepath

    def watch_code(self, code: str) -> None:
        """React to code changes."""
        self.update_display()

    def update_display(self) -> None:
        """Update the displayed code."""
        if not self.code:
            self.update("[dim]No code to display[/dim]")
            return

        # Create syntax highlighted display
        syntax = Syntax(
            self.code,
            self.language,
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
        )

        # Wrap in panel with file info
        title = self.filepath or f"Code ({self.language})"
        panel = Panel(syntax, title=title, border_style="blue")
        self.update(panel)

    def set_code(self, code: str, language: str | None = None, filepath: str | None = None) -> None:
        """Set the code to display.

        Args:
            code: Code content
            language: Optional language override
            filepath: Optional filepath override
        """
        self.code = code
        if language:
            self.language = language
        if filepath:
            self.filepath = filepath
        self.update_display()

    @staticmethod
    def detect_language(filepath: str) -> str:
        """Detect language from file extension.

        Args:
            filepath: Path to file

        Returns:
            Language name for syntax highlighting
        """
        ext = Path(filepath).suffix.lower()
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".sh": "bash",
            ".md": "markdown",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".html": "html",
            ".css": "css",
        }
        return mapping.get(ext, "text")


class DiffView(Static):
    """A widget for displaying unified diffs."""

    diff_text = reactive("")

    def __init__(self, diff_text: str = "", **kwargs: Any):
        """Initialize diff view.

        Args:
            diff_text: Unified diff text
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self.diff_text = diff_text

    def watch_diff_text(self, diff_text: str) -> None:
        """React to diff changes."""
        self.update_display()

    def update_display(self) -> None:
        """Update the displayed diff."""
        if not self.diff_text:
            self.update("[dim]No diff to display[/dim]")
            return

        # Colorize the diff
        lines = self.diff_text.split("\n")
        colored_lines = []

        for line in lines:
            if line.startswith("+") and not line.startswith("+++"):
                colored_lines.append(f"[green]{line}[/green]")
            elif line.startswith("-") and not line.startswith("---"):
                colored_lines.append(f"[red]{line}[/red]")
            elif line.startswith("@@"):
                colored_lines.append(f"[cyan]{line}[/cyan]")
            elif line.startswith("diff --git"):
                colored_lines.append(f"[bold]{line}[/bold]")
            else:
                colored_lines.append(line)

        display = "\n".join(colored_lines)
        panel = Panel(display, title="Diff", border_style="yellow")
        self.update(panel)

    def set_diff(self, diff_text: str) -> None:
        """Set the diff to display.

        Args:
            diff_text: Unified diff text
        """
        self.diff_text = diff_text
        self.update_display()


class FileTree(Tree):
    """A file tree widget with git status support."""

    def __init__(self, root_path: str | Path, **kwargs: Any):
        """Initialize file tree.

        Args:
            root_path: Root directory path
            **kwargs: Additional widget arguments
        """
        self.root_path = Path(root_path)
        super().__init__(self.root_path.name, **kwargs)
        self.auto_expand = False

    def on_mount(self) -> None:
        """Build tree when mounted."""
        self.build_tree()

    def build_tree(self) -> None:
        """Build the file tree from root path."""
        self.clear()
        self.root.set_label(f"📁 {self.root_path.name}")
        self._add_directory(self.root, self.root_path)

    def _add_directory(self, parent: TreeNode, path: Path) -> None:
        """Recursively add directory contents.

        Args:
            parent: Parent tree node
            path: Directory path
        """
        try:
            items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))

            for item in items:
                if item.is_dir():
                    # Skip hidden and common ignore directories
                    if item.name.startswith(".") or item.name in [
                        "__pycache__", "node_modules", "venv", ".git",
                        "dist", "build", ".pytest_cache", ".mypy_cache",
                    ]:
                        continue

                    node = parent.add(f"📁 {item.name}")
                    self._add_directory(node, item)
                else:
                    # Skip hidden files
                    if item.name.startswith("."):
                        continue

                    # Get icon based on extension
                    icon = self._get_file_icon(item.name)
                    parent.add(f"{icon} {item.name}")

        except PermissionError:
            parent.add("[dim](permission denied)[/dim]")

    def _get_file_icon(self, filename: str) -> str:
        """Get appropriate icon for file type.

        Args:
            filename: Name of file

        Returns:
            Icon emoji
        """
        ext = Path(filename).suffix.lower()
        icons = {
            ".py": "🐍",
            ".js": "📜",
            ".ts": "📘",
            ".tsx": "⚛️",
            ".jsx": "⚛️",
            ".go": "🔵",
            ".rs": "🦀",
            ".java": "☕",
            ".c": "🔧",
            ".cpp": "🔧",
            ".h": "📋",
            ".hpp": "📋",
            ".md": "📝",
            ".txt": "📄",
            ".json": "📦",
            ".yaml": "⚙️",
            ".yml": "⚙️",
            ".toml": "⚙️",
            ".html": "🌐",
            ".css": "🎨",
            ".sh": "🔨",
        }
        return icons.get(ext, "📄")

    def refresh_tree(self) -> None:
        """Refresh the tree from disk."""
        self.build_tree()

    def get_selected_path(self) -> Path | None:
        """Get the full path of the selected node.

        Returns:
            Full path or None if no selection
        """
        if not self.cursor_node:
            return None

        # Build path from node labels
        parts = []
        node = self.cursor_node
        while node:
            label = str(node.label)
            # Remove icon
            if " " in label:
                parts.insert(0, label.split(" ", 1)[1])
            else:
                parts.insert(0, label)
            node = node.parent

        if not parts:
            return None

        return self.root_path / "/".join(parts[1:]) if len(parts) > 1 else self.root_path


class StatusBar(Static):
    """Status bar showing agent state."""

    model = reactive("")
    tokens = reactive(0)
    status = reactive("Ready")
    git_branch = reactive("")

    def __init__(self, **kwargs: Any):
        """Initialize status bar."""
        super().__init__(**kwargs)

    def watch_model(self, model: str) -> None:
        """Update when model changes."""
        self.update_display()

    def watch_tokens(self, tokens: int) -> None:
        """Update when tokens change."""
        self.update_display()

    def watch_status(self, status: str) -> None:
        """Update when status changes."""
        self.update_display()

    def watch_git_branch(self, branch: str) -> None:
        """Update when branch changes."""
        self.update_display()

    def update_display(self) -> None:
        """Update the status display."""
        parts = []

        # Model indicator
        if self.model:
            parts.append(f"🤖 {self.model}")

        # Token count
        if self.tokens:
            parts.append(f"📊 {self.tokens:,} tokens")

        # Status
        if self.status:
            parts.append(f"● {self.status}")

        # Git branch
        if self.git_branch:
            parts.append(f"🌿 {self.git_branch}")

        text = " | ".join(parts) if parts else "Neo Ready"
        self.update(Text(text, style="bold white on blue"))

    def set_status(self, status: str) -> None:
        """Set the status message.

        Args:
            status: Status text
        """
        self.status = status


class _SubmitTextArea(TextArea):
    """TextArea that submits on Enter."""

    def __init__(self, **kwargs):
        self._parent_widget = None
        super().__init__(**kwargs)

    def _on_key(self, event) -> None:
        """Handle key press."""
        if event.key == "enter":
            # Submit on Enter (Shift+Enter would be "shift+enter")
            event.stop()
            if self._parent_widget:
                self._parent_widget.post_message(
                    self._parent_widget.Submitted(self._parent_widget, self.text)
                )
        else:
            super()._on_key(event)


class InputArea(Static):
    """Enhanced input area with multi-line support."""

    placeholder = reactive("Type your message... (Enter to submit)")

    def __init__(self, **kwargs: Any):
        """Initialize input area."""
        super().__init__(**kwargs)

    def compose(self):
        """Compose the widget."""
        # Use custom TextArea that submits on Enter
        self.text_area = _SubmitTextArea(
            text="",
            show_line_numbers=False,
        )
        self.text_area._parent_widget = self
        self.text_area.placeholder = self.placeholder
        yield self.text_area

    def on_mount(self) -> None:
        """Handle mount."""
        self.text_area.focus()

    def get_text(self) -> str:
        """Get current input text.

        Returns:
            Input text
        """
        return self.text_area.text

    def clear(self) -> None:
        """Clear the input."""
        self.text_area.text = ""

    def focus_input(self) -> None:
        """Focus the input area."""
        self.text_area.focus()

    class Submitted(Message):
        """Message sent when input is submitted."""

        def __init__(self, sender: InputArea, text: str) -> None:
            """Initialize submitted message.

            Args:
                sender: The InputArea that sent the message
                text: The submitted text
            """
            self.text = text
            super().__init__()
