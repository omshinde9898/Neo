"""Project memory for Neo."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ProjectMemory:
    """Project-specific context storage."""

    NEO_DIR = ".neo"
    CONFIG_FILE = "project.json"

    def __init__(self, project_path: Path):
        """Initialize project memory.

        Args:
            project_path: Path to the project root
        """
        self.path = Path(project_path).resolve()
        self.config_file = self.path / self.NEO_DIR / self.CONFIG_FILE

        # Project info
        self.languages: list[str] = []
        self.key_files: list[str] = []
        self.description: str = ""

        # Try to load existing config
        self.load()

        # Scan project if no config exists
        if not self.config_file.exists():
            self.scan_project()

    def load(self) -> None:
        """Load project configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self.languages = data.get("languages", [])
                    self.key_files = data.get("key_files", [])
                    self.description = data.get("description", "")
                logger.debug(f"Loaded project config from {self.config_file}")
            except Exception as e:
                logger.warning(f"Failed to load project config: {e}")

    def save(self) -> None:
        """Save project configuration to file."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "languages": self.languages,
                "key_files": self.key_files,
                "description": self.description,
            }
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved project config to {self.config_file}")
        except Exception as e:
            logger.warning(f"Failed to save project config: {e}")

    def scan_project(self) -> None:
        """Scan project to build code map."""
        logger.info(f"Scanning project: {self.path}")

        # Detect languages by file extensions
        extensions: dict[str, int] = {}
        key_files = []

        for file_path in self.path.rglob("*"):
            # Skip hidden dirs and common non-source directories
            if any(part.startswith(".") for part in file_path.relative_to(self.path).parts):
                continue
            if any(part in ["node_modules", "__pycache__", "venv", ".git"] for part in file_path.parts):
                continue

            if file_path.is_file():
                # Count extensions
                ext = file_path.suffix.lower()
                if ext:
                    extensions[ext] = extensions.get(ext, 0) + 1

                # Identify key files
                name = file_path.name.lower()
                if name in [
                    "readme.md", "pyproject.toml", "package.json", "requirements.txt",
                    "makefile", "dockerfile", ".gitignore", "setup.py", "main.py",
                    "app.py", "index.js", "src",
                ]:
                    key_files.append(str(file_path.relative_to(self.path)))

        # Map extensions to languages
        lang_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".jsx": "React",
            ".tsx": "React TypeScript",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".c": "C",
            ".cpp": "C++",
            ".h": "C/C++ Header",
            ".cs": "C#",
            ".rb": "Ruby",
            ".php": "PHP",
            ".swift": "Swift",
            ".kt": "Kotlin",
            ".scala": "Scala",
            ".r": "R",
            ".m": "Objective-C",
            ".sh": "Shell",
            ".html": "HTML",
            ".css": "CSS",
            ".scss": "SCSS",
            ".sass": "Sass",
            ".json": "JSON",
            ".yaml": "YAML",
            ".yml": "YAML",
            ".toml": "TOML",
            ".md": "Markdown",
        }

        # Get top languages by file count
        sorted_exts = sorted(extensions.items(), key=lambda x: x[1], reverse=True)
        self.languages = []
        for ext, count in sorted_exts[:5]:  # Top 5
            if ext in lang_map:
                self.languages.append(lang_map[ext])

        self.key_files = key_files[:10]  # Limit to 10 key files
        self.description = f"Project with {sum(extensions.values())} files"

        self.save()

    def get_context(self) -> str:
        """Generate project context string for system prompt."""
        lines = [
            f"Project: {self.path.name}",
            f"Path: {self.path}",
        ]

        if self.languages:
            lines.append(f"Languages: {', '.join(self.languages)}")

        if self.key_files:
            lines.append(f"Key files: {', '.join(self.key_files[:5])}")

        return "\n".join(lines)

    def get_language_extensions(self) -> list[str]:
        """Get file extensions for detected languages."""
        ext_map = {
            "Python": [".py"],
            "JavaScript": [".js", ".mjs"],
            "TypeScript": [".ts"],
            "React": [".jsx"],
            "React TypeScript": [".tsx"],
            "Go": [".go"],
            "Rust": [".rs"],
            "Java": [".java"],
            "C": [".c", ".h"],
            "C++": [".cpp", ".hpp", ".h"],
            "C#": [".cs"],
            "Ruby": [".rb"],
            "PHP": [".php"],
            "Swift": [".swift"],
            "Kotlin": [".kt"],
            "HTML": [".html", ".htm"],
            "CSS": [".css"],
            "SCSS": [".scss"],
            "Sass": [".sass"],
        }

        extensions = []
        for lang in self.languages:
            if lang in ext_map:
                extensions.extend(ext_map[lang])

        return extensions
