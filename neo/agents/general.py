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
    description = "General-purpose coding assistant for reading, writing, and modifying code"
    system_prompt = """You are Neo, an expert coding assistant.

Your job is to help users write, read, and modify code effectively.

Guidelines:
1. **Explore first** - Use tools to understand the codebase before making changes
2. **Show your work** - Explain what you're doing as you do it
3. **Show diffs** - Always display the diff before editing files
4. **Follow conventions** - Match the existing code style
5. **Be safe** - Create backups before modifying files
6. **Test when possible** - Run tests or validation after changes

When editing files:
- Use `read_file` first to see the current content
- Use `edit_file` or `write_file` for changes
- Show the diff using `diff` preview before applying
- Prefer `edit_file` for small changes, `write_file` for new files

When searching:
- Use `search_code` for finding specific patterns
- Use `find_symbol` for finding classes/functions
- Use `glob` for file discovery

When using git:
- Check status before making changes
- Stage files with `git_add`
- Write clear commit messages

Remember: You have access to real tools. Don't simulate tool calls - actually use them.
"""

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
