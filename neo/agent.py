"""Simplified monolithic agent for Neo - Claude Code style architecture."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from neo.config import Config
from neo.llm.client import CompletionResult, Message, OpenAIClient
from neo.logger import get_logger
from neo.memory.session import SessionMemory
from neo.tools.base import ToolResult
from neo.tools.registry import ToolRegistry

logger = get_logger(__name__)


@dataclass
class AgentResult:
    """Result of an agent execution."""

    success: bool
    content: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    tokens_used: int = 0


class Agent:
    """Monolithic agent with direct tool access - Claude Code style.

    This agent is intentionally simple:
    - Single agent, no routing overhead
    - Direct tool calling without pre-indexing
    - Just-in-time context gathering
    - Conversation history for continuity
    """

    SYSTEM_PROMPT = """You are Neo, a helpful coding assistant. Help users write, read, and modify code.

Guidelines:
- Use tools to explore and understand before making changes
- Be concise but complete - get to the point without rambling
- Read files before explaining them
- Show relevant code snippets when discussing changes
- Use markdown formatting when it helps clarity (code blocks, bullet points)
- Propose next steps but wait for confirmation before major edits
- Ask permission before destructive operations (deleting files, large rewrites)
- Focus on practical solutions over theoretical explanations
- If you don't know something, say so rather than guessing

Tool Usage:
- Use Read to read files, Read({"file_path": "path/to/file"})
- Use Edit to modify files, Edit({"file_path": "path", "old_string": "...", "new_string": "..."})
- Use Write to create files, Write({"file_path": "path", "content": "..."})
- Use Glob to find files, Glob({"pattern": "**/*.py"})
- Use Grep to search code, Grep({"pattern": "class Foo"})
- Use Bash for shell commands, Bash({"command": "ls -la"})
- Always use forward slashes in file paths (even on Windows)
- Use relative paths from the project root when possible

When editing files:
- Make sure old_string matches exactly (including indentation)
- For multi-line edits, include enough context to make it unique
- If the string isn't unique, provide more surrounding lines
"""

    def __init__(
        self,
        llm: OpenAIClient,
        tools: ToolRegistry,
        project_path: Path,
        config: Config | None = None,
        streaming_callback: Callable[[str], None] | None = None,
        tool_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ):
        """Initialize the agent.

        Args:
            llm: OpenAI client for LLM calls
            tools: Tool registry for tool execution
            project_path: Path to the current project
            config: Configuration settings
            streaming_callback: Optional callback for streaming output
            tool_callback: Optional callback for tool execution
        """
        self.llm = llm
        self.tools = tools
        self.project_path = Path(project_path).resolve()
        self.config = config or Config.load()
        self.memory = SessionMemory(max_turns=self.config.max_session_turns)
        self.streaming_callback = streaming_callback
        self.tool_callback = tool_callback

        # Token tracking
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

        logger.info("Agent initialized (monolithic mode)")

    async def run(
        self,
        user_input: str,
        streaming_callback: Callable[[str], None] | None = None,
        tool_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> str:
        """Run the agent with user input.

        Args:
            user_input: User's request
            streaming_callback: Optional callback for streaming tokens
            tool_callback: Optional callback for tool execution

        Returns:
            Agent response string
        """
        logger.info(f"Agent run: {user_input[:100]}...")

        # Use passed tool_callback if provided, otherwise use instance one
        effective_tool_callback = tool_callback or self.tool_callback

        # Build messages with system prompt and history
        messages = self._build_messages(user_input)

        # Run the agent loop
        callback = streaming_callback or self.streaming_callback
        result = await self._run_agent_loop(
            messages=messages,
            streaming=callback is not None,
            streaming_callback=callback,
            tool_callback=effective_tool_callback,
        )

        # Store in memory
        self.memory.add_turn("user", user_input)
        self.memory.add_turn("assistant", result.content or "")

        # Track tokens
        self.total_prompt_tokens += result.prompt_tokens
        self.total_completion_tokens += result.completion_tokens

        return result.content or ""

    def _build_messages(self, user_input: str) -> list[Message]:
        """Build messages for the LLM.

        Args:
            user_input: Current user input

        Returns:
            List of messages
        """
        messages: list[Message] = [
            Message(role="system", content=self.SYSTEM_PROMPT),
        ]

        # Add conversation history
        for msg in self.memory.get_messages():
            messages.append(Message(role=msg["role"], content=msg["content"]))

        # Add current user message
        messages.append(Message(role="user", content=user_input))

        return messages

    async def _run_agent_loop(
        self,
        messages: list[Message],
        max_iterations: int | None = None,
        streaming: bool = False,
        streaming_callback: Callable[[str], None] | None = None,
        tool_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> CompletionResult:
        """Run the agent loop with tool calling.

        Args:
            messages: Messages for the conversation
            max_iterations: Maximum number of tool-calling iterations
            streaming: Whether to stream the response
            streaming_callback: Optional callback for streaming tokens
            tool_callback: Optional callback for tool execution

        Returns:
            CompletionResult with final response
        """
        max_iterations = max_iterations or self.config.max_iterations

        for iteration in range(max_iterations):
            logger.debug(f"Agent loop iteration {iteration + 1}/{max_iterations}")

            # Call LLM
            result = await self.llm.complete(
                messages=messages,
                tools=self.tools.to_openai_format(),
                stream=streaming,
                streaming_callback=streaming_callback,
            )

            if result.has_function_calls():
                # Execute tools
                logger.debug(f"Executing {len(result.tool_calls)} tool call(s)")

                # Add assistant message with tool calls
                messages.append(
                    Message(
                        role="assistant",
                        content=result.content,
                        tool_calls=result.tool_calls,
                    )
                )

                # Execute tools and add results
                await self._execute_tool_calls(result.tool_calls, messages, tool_callback)

            else:
                # Final response
                logger.debug("No tool calls, returning final response")
                return result

        # Max iterations reached
        logger.warning(f"Max iterations ({max_iterations}) reached")
        return CompletionResult(
            content="Max iterations reached. The task may be too complex."
        )

    async def _execute_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
        messages: list[Message],
        tool_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        """Execute tool calls and add results to messages.

        Args:
            tool_calls: List of tool calls from LLM
            messages: Messages list to append results to
        """
        import asyncio

        # Execute all tools in parallel
        tasks = [
            self._execute_single_tool(tc, tool_callback)
            for tc in tool_calls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Add results to messages
        MAX_TOOL_OUTPUT = 10000  # Limit to prevent token explosion

        for tool_call, result in zip(tool_calls, results):
            tool_call_id = tool_call.get("id", "")
            function = tool_call.get("function", {})
            tool_name = function.get("name", "unknown")

            if isinstance(result, Exception):
                logger.exception(f"Tool execution failed: {tool_name}")
                output = f"Error: {str(result)}"
            else:
                result_obj = result
                output = result_obj.output if result_obj.success else (result_obj.error or "Error")

            # Truncate long outputs
            if len(output) > MAX_TOOL_OUTPUT:
                output = output[:MAX_TOOL_OUTPUT] + f"\n... ({len(output) - MAX_TOOL_OUTPUT} chars truncated)"

            messages.append(
                Message(
                    role="tool",
                    content=output,
                    name=tool_name,
                    tool_call_id=tool_call_id,
                )
            )

    async def _execute_single_tool(
        self,
        tool_call: dict[str, Any],
        tool_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> ToolResult:
        """Execute a single tool call.

        Args:
            tool_call: Tool call specification

        Returns:
            ToolResult from execution
        """
        function = tool_call.get("function", {})
        tool_name = function.get("name", "")
        arguments_str = function.get("arguments", "{}")

        # Parse arguments
        try:
            arguments = json.loads(arguments_str)
        except json.JSONDecodeError:
            arguments = {}

        # Notify tool callback if registered (use passed callback if available)
        effective_callback = tool_callback or self.tool_callback
        if effective_callback:
            try:
                effective_callback(tool_name, arguments)
            except Exception:
                pass

        return await self.tools.execute(tool_name, arguments)

    def get_status(self) -> dict[str, Any]:
        """Get agent status information."""
        return {
            "model": self.llm.model if hasattr(self.llm, "model") else "unknown",
            "memory_turns": len(self.memory),
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "project": str(self.project_path),
        }

    def reset_memory(self) -> None:
        """Clear conversation history."""
        self.memory.clear()
        logger.info("Memory cleared")

    def get_cost_report(self) -> str:
        """Get cost report from LLM client."""
        if hasattr(self.llm, "format_cost_report"):
            return self.llm.format_cost_report()
        return "Cost tracking not available"
