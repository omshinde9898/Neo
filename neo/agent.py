"""Main agent loop for Neo - Now using multi-agent orchestration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from neo.agents.orchestrator import AgentOrchestrator
from neo.agents.base import AgentResult
from neo.config import Config
from neo.llm.client import OpenAIClient
from neo.memory.project import ProjectMemory

logger = logging.getLogger(__name__)


class Agent:
    """Neo Agent - Multi-agent orchestrated coding assistant.

    This is the main entry point for Neo. It uses AgentOrchestrator
    to route tasks to specialized agents.
    """

    def __init__(
        self,
        llm: OpenAIClient,
        tools: Any,
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
        self.project_path = project_path
        self.config = config or Config.load()
        self.project = ProjectMemory(project_path)

        # Initialize the orchestrator
        self.orchestrator = AgentOrchestrator(
            llm=llm,
            tools=tools,
            project_path=project_path,
            config=self.config,
        )

        logger.info(f"Agent initialized with orchestrator for project: {project_path}")

    async def run(
        self,
        user_input: str,
        streaming_callback: Callable[[str], None] | None = None,
        tool_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> str:
        """Execute user request through the orchestrated multi-agent system.

        Args:
            user_input: User's request
            streaming_callback: Optional callback for streaming output
            tool_callback: Optional callback for tool execution

        Returns:
            Final response from the agent
        """
        logger.info(f"Processing request: {user_input[:50]}...")

        try:
            # Execute through orchestrator
            result = await self.orchestrator.execute(
                user_input=user_input,
                streaming_callback=streaming_callback,
                tool_callback=tool_callback,
            )

            if result.success:
                return result.content
            else:
                return f"Error: {result.error or 'Unknown error'}"

        except Exception as e:
            logger.exception("Error in agent execution")
            return f"Error: {str(e)}"

    def get_status(self) -> dict[str, Any]:
        """Get agent status information."""
        orch_status = self.orchestrator.get_status()
        return {
            "model": self.llm.model,
            "project": str(self.project.path),
            "languages": self.project.languages,
            **orch_status,
            "tokens": self.llm.get_token_stats(),
        }

    def reset_memory(self) -> None:
        """Clear conversation history and reset orchestrator."""
        self.orchestrator.reset()
        logger.info("Memory cleared")
