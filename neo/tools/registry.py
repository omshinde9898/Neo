"""Tool registry for managing and executing tools."""

from __future__ import annotations

from typing import Any

from neo.tools.base import BaseTool, ToolResult
from neo.logger import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool in the registry."""
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered, overwriting")
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry."""
        if name in self._tools:
            del self._tools[name]
            logger.debug(f"Unregistered tool: {name}")

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> list[BaseTool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def to_openai_format(self) -> list[dict[str, Any]]:
        """Convert all tools to OpenAI function format."""
        return [tool.to_openai_format() for tool in self._tools.values()]

    async def execute(self, name: str, params: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with given parameters."""
        tool = self.get(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool '{name}' not found",
            )

        try:
            result = await tool.execute(**params)
            return result
        except Exception as e:
            logger.exception(f"Error executing tool '{name}'")
            return ToolResult(
                success=False,
                error=f"Execution error: {str(e)}",
            )

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def __len__(self) -> int:
        """Get number of registered tools."""
        return len(self._tools)
