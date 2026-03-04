"""File operation tools for Neo."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from neo.tools.base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """Read file contents with optional offset and limit."""

    name = "read_file"
    description = "Read contents of a file. Returns the file content as a string. Use offset and limit to read specific portions of large files."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to read (absolute or relative to current directory)",
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-indexed)",
                "default": 1,
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read",
                "default": 100,
            },
        },
        "required": ["file_path"],
    }

    async def execute(
        self,
        file_path: str,
        offset: int | str = 1,
        limit: int | str = 100,
    ) -> ToolResult:
        """Read a file with optional offset and line limit."""
        try:
            # Convert parameters to integers if needed
            offset = int(offset) if isinstance(offset, str) else offset
            limit = int(limit) if isinstance(limit, str) else limit

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

            # Read file content
            content = path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            total_lines = len(lines)

            # Adjust offset to 0-indexed
            start_idx = max(0, offset - 1)
            end_idx = min(total_lines, start_idx + limit)

            # Get requested lines
            selected_lines = lines[start_idx:end_idx]

            # Format with line numbers
            numbered_lines = []
            for i, line in enumerate(selected_lines, start=start_idx + 1):
                numbered_lines.append(f"{i:4d} | {line}")

            result_content = "\n".join(numbered_lines)

            # Add truncation notice if applicable
            if end_idx < total_lines:
                result_content += f"\n\n... ({total_lines - end_idx} more lines)"

            return ToolResult(
                success=True,
                output=result_content,
                data={
                    "file_path": str(path),
                    "total_lines": total_lines,
                    "start_line": start_idx + 1,
                    "end_line": end_idx,
                    "bytes": path.stat().st_size,
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
                error=f"Error reading file: {str(e)}",
            )


class WriteFileTool(BaseTool):
    """Write content to a file atomically with backup."""

    name = "write_file"
    description = "Write content to a file. Creates parent directories if needed. If the file exists, creates a backup with .neo.bak extension before overwriting."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["file_path", "content"],
    }

    async def execute(self, file_path: str, content: str) -> ToolResult:
        """Write file with atomic operation and backup."""
        try:
            path = Path(file_path).expanduser().resolve()

            # Create parent directories
            path.parent.mkdir(parents=True, exist_ok=True)

            # Create backup if file exists
            backup_created = False
            if path.exists():
                backup_path = path.with_suffix(path.suffix + ".neo.bak")
                shutil.copy2(path, backup_path)
                backup_created = True

            # Atomic write using temp file
            temp_path = path.with_suffix(path.suffix + ".neo.tmp")
            temp_path.write_text(content, encoding="utf-8")
            temp_path.rename(path)

            return ToolResult(
                success=True,
                output=f"Wrote {path}",
                data={
                    "file_path": str(path),
                    "bytes_written": len(content.encode("utf-8")),
                    "backup_created": backup_created,
                    "backup_path": str(backup_path) if backup_created else None,
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
                error=f"Error writing file: {str(e)}",
            )


class EditFileTool(BaseTool):
    """Edit a file by replacing text."""

    name = "edit_file"
    description = "Edit a file by replacing old_string with new_string. Shows a diff preview of the changes. Only replaces the first occurrence unless replace_all is true."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to edit",
            },
            "old_string": {
                "type": "string",
                "description": "Text to replace",
            },
            "new_string": {
                "type": "string",
                "description": "Text to replace with",
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences instead of just the first",
                "default": False,
            },
        },
        "required": ["file_path", "old_string", "new_string"],
    }

    async def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> ToolResult:
        """Edit a file by replacing text."""
        try:
            path = Path(file_path).expanduser().resolve()

            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f"File not found: {file_path}",
                )

            # Read original content
            original_content = path.read_text(encoding="utf-8", errors="replace")

            # Check if old_string exists
            if old_string not in original_content:
                return ToolResult(
                    success=False,
                    error=f"String not found in file: {old_string[:50]}...",
                )

            # Count occurrences
            occurrences = original_content.count(old_string)

            # Create backup
            backup_path = path.with_suffix(path.suffix + ".neo.bak")
            shutil.copy2(path, backup_path)

            # Replace
            if replace_all:
                new_content = original_content.replace(old_string, new_string)
            else:
                new_content = original_content.replace(old_string, new_string, 1)

            # Write atomically
            temp_path = path.with_suffix(path.suffix + ".neo.tmp")
            temp_path.write_text(new_content, encoding="utf-8")
            temp_path.rename(path)

            # Generate diff preview
            from difflib import unified_diff

            original_lines = original_content.splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)

            diff = list(
                unified_diff(
                    original_lines,
                    new_lines,
                    fromfile=f"a/{path.name}",
                    tofile=f"b/{path.name}",
                )
            )

            diff_str = "".join(diff)

            return ToolResult(
                success=True,
                output=f"Edited {path}\n\nDiff:\n{diff_str}",
                data={
                    "file_path": str(path),
                    "occurrences_replaced": occurrences if replace_all else 1,
                    "total_occurrences": occurrences,
                    "diff": diff_str,
                    "backup_path": str(backup_path),
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
                error=f"Error editing file: {str(e)}",
            )


class ListDirTool(BaseTool):
    """List directory contents."""

    name = "list_dir"
    description = "List the contents of a directory. Shows files and subdirectories with their types and sizes."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the directory to list (default: current directory)",
            },
            "recursive": {
                "type": "boolean",
                "description": "List recursively",
                "default": False,
            },
        },
        "required": [],
    }

    async def execute(self, path: str = ".", recursive: bool = False) -> ToolResult:
        """List directory contents."""
        try:
            dir_path = Path(path).expanduser().resolve()

            if not dir_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Directory not found: {path}",
                )

            if not dir_path.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Path is not a directory: {path}",
                )

            entries = []

            if recursive:
                for item in sorted(dir_path.rglob("*")):
                    rel_path = item.relative_to(dir_path)
                    if item.is_dir():
                        entries.append(f"[DIR]  {rel_path}/")
                    else:
                        size = item.stat().st_size
                        entries.append(f"[FILE] {rel_path} ({self._format_size(size)})")
            else:
                for item in sorted(dir_path.iterdir()):
                    if item.is_dir():
                        entries.append(f"[DIR]  {item.name}/")
                    else:
                        size = item.stat().st_size
                        entries.append(f"[FILE] {item.name} ({self._format_size(size)})")

            return ToolResult(
                success=True,
                output="\n".join(entries) if entries else "(empty directory)",
                data={
                    "path": str(dir_path),
                    "entries": len(entries),
                    "recursive": recursive,
                },
            )

        except PermissionError:
            return ToolResult(
                success=False,
                error=f"Permission denied: {path}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error listing directory: {str(e)}",
            )

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable form."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class GlobTool(BaseTool):
    """Search for files matching a pattern."""

    name = "glob"
    description = "Search for files matching a glob pattern (e.g., '*.py', 'src/**/*.js'). Returns a list of matching file paths."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match (e.g., '*.py', 'src/**/*.js')",
            },
            "path": {
                "type": "string",
                "description": "Base directory for search (default: current directory)",
                "default": ".",
            },
        },
        "required": ["pattern"],
    }

    async def execute(self, pattern: str, path: str = ".") -> ToolResult:
        """Search for files matching a glob pattern."""
        try:
            base_path = Path(path).expanduser().resolve()

            if not base_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Directory not found: {path}",
                )

            matches = list(base_path.glob(pattern))
            matches.sort()

            # Filter to files only (optional, can be configured)
            file_matches = [m for m in matches if m.is_file()]

            output_lines = [str(m.relative_to(base_path)) for m in file_matches]

            return ToolResult(
                success=True,
                output="\n".join(output_lines) if output_lines else "No matches found",
                data={
                    "pattern": pattern,
                    "path": str(base_path),
                    "matches": [str(m) for m in file_matches],
                    "count": len(file_matches),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error searching pattern: {str(e)}",
            )
