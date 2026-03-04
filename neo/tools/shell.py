"""Shell execution tool for Neo."""

from __future__ import annotations

import asyncio
import shlex
from pathlib import Path
from typing import Any

from neo.tools.base import BaseTool, ToolResult


class RunShellTool(BaseTool):
    """Execute shell commands with safety checks."""

    name = "run_shell"
    description = """Execute a shell command and return the output.

Safety note: Certain dangerous commands are blocked (rm -rf /, format, etc.).
Commands run in the current working directory.
Timeout is set to 60 seconds by default."""
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 60)",
                "default": 60,
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for command (default: current directory)",
            },
        },
        "required": ["command"],
    }

    # Dangerous commands that are blocked
    BLOCKED_COMMANDS = [
        "rm -rf /",
        "rm -rf /*",
        "rm -rf ~",
        "format",
        "mkfs",
        "dd if=/dev/zero",
        ":(){ :|:& };:",  # Fork bomb
    ]

    async def execute(
        self,
        command: str,
        timeout: int | str = 60,
        cwd: str | None = None,
    ) -> ToolResult:
        """Execute a shell command with safety checks."""
        try:
            # Convert parameters if needed
            timeout = int(timeout) if isinstance(timeout, str) else timeout
            # Safety check
            for blocked in self.BLOCKED_COMMANDS:
                if blocked in command:
                    return ToolResult(
                        success=False,
                        error=f"Command blocked for safety: contains '{blocked}'",
                    )

            # Prepare working directory
            work_dir = Path(cwd).expanduser().resolve() if cwd else Path.cwd()

            if not work_dir.exists():
                return ToolResult(
                    success=False,
                    error=f"Working directory not found: {cwd}",
                )

            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(
                    success=False,
                    error=f"Command timed out after {timeout} seconds",
                )

            # Decode output
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # Build output
            output_parts = []
            if stdout_str:
                output_parts.append(f"STDOUT:\n{stdout_str}")
            if stderr_str:
                output_parts.append(f"STDERR:\n{stderr_str}")

            output = "\n\n".join(output_parts) if output_parts else "(no output)"

            return ToolResult(
                success=process.returncode == 0,
                output=output,
                error=stderr_str if process.returncode != 0 else None,
                data={
                    "command": command,
                    "return_code": process.returncode,
                    "cwd": str(work_dir),
                    "stdout_length": len(stdout_str),
                    "stderr_length": len(stderr_str),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error executing command: {str(e)}",
            )
