"""Textual TUI for Neo - Rich terminal interface.

This module provides a modern terminal UI for Neo using Textual:
- Split-pane layout with file tree and chat
- Streaming response display
- Syntax highlighted code viewing
- Interactive diff viewing
- Command palette
"""

from neo.tui.app import NeoApp
from neo.tui.widgets import ChatMessage, CodeView, DiffView, FileTree, InputArea, ToolCall

__all__ = [
    "NeoApp",
    "ChatMessage",
    "CodeView",
    "DiffView",
    "FileTree",
    "InputArea",
    "ToolCall",
]
