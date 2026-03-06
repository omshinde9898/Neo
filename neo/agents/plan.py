"""Plan agent for creating implementation plans."""

from __future__ import annotations

import json
import logging
from typing import Any

from neo.agents.base import AgentResult, AgentTask, BaseAgent
from neo.llm.client import Message

logger = logging.getLogger(__name__)


class PlanAgent(BaseAgent):
    """Planning agent for designing implementation strategies.

    This agent creates detailed plans before making changes:
    - Breaks down complex tasks into steps
    - Identifies critical files and dependencies
    - Considers architectural trade-offs
    - Creates implementation order

    Use this agent before making complex multi-file changes.
    """

    name = "plan"
    description = "Creates implementation plans"
    system_prompt = "You are a planning expert. Create step-by-step implementation plans. Use tools to explore first. Output plans as JSON."

    async def _execute_task(self, task: AgentTask) -> AgentResult:
        """Execute planning task.

        Args:
            task: Task to execute

        Returns:
            AgentResult with the plan
        """
        logger.info(f"PlanAgent creating plan for: {task.description}")

        # First, explore the codebase if needed
        context = task.context or {}
        files_to_explore = context.get("files_to_explore", [])

        if not files_to_explore and "explore" not in task.description.lower():
            # Suggest exploration first
            logger.info("Planning suggests exploration first")

        # Build planning prompt
        planning_prompt = self._build_planning_prompt(task)

        messages = [
            self.build_system_message(),
            Message(role="user", content=planning_prompt),
        ]

        # Run planning
        result = await self._run_agent_loop(
            messages=messages,
            max_iterations=task.max_iterations,
        )

        # Parse the plan
        plan = self._parse_plan(result.content or "")

        return AgentResult(
            success=True,
            content=result.content or "",
            data=plan,
            tokens_used=result.prompt_tokens + result.completion_tokens,
        )

    def _build_planning_prompt(self, task: AgentTask) -> str:
        """Build a planning-focused prompt.

        Args:
            task: The planning task

        Returns:
            Optimized planning prompt
        """
        prompt_parts = [
            f"Task: {task.description}",
            "",
            "Create a detailed implementation plan. Follow these steps:",
            "1. First, explore the codebase to understand the current state",
            "2. Identify all files that need to be modified or created",
            "3. Break down the implementation into specific steps",
            "4. Note dependencies between steps",
            "5. Provide the plan in the JSON format specified in your instructions",
            "",
            "Remember to:",
            "- Check for existing patterns to follow",
            "- Consider edge cases",
            "- Plan for testing/verification",
            "- Keep changes minimal and focused",
        ]

        # Add context
        if task.context:
            prompt_parts.append("\nContext:")
            for key, value in task.context.items():
                prompt_parts.append(f"- {key}: {value}")

        return "\n".join(prompt_parts)

    def _parse_plan(self, content: str) -> dict[str, Any]:
        """Parse the plan from agent response.

        Args:
            content: The agent's response

        Returns:
            Structured plan data
        """
        plan: dict[str, Any] = {
            "task": "",
            "approach": "",
            "files_affected": [],
            "steps": [],
            "dependencies": [],
            "risks": [],
            "verification": "",
            "raw_response": content,
        }

        # Try to extract JSON from response
        try:
            # Look for JSON code block
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            else:
                # Try to find JSON directly
                json_str = content

            parsed = json.loads(json_str)
            plan.update(parsed)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Could not parse plan JSON: {e}")
            # Keep the raw response
            plan["parse_error"] = str(e)

        # Extract files from text if JSON parsing failed
        if not plan["files_affected"]:
            plan["files_affected"] = self._extract_files_from_text(content)

        return plan

    def _extract_files_from_text(self, content: str) -> list[dict[str, str]]:
        """Extract file references from text.

        Args:
            content: Text to parse

        Returns:
            List of file info dicts
        """
        files: list[dict[str, str]] = []
        lines = content.split("\n")

        for line in lines:
            # Look for file references
            for ext in [".py", ".js", ".ts", ".go", ".rs", ".java"]:
                if ext in line:
                    # Try to extract filename
                    words = line.split()
                    for word in words:
                        if ext in word and ("/" in word or "\\" in word or word.endswith(ext)):
                            files.append({
                                "path": word.strip("`()[]{}:;,."),
                                "change_type": "modify",
                                "reason": "referenced in plan",
                            })

        return files

    async def create_plan(
        self,
        task_description: str,
        files_to_explore: list[str] | None = None,
    ) -> AgentResult:
        """Create an implementation plan.

        Args:
            task_description: What needs to be done
            files_to_explore: Optional files to analyze first

        Returns:
            AgentResult with the plan
        """
        task = AgentTask(
            id="plan_implementation",
            type="plan",
            description=task_description,
            context={"files_to_explore": files_to_explore or []},
            max_iterations=self.config.max_iterations,
        )
        return await self.execute(task)

    async def analyze_architecture(self, target_path: str | None = None) -> AgentResult:
        """Analyze the architecture of a codebase or component.

        Args:
            target_path: Optional specific path to analyze

        Returns:
            AgentResult with architecture analysis
        """
        task = AgentTask(
            id="analyze_architecture",
            type="plan",
            description=f"Analyze the architecture of the codebase{f' at {target_path}' if target_path else ''}. "
                       f"Identify: main components, data flow, dependencies, entry points, "
                       f"configuration patterns, and architectural patterns used.",
            max_iterations=self.config.max_iterations,
        )
        return await self.execute(task)
