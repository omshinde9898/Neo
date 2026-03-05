"""LLM client for Neo."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

try:
    from openai import AsyncOpenAI
    from openai.types.chat import ChatCompletion, ChatCompletionMessage
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A chat message."""

    role: str  # system, user, assistant, tool
    content: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to OpenAI format with valid tool call types."""
        msg: dict[str, Any] = {"role": self.role}

        if self.content:
            msg["content"] = self.content

        if self.tool_calls:
            formatted_calls = []
            for tc in self.tool_calls:
                if "type" not in tc or tc["type"] not in ("function", "allowed_tools", "custom"):
                    tc["type"] = "function"
                formatted_calls.append(tc)
            msg["tool_calls"] = formatted_calls

        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id

        if self.name:
            msg["name"] = self.name

        return msg


@dataclass
class CompletionResult:
    """Result of a completion request."""

    content: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""

    def has_function_calls(self) -> bool:
        """Check if result has function calls."""
        return len(self.tool_calls) > 0

    def get_function_calls(self) -> list[dict[str, Any]]:
        """Get function calls from result."""
        return self.tool_calls


class OpenAIClient:
    """OpenAI API client with function calling support."""

    SUPPORTED_MODELS = [
        "gpt-4o-mini",
        "gpt-4o",
        "o1-mini",
        "o1-preview",
    ]

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str | None = None):
        """Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key (use "ollama" or any string for Ollama)
            model: Model to use (default: gpt-4o-mini)
            base_url: Custom API base URL (e.g., http://localhost:11434/v1 for Ollama)
        """
        if not HAS_OPENAI:
            raise ImportError(
                "OpenAI package not installed. Install with: pip install openai"
            )

        self.api_key = api_key
        self.model = model
        self.base_url = base_url

        # Initialize client with optional base_url
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = AsyncOpenAI(**client_kwargs)

        # Token tracking
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

        if base_url:
            logger.info(f"OpenAI client initialized with model: {model} (base_url: {base_url})")
        else:
            logger.info(f"OpenAI client initialized with model: {model}")

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> CompletionResult:
        """Send completion request to OpenAI.

        Args:
            messages: List of messages
            tools: Optional list of tool definitions
            stream: Whether to stream the response

        Returns:
            CompletionResult with content and/or tool calls
        """
        # Convert messages to OpenAI format
        openai_messages = [m.to_dict() for m in messages]

        logger.debug(f"Sending {len(openai_messages)} messages to OpenAI")
        if tools:
            logger.debug(f"With {len(tools)} tools")

        try:
            # Make the API call
            response: ChatCompletion = await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                stream=False,  # Streaming not implemented yet
            )

            # Extract result
            message = response.choices[0].message

            # Track tokens
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens

            logger.debug(f"Tokens used: {prompt_tokens} prompt, {completion_tokens} completion")

            # Extract tool calls
            tool_calls = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append({
                        "id": tc.id,
                        "type":"function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    })

            return CompletionResult(
                content=message.content,
                tool_calls=tool_calls,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=response.model,
            )

        except Exception as e:
            logger.exception("Error calling OpenAI API")
            raise

    def format_tools(self, tools: list[Any]) -> list[dict[str, Any]]:
        """Convert tools to OpenAI function format.

        Args:
            tools: List of tool objects with to_openai_format method

        Returns:
            List of tool definitions in OpenAI format
        """
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
