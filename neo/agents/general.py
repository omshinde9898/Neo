"""General-purpose coding agent - the default agent for most tasks."""

from __future__ import annotations

import logging
from typing import Any

from neo.agents.base import AgentResult, AgentTask, BaseAgent
from neo.llm.client import Message

logger = logging.getLogger(__name__)


class GeneralAgent(BaseAgent):
    """General-purpose coding agent for most tasks.

    This is the default agent that handles:
    - Code reading and writing
    - File operations
    - Git operations
    - Shell commands
    - General coding questions
    """

    name = "general"
    description = "General coding assistant"
    system_prompt = "You are Neo, a coding assistant. Use tools to explore, read, and edit code. Be concise."

    async def _execute_task(self, task: AgentTask) -> AgentResult:
        """Execute a general coding task.

        Args:
            task: Task to execute

        Returns:
            AgentResult with the execution result
        """
        logger.info(f"GeneralAgent executing: {task.description}")

        # Build messages
        messages = [
            self.build_system_message(),
            Message(role="user", content=task.description),
        ]

        # Add context from task
        if task.context:
            context_str = "\n".join(
                f"{key}: {value}" for key, value in task.context.items()
            )
            messages.append(
                Message(role="system", content=f"Task Context:\n{context_str}")
            )

        # Run agent loop
        result = await self._run_agent_loop(
            messages=messages,
            max_iterations=task.max_iterations,
            streaming=task.streaming,
        )

        # Store in memory
        self.memory.add_turn("user", task.description)
        self.memory.add_turn("assistant", result.content or "")

        return AgentResult(
            success=True,
            content=result.content or "",
            tokens_used=result.prompt_tokens + result.completion_tokens,
        )
