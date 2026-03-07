"""Base agent class for Neo multi-agent system."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
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
class AgentTask:
    """A task to be executed by an agent."""

    id: str
    type: str  # explore, plan, code, review, etc.
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    max_iterations: int = 10
    streaming: bool = False
    parent_id: str | None = None


@dataclass
class AgentResult:
    """Result of an agent execution."""

    success: bool
    content: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    subtasks: list[AgentResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "content": self.content,
            "data": self.data,
            "error": self.error,
            "tool_calls": self.tool_calls,
            "tokens_used": self.tokens_used,
        }


@dataclass
class ToolExecution:
    """Represents a tool execution with dependencies."""

    tool_name: str
    arguments: dict[str, Any]
    dependencies: list[str] = field(default_factory=list)
    result: ToolResult | None = None
    executed: bool = False
    tool_call_id: str = ""  # Required for OpenAI API


class BaseAgent(ABC):
    """Base class for all Neo agents."""

    name: str = ""
    description: str = ""
    system_prompt: str = """You are a helpful coding assistant. Use tools to explore and modify code.

Guidelines:
- Be concise but complete
- Use tools rather than describing what you would do
- Ask before destructive operations
- Show relevant code when discussing changes"""

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
            tool_callback: Optional callback for tool execution (tool_name, inputs)
        """
        self.llm = llm
        self.tools = tools
        self.project_path = project_path
        self.config = config or Config.load()
        self.memory = SessionMemory(max_turns=self.config.max_session_turns)
        self.streaming_callback = streaming_callback
        self.tool_callback = tool_callback
        self._subagents: list[BaseAgent] = []

        logger.info(f"{self.__class__.__name__} initialized")

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute a task.

        Args:
            task: The task to execute

        Returns:
            AgentResult with the execution result
        """
        logger.info(f"{self.name} executing task: {task.description[:50]}...")
        return await self._execute_task(task)

    @abstractmethod
    async def _execute_task(self, task: AgentTask) -> AgentResult:
        """Internal task execution - to be implemented by subclasses."""
        pass

    async def _run_agent_loop(
        self,
        messages: list[Message],
        max_iterations: int | None = None,
        streaming: bool = False,
        streaming_callback: Callable[[str], None] | None = None,
    ) -> CompletionResult:
        """Run the standard agent loop with tool calling.

        Args:
            messages: Initial messages for the conversation
            max_iterations: Maximum number of tool-calling iterations
            streaming: Whether to stream the response
            streaming_callback: Optional callback for streaming tokens

        Returns:
            CompletionResult with final response
        """
        max_iterations = max_iterations or self.config.max_iterations
        callback = streaming_callback or self.streaming_callback

        for iteration in range(max_iterations):
            logger.debug(f"Agent loop iteration {iteration + 1}/{max_iterations}")

            # Call LLM with optional streaming
            result = await self.llm.complete(
                messages=messages,
                tools=self.tools.to_openai_format(),
                stream=streaming,
                streaming_callback=callback,
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

                # Build execution plan for parallel execution
                tool_executions = await self._plan_tool_executions(result.tool_calls)

                # Execute tools
                await self._execute_tools(tool_executions, messages)

            else:
                # Final response
                logger.debug("No tool calls, returning final response")
                # Sanitize output to remove JSON/markdown wrappers
                if result.content:
                    result.content = self._sanitize_output(result.content)
                return result

        # Max iterations reached
        logger.warning(f"Max iterations ({max_iterations}) reached")
        return CompletionResult(
            content="Max iterations reached. The task may be too complex."
        )

    async def _plan_tool_executions(
        self, tool_calls: list[dict[str, Any]]
    ) -> list[ToolExecution]:
        """Plan tool executions, determining dependencies.

        Args:
            tool_calls: List of tool calls from LLM

        Returns:
            List of ToolExecution with dependencies
        """
        executions: list[ToolExecution] = []

        for tool_call in tool_calls:
            function = tool_call.get("function", {})
            name = function.get("name", "")
            arguments_str = function.get("arguments", "{}")
            tool_call_id = tool_call.get("id", "")  # Capture tool_call_id

            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError:
                arguments = {}

            # Analyze dependencies - tools that read files are often independent
            # tools that write files may depend on reads
            dependencies = []

            executions.append(
                ToolExecution(
                    tool_name=name,
                    arguments=arguments,
                    dependencies=dependencies,
                    tool_call_id=tool_call_id,  # Store for API compliance
                )
            )

        return executions

    async def _execute_tools(
        self,
        executions: list[ToolExecution],
        messages: list[Message],
    ) -> None:
        """Execute tools with dependency management.

        Args:
            executions: List of tool executions
            messages: Messages list to append results to
        """
        import asyncio

        # Group tools by dependency level
        executed = set()
        pending = list(executions)

        while pending:
            # Find tools with all dependencies satisfied
            ready = [
                ex for ex in pending if all(dep in executed for dep in ex.dependencies)
            ]

            if not ready:
                # No ready tools but pending exist - dependency issue
                logger.warning("Dependency cycle detected, executing sequentially")
                ready = [pending[0]]

            # Execute ready tools in parallel
            tasks = [
                self._execute_single_tool(ex) for ex in ready
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for execution, result in zip(ready, results):
                if isinstance(result, Exception):
                    logger.exception(f"Tool execution failed: {execution.tool_name}")
                    execution.result = ToolResult(
                        success=False,
                        error=str(result),
                    )
                else:
                    execution.result = result
                execution.executed = True
                executed.add(execution.tool_name)
                pending.remove(execution)

        # Add all results to messages (with size limits to control token usage)
        MAX_TOOL_OUTPUT = 2000  # Limit tool output to prevent token explosion
        for execution in executions:
            result = execution.result
            if result:
                output = result.output if result.success else (result.error or "Error")
                # Truncate long outputs
                if len(output) > MAX_TOOL_OUTPUT:
                    output = output[:MAX_TOOL_OUTPUT] + f"\n... ({len(output) - MAX_TOOL_OUTPUT} chars truncated)"
                messages.append(
                    Message(
                        role="tool",
                        content=output,
                        name=execution.tool_name,
                        tool_call_id=execution.tool_call_id,  # Required by OpenAI API
                    )
                )

    async def _execute_single_tool(self, execution: ToolExecution) -> ToolResult:
        """Execute a single tool.

        Args:
            execution: Tool execution specification

        Returns:
            ToolResult from execution
        """
        # Notify tool callback if registered
        if self.tool_callback:
            try:
                self.tool_callback(execution.tool_name, execution.arguments)
            except Exception:
                pass  # Don't fail if callback errors

        return await self.tools.execute(execution.tool_name, execution.arguments)

    def build_system_message(self, extra_context: str = "") -> Message:
        """Build the system message with context.

        Args:
            extra_context: Additional context to include

        Returns:
            System message
        """
        # Keep system prompt minimal - extra_context only if explicitly provided
        content = self.system_prompt
        if extra_context:
            content = f"{self.system_prompt}\n\nContext: {extra_context}"
        return Message(role="system", content=content)

    def build_conversation_messages(self, user_content: str) -> list[Message]:
        """Build messages list with system prompt, history, and user message.

        Args:
            user_content: Current user message content

        Returns:
            List of messages ready for LLM
        """
        messages: list[Message] = [self.build_system_message()]

        # Add conversation history
        for msg in self.memory.get_messages():
            messages.append(Message(role=msg["role"], content=msg["content"]))

        # Add current user message
        messages.append(Message(role="user", content=user_content))

        return messages

    def _sanitize_output(self, content: str) -> str:
        """Remove pure JSON wrappers from output while preserving markdown.

        Args:
            content: Raw LLM output

        Returns:
            Cleaned content
        """
        import json

        # Only unwrap if content is purely a JSON string wrapper
        # e.g., "{\"response\": \"actual content\"}" -> actual content
        try:
            parsed = json.loads(content.strip())
            if isinstance(parsed, str):
                return parsed.strip()
            # If it's a dict with a single string value, extract it
            if isinstance(parsed, dict) and len(parsed) == 1:
                value = list(parsed.values())[0]
                if isinstance(value, str):
                    return value.strip()
        except (json.JSONDecodeError, ValueError):
            pass

        return content.strip()

    def spawn_subagent(self, agent_class: type[BaseAgent]) -> BaseAgent:
        """Spawn a sub-agent for parallel work.

        Args:
            agent_class: Class of the sub-agent to spawn

        Returns:
            Initialized sub-agent
        """
        subagent = agent_class(
            llm=self.llm,
            tools=self.tools,
            project_path=self.project_path,
            config=self.config,
            streaming_callback=self.streaming_callback,
        )
        self._subagents.append(subagent)
        return subagent

    async def run_parallel(
        self,
        tasks: list[tuple[type[BaseAgent], AgentTask]],
    ) -> list[AgentResult]:
        """Run multiple agents in parallel.

        Args:
            tasks: List of (agent_class, task) tuples

        Returns:
            List of AgentResults
        """
        import asyncio

        async def run_single(
            agent_class: type[BaseAgent], task: AgentTask
        ) -> AgentResult:
            agent = self.spawn_subagent(agent_class)
            return await agent.execute(task)

        coros = [run_single(agent_class, task) for agent_class, task in tasks]
        return await asyncio.gather(*coros, return_exceptions=True)

    def get_status(self) -> dict[str, Any]:
        """Get agent status information."""
        return {
            "agent": self.name,
            "memory_turns": len(self.memory),
            "subagents": len(self._subagents),
        }
