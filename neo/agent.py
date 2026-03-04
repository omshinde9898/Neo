"""Main agent loop for Neo."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from neo.config import Config
from neo.llm.client import Message, OpenAIClient
from neo.memory.project import ProjectMemory
from neo.memory.session import SessionMemory
from neo.tools.base import ToolResult
from neo.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are Neo, a coding assistant.

You help users write, read, and modify code. You have access to tools for:
- Reading and writing files
- Running shell commands
- Git operations
- Searching code

Guidelines:
1. Use tools to explore before making changes
2. Show diffs before editing files
3. Write clean, documented code
4. Run tests or checks when available
5. Be concise - focus on code, not explanations

When editing files:
- Always show the diff of changes first
- Use atomic writes with backups
- Follow existing code style

Project Context:
{project_context}
"""


class Agent:
    """Simple agent loop for coding tasks."""

    def __init__(
        self,
        llm: OpenAIClient,
        tools: ToolRegistry,
        project_path: Path,
        config: Config | None = None,
    ):
        """Initialize the agent.

        Args:
            llm: OpenAI client
            tools: Tool registry
            project_path: Path to current project
            config: Optional configuration
        """
        self.llm = llm
        self.tools = tools
        self.config = config or Config.load()
        self.memory = SessionMemory(max_turns=self.config.max_session_turns)
        self.project = ProjectMemory(project_path)

        self.max_iterations = self.config.max_iterations

        logger.info(f"Agent initialized for project: {project_path}")

    async def run(self, user_input: str) -> str:
        """Execute user request through the agent loop.

        Args:
            user_input: User's request

        Returns:
            Final response from the agent
        """
        logger.info(f"Processing request: {user_input[:50]}...")

        # Build initial messages
        messages = [
            Message(role="system", content=self.build_context()),
            *[Message(role=m["role"], content=m["content"]) for m in self.memory.get_messages()],
            Message(role="user", content=user_input),
        ]

        # Agent loop
        for iteration in range(self.max_iterations):
            logger.debug(f"Iteration {iteration + 1}/{self.max_iterations}")

            try:
                # Call LLM
                result = await self.llm.complete(
                    messages=messages,
                    tools=self.tools.to_openai_format(),
                )

                if result.has_function_calls():
                    # Execute tools
                    logger.debug(f"Executing {len(result.tool_calls)} tool call(s)")

                    # Add assistant message with tool calls
                    messages.append(Message(
                        role="assistant",
                        content=result.content,
                        tool_calls=result.tool_calls,
                    ))

                    # Execute each tool call
                    for tool_call in result.tool_calls:
                        tool_result = await self.execute_tool_call(tool_call)

                        # Add tool result to messages
                        messages.append(Message(
                            role="tool",
                            content=tool_result.output if tool_result.success else (tool_result.error or "Error"),
                            tool_call_id=tool_call.get("id", ""),
                            name=tool_call.get("function", {}).get("name", ""),
                        ))

                else:
                    # Final response - no more tool calls
                    response = result.content or "(no response)"

                    # Store in memory
                    self.memory.add_turn("user", user_input)
                    self.memory.add_turn("assistant", response)

                    logger.info("Request completed")
                    return response

            except Exception as e:
                logger.exception("Error in agent loop")
                return f"Error: {str(e)}"

        return "Max iterations reached. The task may be too complex."

    async def execute_tool_call(self, tool_call: dict[str, Any]) -> ToolResult:
        """Execute a single tool call.

        Args:
            tool_call: Tool call from LLM

        Returns:
            Tool execution result
        """
        function = tool_call.get("function", {})
        name = function.get("name", "")
        arguments_str = function.get("arguments", "{}")

        try:
            arguments = json.loads(arguments_str)
        except json.JSONDecodeError:
            return ToolResult(
                success=False,
                error=f"Invalid JSON in tool arguments: {arguments_str}",
            )

        logger.debug(f"Executing tool: {name} with args: {arguments}")

        return await self.tools.execute(name, arguments)

    def build_context(self) -> str:
        """Build system context with project info."""
        return SYSTEM_PROMPT.format(
            project_context=self.project.get_context()
        )

    def get_status(self) -> dict[str, Any]:
        """Get agent status information."""
        return {
            "model": self.llm.model,
            "project": str(self.project.path),
            "languages": self.project.languages,
            "memory_turns": len(self.memory),
            "max_turns": self.memory.max_turns,
            "tokens": self.llm.get_token_stats(),
        }

    def reset_memory(self) -> None:
        """Clear conversation history."""
        self.memory.clear()
        logger.info("Memory cleared")
