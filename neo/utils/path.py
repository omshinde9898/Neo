"""Path utilities for Neo."""

from __future__ import annotations

from pathlib import Path


def resolve_path(path: str, base: Path | None = None) -> Path:
    """Resolve a path, handling ~ and relative paths.

    Args:
        path: Path string to resolve
        base: Base directory for relative paths

    Returns:
        Resolved Path object
    """
    p = Path(path).expanduser()

    if p.is_absolute():
        return p.resolve()

    if base:
        return (base / p).resolve()

    return p.resolve()


def find_project_root(start: Path | None = None, markers: list[str] | None = None) -> Path:
    """Find project root by looking for marker files.

    Args:
        start: Starting directory (default: current directory)
        markers: Files/directories that indicate project root

    Returns:
        Path to project root (or current directory if not found)
    """
    if start is None:
        start = Path.cwd()

    if markers is None:
        markers = [
            ".git",
            "pyproject.toml",
            "package.json",
            "setup.py",
            "Cargo.toml",
            "go.mod",
            ".neo",
        ]

    current = start.resolve()

    while current != current.parent:
        for marker in markers:
            if (current / marker).exists():
                return current
        current = current.parent

    # Fall back to starting directory
    return start.resolve()


def is_safe_path(path: Path, base: Path) -> bool:
    """Check if a path is within a safe base directory.

    Args:
        path: Path to check
        base: Base directory that path should be within

    Returns:
        True if path is within base or base's subdirectories
    """
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False
