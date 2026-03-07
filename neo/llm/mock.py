"""Mock LLM client for testing Neo without API keys."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from neo.llm.client import CompletionResult, Message

from neo.logger import get_logger

logger = get_logger(__name__)


class MockOpenAIClient:
    """Mock OpenAI client for testing without API keys."""

    SUPPORTED_MODELS = [
        "gpt-4o-mini",
        "gpt-4o",
        "mock",
    ]

    def __init__(self, api_key: str = "mock", model: str = "mock"):
        """Initialize the mock client."""
        self.api_key = api_key
        self.model = model
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.call_count = 0

        logger.info(f"Mock OpenAI client initialized (testing mode)")

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> CompletionResult:
        """Return a mock completion response."""
        self.call_count += 1

        # Get the last user message
        last_user_msg = ""
        for msg in reversed(messages):
            if msg.role == "user":
                last_user_msg = msg.content or ""
                break

        logger.debug(f"Mock LLM call #{self.call_count}: {last_user_msg[:50]}...")

        # Simple pattern matching to simulate responses
        content = self._generate_response(last_user_msg, tools)

        # Simulate token usage
        prompt_tokens = sum(len(m.content or "") for m in messages) // 4
        completion_tokens = len(content) // 4
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens

        return CompletionResult(
            content=content,
            tool_calls=[],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=self.model,
        )

    def _generate_response(self, user_input: str, tools: list[dict[str, Any]] | None) -> str:
        """Generate a mock response based on user input."""
        user_lower = user_input.lower()

        # Help response
        if "help" in user_lower or user_lower.strip() == "?":
            return (
                "I'm Neo (MOCK MODE), a coding assistant.\n\n"
                "Available tools:\n"
                "- File: read_file, write_file, edit_file, list_dir, glob\n"
                "- Code: analyze_file, find_symbol\n"
                "- Search: search_code, view\n"
                "- Git: git_status, git_diff, git_add, git_commit, git_log\n"
                "- Shell: run_shell\n"
                "- System: get_system_info\n\n"
                "Try: 'list the current directory' or 'show git status'"
            )

        # File listing
        if any(word in user_lower for word in ["list", "ls", "directory", "dir", "files"]):
            return "[MOCK MODE: Would call list_dir tool to show directory contents]"

        # Git operations
        if "git" in user_lower or "status" in user_lower:
            return "[MOCK MODE: Would call git_status tool]"

        # File reading
        if any(word in user_lower for word in ["read", "show", "view", "open", "file"]):
            return "[MOCK MODE: Would call read_file or view tool]"

        # Search
        if any(word in user_lower for word in ["search", "find", "grep", "pattern"]):
            return "[MOCK MODE: Would call search_code tool]"

        # Shell
        if any(word in user_lower for word in ["run", "execute", "command", "shell"]):
            return "[MOCK MODE: Would call run_shell tool]"

        # Default response
        return (
            f"[MOCK MODE: Received: '{user_input[:50]}...']\n\n"
            "I would normally process this request using the available tools.\n"
            "Set OPENAI_API_KEY in your .env file to use the real LLM."
        )

    def format_tools(self, tools: list[Any]) -> list[dict[str, Any]]:
        """Convert tools to OpenAI function format."""
        return [tool.to_openai_format() for tool in tools]

    def get_token_stats(self) -> dict[str, int]:
        """Get token usage statistics."""
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
        }

    def reset_token_stats(self) -> None:
        """Reset token statistics."""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
