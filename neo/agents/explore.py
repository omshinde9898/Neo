"""Explore agent for fast codebase navigation and search."""

from __future__ import annotations

from typing import Any

from neo.agents.base import AgentResult, AgentTask, BaseAgent
from neo.llm.client import Message

from neo.logger import get_logger

logger = get_logger(__name__)


class ExploreAgent(BaseAgent):
    """Fast exploration agent for codebase navigation.

    This agent is optimized for:
    - Finding files and symbols quickly
    - Understanding project structure
    - Searching code patterns
    - Mapping code relationships

    It uses a faster, more focused approach than the general agent.
    """

    name = "explore"
    description = "Fast codebase exploration and navigation"
    system_prompt = """You are a code explorer. Help users understand and navigate codebases quickly.

Guidelines:
- Use search and glob tools to find relevant files efficiently
- Show file paths with line numbers when referencing code
- Summarize what you find in a scannable format (bullet points, short paragraphs)
- If a search returns many results, prioritize the most relevant ones
- Explain patterns you notice in the codebase structure
- Suggest where to look next if the answer isn't complete"""

    async def _execute_task(self, task: AgentTask) -> AgentResult:
        """Execute an exploration task.

        Args:
            task: Task to execute

        Returns:
            AgentResult with findings
        """
        logger.info(f"ExploreAgent: {task.description}")

        # Build focused exploration prompt
        explore_prompt = self._build_exploration_prompt(task)

        # Build messages with conversation history
        messages = self.build_conversation_messages(explore_prompt)

        # Run exploration (use config max_iterations via base class)
        result = await self._run_agent_loop(
            messages=messages,
            max_iterations=task.max_iterations,
        )

        # Parse exploration results
        findings = self._parse_findings(result.content or "")

        return AgentResult(
            success=True,
            content=result.content or "",
            data=findings,
            tokens_used=result.prompt_tokens + result.completion_tokens,
        )

    def _build_exploration_prompt(self, task: AgentTask) -> str:
        """Build a focused exploration prompt.

        Args:
            task: The exploration task

        Returns:
            Optimized prompt for exploration
        """
        base_prompt = task.description

        # Add context hints
        hints = []

        if "find" in task.description.lower() or "where" in task.description.lower():
            hints.append("Use search_code and find_symbol for locating symbols")

        if "structure" in task.description.lower() or "organize" in task.description.lower():
            hints.append("Use list_dir and glob to map the project structure")

        if hints:
            base_prompt += f"\n\nHints: {'; '.join(hints)}"

        return base_prompt

    def _parse_findings(self, content: str) -> dict[str, Any]:
        """Parse exploration results into structured data.

        Args:
            content: The agent's response

        Returns:
            Structured findings
        """
        findings: dict[str, Any] = {
            "files_found": [],
            "symbols_found": [],
            "patterns": [],
        }

        # Extract file paths (lines containing .py, .js, etc.)
        lines = content.split("\n")
        for line in lines:
            # Look for file references
            for ext in [".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp"]:
                if ext in line and "/" in line or "\\" in line:
                    findings["files_found"].append(line.strip())

            # Look for symbol references (function, class definitions)
            if "def " in line or "class " in line:
                findings["symbols_found"].append(line.strip())

        return findings

    async def find_symbol(self, symbol_name: str) -> AgentResult:
        """Quickly find a symbol in the codebase.

        Args:
            symbol_name: Name of the symbol to find

        Returns:
            AgentResult with locations
        """
        task = AgentTask(
            id=f"find_{symbol_name}",
            type="explore",
            description=f"Find all definitions of '{symbol_name}' in the codebase. "
                       f"Search in Python files, JavaScript files, etc. "
                       f"Report file paths and line numbers.",
            max_iterations=3,
        )
        return await self.execute(task)

    async def map_project(self) -> AgentResult:
        """Map the overall project structure.

        Returns:
            AgentResult with project structure
        """
        task = AgentTask(
            id="map_project",
            type="explore",
            description="Map the project structure. Show: "
                       "1. Directory organization "
                       "2. Key configuration files "
                       "3. Entry points (main, index, etc.) "
                       "4. Test directory location "
                       "5. Documentation files",
            max_iterations=4,
        )
        return await self.execute(task)

    async def search_pattern(self, pattern: str) -> AgentResult:
        """Search for a pattern across the codebase.

        Args:
            pattern: Regex pattern to search

        Returns:
            AgentResult with matches
        """
        task = AgentTask(
            id=f"search_{pattern}",
            type="explore",
            description=f"Search for pattern '{pattern}' across all source files. "
                       f"Report all matches with file paths and context.",
            max_iterations=3,
        )
        return await self.execute(task)
