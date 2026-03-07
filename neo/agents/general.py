"""General-purpose coding agent - the default agent for most tasks."""

from __future__ import annotations

from typing import Any

from neo.agents.base import AgentResult, AgentTask, BaseAgent
from neo.llm.client import Message

from neo.logger import get_logger

logger = get_logger(__name__)


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
    system_prompt = """You are Neo, a helpful coding assistant. You help users write, read, and modify code.

Guidelines:
- Use tools to explore and understand before making changes
- Be concise but complete - get to the point without rambling
- Read files before explaining them
- Show relevant code snippets when discussing changes
- Use markdown formatting when it helps clarity (code blocks, bullet points)
- Propose next steps but wait for confirmation before major edits
- Ask permission before destructive operations (deleting files, large rewrites)
- Focus on practical solutions over theoretical explanations
- If you don't know something, say so rather than guessing"""

    async def _execute_task(self, task: AgentTask) -> AgentResult:
        """Execute a general coding task.

        Args:
            task: Task to execute

        Returns:
            AgentResult with the execution result
        """
        logger.info(f"GeneralAgent executing: {task.description}")

        # Build messages with conversation history
        messages = self.build_conversation_messages(task.description)

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
