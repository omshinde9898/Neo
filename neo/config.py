"""Configuration management for Neo."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from platformdirs import user_config_dir

# Load .env file from current directory or parent directories
def _load_env_files() -> None:
    """Load .env files from current directory, project root, and home directory."""
    # Try current directory first
    load_dotenv(".env")
    load_dotenv(".env.local")

    # Try to find project root (stop at home directory)
    current = Path.cwd()
    home = Path.home()
    for _ in range(5):  # Check up to 5 parent directories
        load_dotenv(current / ".env")
        load_dotenv(current / ".env.local")
        if (current / ".git").exists() or (current / ".neo").exists():
            break
        # Stop if we reached home directory or filesystem root
        if current == home or current.parent == current:
            break
        current = current.parent

    # Load from home directory as fallback (lowest priority)
    load_dotenv(home / ".env")
    load_dotenv(home / ".neo" / ".env")

_load_env_files()


@dataclass
class Config:
    """Neo configuration settings."""

    # OpenAI / OpenAI-compatible API (e.g., Ollama, vLLM)
    openai_api_key: str = ""
    model: str = "gpt-4o-mini"
    base_url: str | None = None  # Custom API base URL (e.g., http://localhost:11434/v1 for Ollama)
    mock_mode: bool = False  # Use mock LLM for testing

    # Behavior
    max_iterations: int = 50
    auto_confirm_edits: bool = False
    show_diffs: bool = True

    # Context
    max_session_turns: int = 20
    include_project_context: bool = True

    # UI
    theme: str = "monokai"
    streaming: bool = True

    # Safety
    shell_blocked_commands: list[str] = field(
        default_factory=lambda: [
            "rm -rf /",
            "rm -rf /*",
            "format",
            "mkfs",
            "dd if=/dev/zero",
        ]
    )

    @classmethod
    def load(cls) -> Config:
        """Load configuration from file or environment."""
        config = cls()

        # Try config file first
        config_path = cls.get_config_path()
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)

        # Environment variables override config file
        if api_key := os.getenv("OPENAI_API_KEY"):
            config.openai_api_key = api_key
        if model := os.getenv("NEO_MODEL"):
            config.model = model
        if base_url := os.getenv("OPENAI_BASE_URL"):
            config.base_url = base_url
        if auto_confirm := os.getenv("NEO_AUTO_CONFIRM"):
            config.auto_confirm_edits = auto_confirm.lower() in ("true", "1", "yes")
        if mock_mode := os.getenv("NEO_MOCK"):
            config.mock_mode = mock_mode.lower() in ("true", "1", "yes")

        return config

    def save(self) -> None:
        """Save configuration to file."""
        config_path = self.get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict, excluding empty API key for security
        data = {
            "model": self.model,
            "max_iterations": self.max_iterations,
            "auto_confirm_edits": self.auto_confirm_edits,
            "show_diffs": self.show_diffs,
            "max_session_turns": self.max_session_turns,
            "include_project_context": self.include_project_context,
            "theme": self.theme,
            "streaming": self.streaming,
            "shell_blocked_commands": self.shell_blocked_commands,
        }

        # Only save API key if explicitly set (not from env)
        if self.openai_api_key and not os.getenv("OPENAI_API_KEY"):
            data["openai_api_key"] = self.openai_api_key

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the path to the config file."""
        config_dir = Path(user_config_dir("neo", "neo-ai"))
        return config_dir / "config.json"

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if not self.openai_api_key:
            errors.append("OpenAI API key not set. Set OPENAI_API_KEY environment variable.")

        supported_models = ["gpt-4o-mini", "gpt-4o", "o1-mini", "o1-preview"]
        if self.model not in supported_models:
            errors.append(f"Unsupported model: {self.model}. Supported: {supported_models}")

        return errors
