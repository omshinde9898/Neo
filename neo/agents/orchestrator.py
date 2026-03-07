"""Orchestrator for routing tasks to appropriate agents."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from neo.agents.base import AgentResult, AgentTask, BaseAgent
from neo.agents.explore import ExploreAgent
from neo.agents.general import GeneralAgent
from neo.agents.plan import PlanAgent
from neo.config import Config
from neo.llm.client import Message, OpenAIClient
from neo.logger import get_logger
from neo.tools.registry import ToolRegistry

logger = get_logger(__name__)


@dataclass
class TaskRoute:
    """Result of task routing decision."""

    agent_type: str
    confidence: float
    reasoning: str


@dataclass
class ExecutionPlan:
    """Multi-step execution plan."""

    steps: list[AgentTask] = field(default_factory=list)
    parallel_groups: list[list[int]] = field(default_factory=list)


class AgentOrchestrator:
    """Orchestrates multiple agents for complex tasks.

    The orchestrator:
    1. Analyzes incoming tasks
    2. Routes to appropriate agent(s)
    3. Coordinates multi-agent workflows
    4. Manages parallel execution
    5. Aggregates results
    """

    AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
        "general": GeneralAgent,
        "explore": ExploreAgent,
        "plan": PlanAgent,
    }

    def __init__(
        self,
        llm: OpenAIClient,
        tools: ToolRegistry,
        project_path: Path,
        config: Config | None = None,
    ):
        """Initialize the orchestrator.

        Args:
            llm: OpenAI client
            tools: Tool registry
            project_path: Path to project
            config: Optional config
        """
        self.llm = llm
        self.tools = tools
        self.project_path = project_path
        self.config = config or Config.load()
        self._agents: dict[str, BaseAgent] = {}
        self._task_history: list[AgentTask] = []

        logger.info("AgentOrchestrator initialized")

    async def execute(
        self,
        user_input: str,
        streaming_callback: Any | None = None,
        tool_callback: Any | None = None,
    ) -> AgentResult:
        """Execute user input through the orchestrated agent system.

        Args:
            user_input: User's request
            streaming_callback: Optional callback for streaming output
            tool_callback: Optional callback for tool execution

        Returns:
            AgentResult with the execution result
        """
        logger.info(f"Orchestrator processing: {user_input[:50]}...")

        # Analyze and route the task
        route = await self._route_task(user_input)
        logger.info(f"Task routed to: {route.agent_type} (confidence: {route.confidence:.2f})")

        # Create the task
        task = AgentTask(
            id=str(uuid.uuid4()),
            type=route.agent_type,
            description=user_input,
            max_iterations=self.config.max_iterations,
            streaming=streaming_callback is not None,
        )
        self._task_history.append(task)

        # Get or create the agent
        agent = self._get_agent(route.agent_type, streaming_callback, tool_callback)

        # Execute
        try:
            result = await agent.execute(task)
            return result
        except Exception as e:
            logger.exception(f"Agent execution failed: {e}")
            return AgentResult(
                success=False,
                content=f"Error: {str(e)}",
                error=str(e),
            )

    async def execute_plan(
        self,
        plan: ExecutionPlan,
        streaming_callback: Any | None = None,
    ) -> list[AgentResult]:
        """Execute a multi-step plan with parallelization.

        Args:
            plan: Execution plan with steps
            streaming_callback: Optional streaming callback

        Returns:
            List of results for each step
        """
        import asyncio

        results: list[AgentResult] = []

        for group in plan.parallel_groups:
            # Get tasks in this group
            group_tasks = [plan.steps[i] for i in group if i < len(plan.steps)]

            # Execute in parallel
            tasks = [
                self._execute_single_step(task, streaming_callback)
                for task in group_tasks
            ]
            group_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result in group_results:
                if isinstance(result, Exception):
                    results.append(
                        AgentResult(
                            success=False,
                            content=str(result),
                            error=str(result),
                        )
                    )
                else:
                    results.append(result)

        return results

    async def _execute_single_step(
        self,
        task: AgentTask,
        streaming_callback: Any | None,
    ) -> AgentResult:
        """Execute a single step.

        Args:
            task: Task to execute
            streaming_callback: Optional streaming callback

        Returns:
            AgentResult
        """
        agent = self._get_agent(task.type, streaming_callback)
        return await agent.execute(task)

    async def _route_task(self, user_input: str) -> TaskRoute:
        """Route a task to the appropriate agent.

        Uses LLM-based routing with heuristics fallback.

        Args:
            user_input: User's request

        Returns:
            TaskRoute with agent type and confidence
        """
        # First try heuristics for speed
        heuristic_route = self._heuristic_routing(user_input)
        if heuristic_route.confidence > 0.8:
            return heuristic_route

        # Fall back to LLM routing for complex cases
        try:
            llm_route = await self._llm_routing(user_input)
            if llm_route.confidence > heuristic_route.confidence:
                return llm_route
        except Exception as e:
            logger.warning(f"LLM routing failed, using heuristic: {e}")

        return heuristic_route

    def _heuristic_routing(self, user_input: str) -> TaskRoute:
        """Fast heuristic-based task routing.

        Args:
            user_input: User's request

        Returns:
            TaskRoute
        """
        text = user_input.lower()

        # Exploration keywords
        explore_keywords = [
            "find", "where is", "search for", "locate", "show me",
            "what files", "where are", "find all", "search", "explore",
            "list all", "show structure", "map the", "discover",
        ]
        for kw in explore_keywords:
            if kw in text:
                return TaskRoute(
                    agent_type="explore",
                    confidence=0.9,
                    reasoning=f"Exploration keyword detected: '{kw}'",
                )

        # Planning keywords
        plan_keywords = [
            "plan", "design", "architecture", "how should",
            "best way to", "approach for", "strategy for",
            "implement", "create a", "build a system",
            "refactor", "reorganize", "redesign",
        ]
        for kw in plan_keywords:
            if kw in text:
                return TaskRoute(
                    agent_type="plan",
                    confidence=0.85,
                    reasoning=f"Planning keyword detected: '{kw}'",
                )

        # Default to general agent
        return TaskRoute(
            agent_type="general",
            confidence=0.7,
            reasoning="No specific keywords detected, using general agent",
        )

    async def _llm_routing(self, user_input: str) -> TaskRoute:
        """LLM-based task routing for complex cases.

        Args:
            user_input: User's request

        Returns:
            TaskRoute
        """
        routing_prompt = f"""Analyze the following task and determine which agent should handle it.

Available agents:
- general: General-purpose coding agent for reading, writing, and modifying code
- explore: Fast agent for finding files, symbols, and exploring codebase structure
- plan: Planning agent for designing implementation strategies and complex changes

Task: "{user_input}"

Respond with JSON:
{{
  "agent": "general|explore|plan",
  "confidence": 0.0-1.0,
  "reasoning": "explanation"
}}
"""

        messages = [Message(role="user", content=routing_prompt)]
        result = await self.llm.complete(messages=messages, tools=None)

        # Parse JSON from response
        import json
        import re

        try:
            # Try to find JSON in the response
            text = result.content or "{}"
            # Look for JSON block
            match = re.search(r'\{[^}]+\}', text)
            if match:
                data = json.loads(match.group())
                return TaskRoute(
                    agent_type=data.get("agent", "general"),
                    confidence=data.get("confidence", 0.5),
                    reasoning=data.get("reasoning", "LLM routing"),
                )
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse routing response: {e}")

        # Fallback
        return TaskRoute(
            agent_type="general",
            confidence=0.5,
            reasoning="LLM routing parse failed",
        )

    def _get_agent(
        self,
        agent_type: str,
        streaming_callback: Any | None = None,
        tool_callback: Any | None = None,
    ) -> BaseAgent:
        """Get or create an agent of the specified type.

        Args:
            agent_type: Type of agent to get
            streaming_callback: Optional streaming callback
            tool_callback: Optional tool execution callback

        Returns:
            BaseAgent instance
        """
        # Create new agent each time for now (stateless)
        # Could cache agents in the future
        agent_class = self.AGENT_REGISTRY.get(agent_type, GeneralAgent)

        return agent_class(
            llm=self.llm,
            tools=self.tools,
            project_path=self.project_path,
            config=self.config,
            streaming_callback=streaming_callback,
            tool_callback=tool_callback,
        )

    def create_execution_plan(
        self,
        high_level_task: str,
        subtasks: list[str],
    ) -> ExecutionPlan:
        """Create an execution plan from a high-level task and subtasks.

        Args:
            high_level_task: The main task
            subtasks: List of subtask descriptions

        Returns:
            ExecutionPlan
        """
        steps: list[AgentTask] = []

        for i, subtask in enumerate(subtasks):
            # Route each subtask
            route = self._heuristic_routing(subtask)

            task = AgentTask(
                id=str(uuid.uuid4()),
                type=route.agent_type,
                description=subtask,
                parent_id=high_level_task,
                max_iterations=self.config.max_iterations,
            )
            steps.append(task)

        # Simple parallelization: all steps can run in parallel for now
        # In future, could analyze dependencies
        parallel_groups = [list(range(len(steps)))]

        return ExecutionPlan(steps=steps, parallel_groups=parallel_groups)

    def get_status(self) -> dict[str, Any]:
        """Get orchestrator status."""
        return {
            "active_agents": len(self._agents),
            "task_history": len(self._task_history),
            "available_agents": list(self.AGENT_REGISTRY.keys()),
        }

    def reset(self) -> None:
        """Reset orchestrator state."""
        self._agents.clear()
        self._task_history.clear()
        logger.info("Orchestrator reset")
