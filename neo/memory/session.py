"""Session memory for Neo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Turn:
    """A conversation turn."""

    role: str  # user, assistant
    content: str


class SessionMemory:
    """In-memory conversation history."""

    def __init__(self, max_turns: int = 20):
        """Initialize session memory.

        Args:
            max_turns: Maximum number of turns to keep
        """
        self.turns: list[Turn] = []
        self.max_turns = max_turns

    def add_turn(self, role: str, content: str) -> None:
        """Add a conversation turn.

        Args:
            role: 'user' or 'assistant'
            content: The message content
        """
        self.turns.append(Turn(role=role, content=content))

        # Trim old turns if exceeding max
        if len(self.turns) > self.max_turns:
            # Keep only the most recent turns
            self.turns = self.turns[-self.max_turns:]

    def get_messages(self) -> list[dict[str, str]]:
        """Get all turns as message dictionaries."""
        return [{"role": t.role, "content": t.content} for t in self.turns]

    def clear(self) -> None:
        """Clear all conversation history."""
        self.turns = []

    def get_last_n(self, n: int) -> list[Turn]:
        """Get last n turns."""
        return self.turns[-n:] if n < len(self.turns) else self.turns

    def __len__(self) -> int:
        """Get number of turns."""
        return len(self.turns)
