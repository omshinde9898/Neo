"""Git operation tools for Neo."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from neo.tools.base import BaseTool, ToolResult


class GitStatusTool(BaseTool):
    """Get git repository status."""

    name = "git_status"
    description = "Show git status."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Repository path", "default": "."},
        },
        "required": [],
    }

    async def _execute_impl(self, path: str = ".") -> ToolResult:
        """Get git status."""
        try:
            repo_path = Path(path).expanduser().resolve()

            if not (repo_path / ".git").exists():
                return ToolResult(
                    success=False,
                    error=f"Not a git repository: {path}",
                )

            result = await self._run_git_command("status --porcelain -b", repo_path)

            if not result.success:
                return result

            # Parse porcelain output
            lines = result.output.strip().split("\n") if result.output.strip() else []

            branch_line = ""
            staged = []
            unstaged = []
            untracked = []

            for line in lines:
                if line.startswith("##"):
                    branch_line = line[3:]
                elif line.startswith("??"):
                    untracked.append(line[3:])
                elif line.startswith(" M") or line.startswith(" D"):
                    unstaged.append(line[3:])
                elif line.startswith("M ") or line.startswith("D ") or line.startswith("A "):
                    staged.append(line[3:])
                elif line.startswith("MM"):
                    staged.append(line[3:] + " (partial)")
                    unstaged.append(line[3:] + " (partial)")

            # Build formatted output
            output_parts = [f"Branch: {branch_line}"]

            if staged:
                output_parts.append("\nStaged changes:")
                for f in staged:
                    output_parts.append(f"  + {f}")

            if unstaged:
                output_parts.append("\nUnstaged changes:")
                for f in unstaged:
                    output_parts.append(f"  ~ {f}")

            if untracked:
                output_parts.append("\nUntracked files:")
                for f in untracked:
                    output_parts.append(f"  ? {f}")

            if not any([staged, unstaged, untracked]):
                output_parts.append("\nWorking tree clean")

            return ToolResult(
                success=True,
                output="\n".join(output_parts),
                data={
                    "path": str(repo_path),
                    "branch": branch_line,
                    "staged": staged,
                    "unstaged": unstaged,
                    "untracked": untracked,
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error getting git status: {str(e)}",
            )

    async def _run_git_command(self, command: str, cwd: Path) -> ToolResult:
        """Run a git command."""
        full_command = f"git {command}"

        process = await asyncio.create_subprocess_shell(
            full_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        stdout, stderr = await process.communicate()

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        return ToolResult(
            success=process.returncode == 0,
            output=stdout_str,
            error=stderr_str if process.returncode != 0 else None,
        )


class GitDiffTool(BaseTool):
    """Show git diff."""

    name = "git_diff"
    description = "Show git diff."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Repository path", "default": "."},
            "file": {"type": "string", "description": "Specific file"},
            "staged": {"type": "boolean", "description": "Show staged changes", "default": False},
        },
        "required": [],
    }

    async def _execute_impl(
        self,
        path: str = ".",
        file: str | None = None,
        staged: bool = False,
    ) -> ToolResult:
        """Show git diff."""
        try:
            repo_path = Path(path).expanduser().resolve()

            if not (repo_path / ".git").exists():
                return ToolResult(
                    success=False,
                    error=f"Not a git repository: {path}",
                )

            # Build command
            cmd = "diff --cached" if staged else "diff"
            if file:
                cmd += f" -- {file}"

            result = await self._run_git_command(cmd, repo_path)
            return result

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error getting git diff: {str(e)}",
            )

    async def _run_git_command(self, command: str, cwd: Path) -> ToolResult:
        """Run a git command."""
        full_command = f"git {command}"

        process = await asyncio.create_subprocess_shell(
            full_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        stdout, stderr = await process.communicate()

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        return ToolResult(
            success=process.returncode == 0,
            output=stdout_str if stdout_str else "(no changes)",
            error=stderr_str if process.returncode != 0 else None,
        )


class GitAddTool(BaseTool):
    """Stage files for commit."""

    name = "git_add"
    description = "Stage files (git add)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Repository path", "default": "."},
            "files": {"type": "array", "items": {"type": "string"}, "description": "Files to stage"},
        },
        "required": [],
    }

    async def _execute_impl(
        self,
        path: str = ".",
        files: list[str] | None = None,
    ) -> ToolResult:
        """Stage files."""
        try:
            repo_path = Path(path).expanduser().resolve()

            if not (repo_path / ".git").exists():
                return ToolResult(
                    success=False,
                    error=f"Not a git repository: {path}",
                )

            # Build command
            file_args = " ".join(f'"{f}"' for f in files) if files else "."
            cmd = f"add {file_args}"

            result = await self._run_git_command(cmd, repo_path)

            if result.success:
                result.output = f"Staged: {file_args}"

            return result

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error staging files: {str(e)}",
            )

    async def _run_git_command(self, command: str, cwd: Path) -> ToolResult:
        """Run a git command."""
        full_command = f"git {command}"

        process = await asyncio.create_subprocess_shell(
            full_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        stdout, stderr = await process.communicate()

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        return ToolResult(
            success=process.returncode == 0,
            output=stdout_str,
            error=stderr_str if process.returncode != 0 else None,
        )


class GitCommitTool(BaseTool):
    """Commit staged changes."""

    name = "git_commit"
    description = "Commit changes."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Repository path", "default": "."},
            "message": {"type": "string", "description": "Commit message"},
            "add_all": {"type": "boolean", "description": "Stage all first", "default": False},
        },
        "required": ["message"],
    }

    async def _execute_impl(
        self,
        message: str,
        path: str = ".",
        add_all: bool = False,
    ) -> ToolResult:
        """Commit changes."""
        try:
            repo_path = Path(path).expanduser().resolve()

            if not (repo_path / ".git").exists():
                return ToolResult(
                    success=False,
                    error=f"Not a git repository: {path}",
                )

            # Build command
            flags = "-a" if add_all else ""
            cmd = f'commit {flags} -m "{message}"'

            result = await self._run_git_command(cmd, repo_path)

            if result.success:
                # Get the commit hash
                hash_result = await self._run_git_command("rev-parse --short HEAD", repo_path)
                commit_hash = hash_result.output.strip() if hash_result.success else "unknown"
                result.output = f"Committed: {commit_hash} - {message}"

            return result

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error committing: {str(e)}",
            )

    async def _run_git_command(self, command: str, cwd: Path) -> ToolResult:
        """Run a git command."""
        full_command = f"git {command}"

        process = await asyncio.create_subprocess_shell(
            full_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        stdout, stderr = await process.communicate()

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        return ToolResult(
            success=process.returncode == 0,
            output=stdout_str,
            error=stderr_str if process.returncode != 0 else None,
        )


class GitLogTool(BaseTool):
    """Show commit history."""

    name = "git_log"
    description = "Show commit history."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Repository path", "default": "."},
            "count": {"type": "integer", "description": "Number of commits", "default": 10},
            "oneline": {"type": "boolean", "description": "One line per commit", "default": True},
        },
        "required": [],
    }

    async def _execute_impl(
        self,
        path: str = ".",
        count: int | str = 10,
        oneline: bool | str = True,
    ) -> ToolResult:
        """Show git log."""
        try:
            # Convert parameters if needed
            count = int(count) if isinstance(count, str) else count
            if isinstance(oneline, str):
                oneline = oneline.lower() in ("true", "1", "yes")

            repo_path = Path(path).expanduser().resolve()

            if not (repo_path / ".git").exists():
                return ToolResult(
                    success=False,
                    error=f"Not a git repository: {path}",
                )

            # Build command
            format_flag = "--oneline" if oneline else ""
            cmd = f"log {format_flag} -n {count}"

            result = await self._run_git_command(cmd, repo_path)
            return result

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error getting git log: {str(e)}",
            )

    async def _run_git_command(self, command: str, cwd: Path) -> ToolResult:
        """Run a git command."""
        full_command = f"git {command}"

        process = await asyncio.create_subprocess_shell(
            full_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        stdout, stderr = await process.communicate()

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        return ToolResult(
            success=process.returncode == 0,
            output=stdout_str,
            error=stderr_str if process.returncode != 0 else None,
        )
