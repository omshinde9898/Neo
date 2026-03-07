"""File operation tools for Neo."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from neo.tools.base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """Read file contents with optional offset and limit."""

    name = "read_file"
    description = "Read a file. Use offset and limit for large files."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to file"},
            "offset": {"type": "integer", "description": "Start line (1-indexed)", "default": 1},
            "limit": {"type": "integer", "description": "Max lines to read", "default": 200},
        },
        "required": ["file_path"],
    }

    async def _execute_impl(
        self,
        file_path: str,
        offset: int | str = 1,
        limit: int | str = 200,
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
    description = "Write content to a file."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to file"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["file_path", "content"],
    }

    async def _execute_impl(self, file_path: str, content: str) -> ToolResult:
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
    description = "Edit a file by replacing text."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to file"},
            "old_string": {"type": "string", "description": "Text to replace"},
            "new_string": {"type": "string", "description": "Replacement text"},
            "replace_all": {"type": "boolean", "description": "Replace all occurrences", "default": False},
        },
        "required": ["file_path", "old_string", "new_string"],
    }

    async def _execute_impl(
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

            # Limit diff output size
            MAX_DIFF = 1000
            diff_output = diff_str[:MAX_DIFF]
            if len(diff_str) > MAX_DIFF:
                diff_output += f"\n... ({len(diff_str) - MAX_DIFF} chars truncated)"

            return ToolResult(
                success=True,
                output=f"Edited {path}\n\nDiff:\n{diff_output}",
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
    description = "List directory contents."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path", "default": "."},
            "recursive": {"type": "boolean", "description": "List recursively", "default": False},
        },
        "required": [],
    }

    async def _execute_impl(self, path: str = ".", recursive: bool = False) -> ToolResult:
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
    description = "Search for files matching a glob pattern."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern (e.g., '*.py')"},
            "path": {"type": "string", "description": "Base directory", "default": "."},
        },
        "required": ["pattern"],
    }

    async def _execute_impl(self, pattern: str, path: str = ".") -> ToolResult:
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


class GrepTool(BaseTool):
    """Search file contents using regex (like grep)."""

    name = "Grep"
    description = "Search for patterns in file contents using regex. Fast way to find code."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search for"},
            "path": {"type": "string", "description": "Directory to search in", "default": "."},
            "glob": {"type": "string", "description": "File pattern filter (e.g., '*.py')"},
        },
        "required": ["pattern"],
    }

    async def _execute_impl(
        self,
        pattern: str,
        path: str = ".",
        glob: str | None = None,
    ) -> ToolResult:
        """Search file contents using regex."""
        import re

        try:
            search_path = Path(path).expanduser().resolve()

            if not search_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Path not found: {path}",
                )

            # Compile regex
            try:
                compiled_pattern = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                return ToolResult(
                    success=False,
                    error=f"Invalid regex pattern: {e}",
                )

            # Find files to search
            if glob:
                files = [f for f in search_path.rglob(glob) if f.is_file()]
            else:
                files = [
                    f for f in search_path.rglob("*")
                    if f.is_file() and not self._is_binary(f)
                ]

            # Search files
            matches = []
            for file_path in files:
                # Skip common non-source directories
                if any(part.startswith('.') or part in {'venv', 'node_modules', '__pycache__', 'dist', 'build'}
                       for part in file_path.parts):
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()

                    for i, line in enumerate(lines, 1):
                        if compiled_pattern.search(line):
                            rel_path = file_path.relative_to(search_path)
                            matches.append({
                                "file": str(rel_path),
                                "line": i,
                                "content": line[:150].strip(),
                            })
                except Exception:
                    continue

            # Format output
            if not matches:
                return ToolResult(
                    success=True,
                    output=f"No matches found for: {pattern}",
                    data={"pattern": pattern, "matches": []},
                )

            output_lines = [f"Found {len(matches)} match(es) for '{pattern}':\n"]
            for m in matches[:30]:  # Limit output
                output_lines.append(f"{m['file']}:{m['line']} | {m['content']}")

            if len(matches) > 30:
                output_lines.append(f"\n... and {len(matches) - 30} more matches")

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
                error=f"Error searching: {str(e)}",
            )

    def _is_binary(self, file_path: Path) -> bool:
        """Check if a file is binary."""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                return b"\0" in chunk
        except Exception:
            return True
