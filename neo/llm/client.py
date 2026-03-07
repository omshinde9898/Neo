"""LLM client for Neo with streaming support."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable

try:
    from openai import AsyncOpenAI
    from openai.types.chat import ChatCompletionChunk
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from neo.logger import get_logger

logger = get_logger(__name__)


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


class StreamingResponse:
    """Handler for streaming LLM responses."""

    def __init__(
        self,
        stream: AsyncIterator[ChatCompletionChunk],
        callback: Callable[[str], None] | None = None,
    ):
        """Initialize streaming response handler.

        Args:
            stream: The async stream from OpenAI
            callback: Optional callback for each token
        """
        self.stream = stream
        self.callback = callback
        self.content_parts: list[str] = []
        self.tool_calls: list[dict[str, Any]] = []
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.model = ""

    async def accumulate(self) -> CompletionResult:
        """Accumulate the stream and return final result.

        Returns:
            CompletionResult with accumulated content
        """
        async for chunk in self.stream:
            # Get model from first chunk
            if not self.model and hasattr(chunk, "model"):
                self.model = chunk.model

            # Process delta
            if chunk.choices:
                delta = chunk.choices[0].delta

                # Handle content
                if delta.content:
                    self.content_parts.append(delta.content)
                    if self.callback:
                        self.callback(delta.content)

                # Handle tool calls
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        # Accumulate tool call data
                        idx = tc_delta.index
                        while len(self.tool_calls) <= idx:
                            self.tool_calls.append({
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            })

                        # Update tool call
                        if tc_delta.id:
                            self.tool_calls[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                self.tool_calls[idx]["function"]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                self.tool_calls[idx]["function"]["arguments"] += tc_delta.function.arguments

                # Handle finish reason
                if chunk.choices[0].finish_reason:
                    logger.debug(f"Stream finished: {chunk.choices[0].finish_reason}")

        # Compile result
        content = "".join(self.content_parts) if self.content_parts else None

        return CompletionResult(
            content=content,
            tool_calls=self.tool_calls,
            completion_tokens=len(self.content_parts),
            model=self.model,
        )


class OpenAIClient:
    """OpenAI API client with function calling and streaming support."""

    SUPPORTED_MODELS = [
        "gpt-4o-mini",
        "gpt-4o",
        "o1-mini",
        "o1-preview",
    ]

    # Pricing per 1M tokens (input, output) in USD
    PRICING = {
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
        "o1-preview": (15.00, 60.00),
        "o1-mini": (3.00, 12.00),
        "gpt-4-turbo": (10.00, 30.00),
        "gpt-4": (30.00, 60.00),
        "gpt-3.5-turbo": (0.50, 1.50),
    }

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str | None = None):
        """Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key
            model: Model to use
            base_url: Custom API base URL (e.g., for Ollama)
        """
        if not HAS_OPENAI:
            raise ImportError(
                "OpenAI package not installed. Install with: pip install openai"
            )

        self.api_key = api_key
        self.model = model
        self.base_url = base_url

        # Initialize client
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = AsyncOpenAI(**client_kwargs)

        # Token tracking
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

        logger.info(f"OpenAI client initialized with model: {model}")

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        streaming_callback: Callable[[str], None] | None = None,
    ) -> CompletionResult:
        """Send completion request to OpenAI.

        Args:
            messages: List of messages
            tools: Optional list of tool definitions
            stream: Whether to stream the response
            streaming_callback: Optional callback for streaming tokens

        Returns:
            CompletionResult with content and/or tool calls
        """
        openai_messages = [m.to_dict() for m in messages]

        logger.debug(f"Sending {len(openai_messages)} messages to OpenAI")

        try:
            if stream:
                # Streaming mode
                response_stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=openai_messages,
                    tools=tools if tools else None,
                    tool_choice="auto" if tools else None,
                    stream=True,
                )

                stream_handler = StreamingResponse(response_stream, streaming_callback)
                result = await stream_handler.accumulate()

                # Update token stats (estimated for streaming)
                self.total_completion_tokens += len(stream_handler.content_parts)

                return result
            else:
                # Non-streaming mode
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=openai_messages,
                    tools=tools if tools else None,
                    tool_choice="auto" if tools else None,
                    stream=False,
                )

                # Extract result
                message = response.choices[0].message

                # Track tokens
                prompt_tokens = response.usage.prompt_tokens if response.usage else 0
                completion_tokens = response.usage.completion_tokens if response.usage else 0
                self.total_prompt_tokens += prompt_tokens
                self.total_completion_tokens += completion_tokens

                # Extract tool calls
                tool_calls = []
                if message.tool_calls:
                    for tc in message.tool_calls:
                        tool_calls.append({
                            "id": tc.id,
                            "type": "function",
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
            tools: List of tool objects

        Returns:
            List of tool definitions
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

    def get_cost_stats(self) -> dict[str, Any]:
        """Get cost statistics with pricing breakdown.

        Returns:
            Dict with token counts and estimated cost in USD
        """
        prompt_tokens = self.total_prompt_tokens
        completion_tokens = self.total_completion_tokens
        total_tokens = prompt_tokens + completion_tokens

        # Get pricing for current model (fallback to gpt-4o-mini if unknown)
        model_pricing = self.PRICING.get(self.model, self.PRICING["gpt-4o-mini"])
        input_price_per_1m, output_price_per_1m = model_pricing

        # Calculate costs (price per 1M tokens)
        input_cost = (prompt_tokens / 1_000_000) * input_price_per_1m
        output_cost = (completion_tokens / 1_000_000) * output_price_per_1m
        total_cost = input_cost + output_cost

        return {
            "model": self.model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "input_price_per_1m": input_price_per_1m,
            "output_price_per_1m": output_price_per_1m,
        }

    def format_cost_report(self) -> str:
        """Format a cost report for display.

        Returns:
            Formatted cost report string
        """
        stats = self.get_cost_stats()

        lines = [
            "📊 Session Cost Report",
            "",
            f"Model: {stats['model']}",
            f"Pricing: ${stats['input_price_per_1m']:.2f} / ${stats['output_price_per_1m']:.2f} per 1M tokens",
            "",
            "Token Usage:",
            f"  Input tokens:  {stats['prompt_tokens']:,}",
            f"  Output tokens: {stats['completion_tokens']:,}",
            f"  Total tokens:  {stats['total_tokens']:,}",
            "",
            "Estimated Cost:",
            f"  Input cost:  ${stats['input_cost']:.6f}",
            f"  Output cost: ${stats['output_cost']:.6f}",
            f"  Total cost:  ${stats['total_cost']:.6f}",
        ]

        return "\n".join(lines)
