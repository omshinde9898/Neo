"""Code review agent for analyzing code quality."""

from __future__ import annotations

from typing import Any

from neo.agents.base import AgentResult, AgentTask, BaseAgent
from neo.llm.client import Message

from neo.logger import get_logger

logger = get_logger(__name__)


class CodeReviewAgent(BaseAgent):
    """Code review agent for analyzing code quality and suggesting improvements.

    This agent specializes in:
    - Code quality analysis
    - Bug detection
    - Security review
    - Performance optimization suggestions
    - Style consistency
    """

    name = "code_review"
    description = "Code review and quality analysis"
    system_prompt = """You are a code reviewer. Analyze code for correctness, security, performance, and maintainability.

Guidelines:
- Read the code carefully before commenting
- Be specific: cite line numbers and file paths
- Categorize issues by severity (critical/warning/suggestion)
- Explain why something is a problem, not just what
- Suggest concrete fixes or improvements
- Acknowledge good practices you see, not just issues
- Focus on the most important issues first"""

    async def _execute_task(self, task: AgentTask) -> AgentResult:
        """Execute code review task.

        Args:
            task: Task to execute

        Returns:
            AgentResult with review
        """
        logger.info(f"CodeReviewAgent: {task.description}")

        # Build messages with conversation history
        messages = self.build_conversation_messages(task.description)

        # Add context
        if task.context:
            context_str = "\n".join(
                f"{key}: {value}" for key, value in task.context.items()
            )
            messages.append(
                Message(role="system", content=f"Review Context:\n{context_str}")
            )

        result = await self._run_agent_loop(
            messages=messages,
            max_iterations=task.max_iterations,
        )

        # Parse findings
        issues = self._parse_issues(result.content or "")

        return AgentResult(
            success=True,
            content=result.content or "",
            data=issues,
            tokens_used=result.prompt_tokens + result.completion_tokens,
        )

    def _parse_issues(self, content: str) -> dict[str, Any]:
        """Parse review findings.

        Args:
            content: Review content

        Returns:
            Structured findings
        """
        findings: dict[str, Any] = {
            "critical": [],
            "warnings": [],
            "suggestions": [],
            "positive": [],
        }

        lines = content.split("\n")
        current_section = None

        for line in lines:
            # Detect severity
            if "🔴" in line or "Critical" in line:
                current_section = "critical"
            elif "🟡" in line or "Warning" in line:
                current_section = "warnings"
            elif "🟢" in line or "Suggestion" in line:
                current_section = "suggestions"
            elif "✅" in line or "Positive" in line or "done well" in line:
                current_section = "positive"

            # Add to appropriate section
            if current_section and line.strip():
                findings[current_section].append(line.strip())

        return findings

    async def review_file(self, file_path: str) -> AgentResult:
        """Review a specific file.

        Args:
            file_path: Path to file

        Returns:
            AgentResult with review
        """
        task = AgentTask(
            id=f"review_{file_path}",
            type="code_review",
            description=f"Review the file {file_path}. "
                       f"Read the file first, then provide a comprehensive review "
                       f"covering correctness, security, performance, and maintainability.",
            context={"file_path": file_path},
            max_iterations=self.config.max_iterations,
        )
        return await self.execute(task)

    async def review_changes(self, diff: str) -> AgentResult:
        """Review a diff/patch.

        Args:
            diff: Unified diff

        Returns:
            AgentResult with review
        """
        task = AgentTask(
            id="review_diff",
            type="code_review",
            description="Review the following code changes:\n\n```diff\n" + diff + "\n```",
            max_iterations=self.config.max_iterations,
        )
        return await self.execute(task)
