"""System information tools for Neo."""

from __future__ import annotations

import os
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from neo.tools.base import BaseTool, ToolResult


class GetSystemInfoTool(BaseTool):
    """Get system information."""

    name = "get_system_info"
    description = "Get system info."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def execute(self) -> ToolResult:
        """Get system information."""
        try:
            info = {
                "os": platform.system(),
                "os_version": platform.version(),
                "platform": platform.platform(),
                "architecture": platform.machine(),
                "python_version": sys.version,
                "python_executable": sys.executable,
                "current_time": datetime.now().isoformat(),
                "working_directory": str(Path.cwd()),
                "home_directory": str(Path.home()),
                "cpu_count": os.cpu_count(),
            }

            # Build output
            output_lines = [
                "System Information:",
                "=" * 40,
                f"OS: {info['os']} {info['architecture']}",
                f"Platform: {info['platform']}",
                f"Python: {info['python_version'].split()[0]}",
                f"Time: {info['current_time']}",
                f"Working Directory: {info['working_directory']}",
                f"CPUs: {info['cpu_count']}",
            ]

            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                data=info,
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error getting system info: {str(e)}",
            )
