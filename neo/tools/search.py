"""Search tools for Neo."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from neo.tools.base import BaseTool, ToolResult


class SearchCodeTool(BaseTool):
    """Search for code patterns using regex."""

    name = "search_code"
    description = "Search for text patterns in files using regex. Searches file contents and returns matching lines with context."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: current directory)",
                "default": ".",
            },
            "glob": {
                "type": "string",
                "description": "File pattern to search (e.g., '*.py', default: all files)",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Case sensitive search (default: false)",
                "default": False,
            },
        },
        "required": ["pattern"],
    }

    async def execute(
        self,
        pattern: str,
        path: str = ".",
        glob: str | None = None,
        case_sensitive: bool = False,
    ) -> ToolResult:
        """Search for code patterns."""
        try:
            search_path = Path(path).expanduser().resolve()

            if not search_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Path not found: {path}",
                )

            # Compile regex
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                compiled_pattern = re.compile(pattern, flags)
            except re.error as e:
                return ToolResult(
                    success=False,
                    error=f"Invalid regex pattern: {e}",
                )

            # Find files to search
            if glob:
                files = list(search_path.rglob(glob))
            else:
                files = [
                    f for f in search_path.rglob("*")
                    if f.is_file() and not self._is_binary(f)
                ]

            # Search files
            matches = []
            for file_path in files:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()

                    for i, line in enumerate(lines, 1):
                        if compiled_pattern.search(line):
                            rel_path = file_path.relative_to(search_path)
                            matches.append({
                                "file": str(rel_path),
                                "line": i,
                                "content": line[:200],  # Limit line length
                            })
                except Exception:
                    # Skip files that can't be read
                    continue

            # Format output
            if not matches:
                return ToolResult(
                    success=True,
                    output=f"No matches found for pattern: {pattern}",
                    data={"pattern": pattern, "matches": []},
                )

            output_lines = [f"Found {len(matches)} match(es):\n"]
            for m in matches[:50]:  # Limit output
                output_lines.append(f"{m['file']}:{m['line']} | {m['content']}")

            if len(matches) > 50:
                output_lines.append(f"\n... and {len(matches) - 50} more matches")

            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                data={
                    "pattern": pattern,
                    "matches": matches,
                    "total_matches": len(matches),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error searching code: {str(e)}",
            )

    def _is_binary(self, file_path: Path) -> bool:
        """Check if a file is binary."""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                return b"\0" in chunk
        except Exception:
            return True


class ViewCodeTool(BaseTool):
    """View code with context and syntax highlighting."""

    name = "view"
    description = "View a file with line numbers and optional context around a specific line. Useful for examining code structure."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to view",
            },
            "line": {
                "type": "integer",
                "description": "Line number to center on (optional)",
            },
            "context": {
                "type": "integer",
                "description": "Number of context lines to show (default: 10)",
                "default": 10,
            },
        },
        "required": ["file_path"],
    }

    async def execute(
        self,
        file_path: str,
        line: int | str | None = None,
        context: int | str = 10,
    ) -> ToolResult:
        """View file with line numbers and context."""
        try:
            # Convert parameters to integers if needed
            if line is not None and isinstance(line, str):
                line = int(line)
            if isinstance(context, str):
                context = int(context)

            path = Path(file_path).expanduser().resolve()

            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f"File not found: {file_path}",
                )

            if not path.is_file():
                return ToolResult(
                    success=False,
                    error=f"Path is not a file: {file_path}",
                )

            # Read file
            content = path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            total_lines = len(lines)

            # Determine range to show
            if line is not None:
                center = max(1, min(line, total_lines))
                start = max(0, center - context - 1)
                end = min(total_lines, center + context)
            else:
                start = 0
                end = min(total_lines, context * 2)

            # Format with line numbers
            output_lines = [f"File: {path.name} ({total_lines} lines)\n"]

            for i in range(start, end):
                line_num = i + 1
                prefix = ">>> " if line and line_num == line else "    "
                output_lines.append(f"{prefix}{line_num:4d} | {lines[i]}")

            if end < total_lines:
                output_lines.append(f"\n... ({total_lines - end} more lines)")

            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                data={
                    "file_path": str(path),
                    "total_lines": total_lines,
                    "start_line": start + 1,
                    "end_line": end,
                    "shown_lines": end - start,
                },
            )

        except PermissionError:
            return ToolResult(
                success=False,
                error=f"Permission denied: {file_path}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error viewing file: {str(e)}",
            )
