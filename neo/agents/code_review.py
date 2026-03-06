"""Code review agent for analyzing code quality."""

from __future__ import annotations

import logging
from typing import Any

from neo.agents.base import AgentResult, AgentTask, BaseAgent
from neo.llm.client import Message

logger = logging.getLogger(__name__)


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
    system_prompt = """You are an expert code reviewer.

Your job is to analyze code for quality, bugs, security, and performance issues.

Review Criteria:
1. **Correctness** - Does the code work as intended?
2. **Security** - Are there security vulnerabilities?
3. **Performance** - Are there performance issues?
4. **Maintainability** - Is the code readable and maintainable?
5. **Best Practices** - Does it follow language conventions?

Review Process:
1. Read the code carefully
2. Analyze each function/class
3. Check for common pitfalls
4. Look for security issues
5. Suggest improvements with examples

Output Format:
```
## Summary
Brief overview of the code and main findings

## Detailed Review

### [File:line] Issue Category: Description
- **Problem**: What is wrong
- **Impact**: How serious is it
- **Suggestion**: How to fix it with code example
- **Severity**: 🔴 Critical | 🟡 Warning | 🟢 Suggestion

## Positive Findings
What's done well

## Action Items
Priority-ordered list of fixes needed
```

Be specific - include line numbers and code examples.
Be constructive - focus on improvement, not criticism.
Be thorough - check edge cases and error handling.
"""

    DEFAULT_MAX_ITERATIONS = 8

    async def _execute_task(self, task: AgentTask) -> AgentResult:
        """Execute code review task.

        Args:
            task: Task to execute

        Returns:
            AgentResult with review
        """
        logger.info(f"CodeReviewAgent: {task.description}")

        messages = [
            self.build_system_message(),
            Message(role="user", content=task.description),
        ]

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
            max_iterations=self.DEFAULT_MAX_ITERATIONS,
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
            max_iterations=self.DEFAULT_MAX_ITERATIONS,
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
            max_iterations=self.DEFAULT_MAX_ITERATIONS,
        )
        return await self.execute(task)
