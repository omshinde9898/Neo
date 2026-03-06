"""Multi-agent system for Neo.

This module provides specialized agents for different types of tasks:
- BaseAgent: Base class for all agents
- GeneralAgent: Default coding agent
- ExploreAgent: Fast codebase exploration
- PlanAgent: Implementation planning
- CodeReviewAgent: Code review and analysis
- Orchestrator: Routes tasks to appropriate agents
"""

from neo.agents.base import AgentResult, AgentTask, BaseAgent
from neo.agents.code_review import CodeReviewAgent
from neo.agents.explore import ExploreAgent
from neo.agents.general import GeneralAgent
from neo.agents.orchestrator import AgentOrchestrator
from neo.agents.plan import PlanAgent

__all__ = [
    "BaseAgent",
    "AgentTask",
    "AgentResult",
    "GeneralAgent",
    "ExploreAgent",
    "PlanAgent",
    "CodeReviewAgent",
    "AgentOrchestrator",
]
