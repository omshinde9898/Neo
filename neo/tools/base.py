"""Base tool class for Neo."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    output: str = ""
    error: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "data": self.data,
        }

    def __str__(self) -> str:
        """String representation of result."""
        if self.success:
            return self.output or "Success"
        return f"Error: {self.error}" if self.error else "Failed"


class BaseTool(ABC):
    """Base class for all Neo tools."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    def __init__(self) -> None:
        """Initialize the tool."""
        if not self.name:
            raise ValueError(f"Tool {self.__class__.__name__} must have a name")
        if not self.description:
            raise ValueError(f"Tool {self.__class__.__name__} must have a description")

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    def to_openai_format(self) -> dict[str, Any]:
        """Convert tool to OpenAI function format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def get_parameter_schema(self, param_type: str, description: str, **extra: Any) -> dict[str, Any]:
        """Helper to create parameter schema."""
        schema: dict[str, Any] = {
            "type": param_type,
            "description": description,
        }
        schema.update(extra)
        return schema
